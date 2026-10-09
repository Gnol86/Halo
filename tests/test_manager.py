"""Integration lifecycle with real persistence and generated Home Assistant devices."""

import asyncio
from copy import deepcopy
from unittest.mock import patch

import pytest
from homeassistant.auth.const import GROUP_ID_READ_ONLY
from homeassistant.core import Context
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, MockUser

from custom_components.halo.const import DOMAIN
from custom_components.halo.manager import HaloError


async def configured(hass):
    area = ar.async_get(hass).async_create("Living room")
    hass.states.async_set(
        "light.bulb", "off", {"supported_color_modes": ["brightness"]}
    )
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, title="Halo", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    manager = entry.runtime_data
    config = deepcopy(manager.config)
    config["rooms"][area.id] = {"lights": ["light.bulb"]}
    await manager.async_save_config(config, manager.revision)
    await hass.async_block_till_done()
    return entry, area, manager


async def test_room_creation_rename_reload_remove(hass):
    entry, area, manager = await configured(hass)
    devices = dr.async_get(hass)
    device = devices.async_get_device_by_identifier((DOMAIN, area.id), entry.entry_id)
    assert device is not None
    assert device.area_id == area.id
    assert (
        len(er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)) == 4
    )
    ar.async_get(hass).async_update(area.id, name="Salon")
    await hass.async_block_till_done()
    assert devices.async_get(device.id).name == "Salon"
    assert manager.room_name(area.id) == "Salon"
    manager.runtime_state[area.id]["pause_until"] = 4102444800
    await manager.async_persist_runtime()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    manager = entry.runtime_data
    assert manager.config["rooms"][area.id]["lights"] == ["light.bulb"]
    assert manager.runtime_state[area.id]["pause_until"] == 4102444800
    assert (
        devices.async_get_device_by_identifier((DOMAIN, area.id), entry.entry_id).id
        == device.id
    )
    config = deepcopy(manager.config)
    config["rooms"].clear()
    await manager.async_save_config(config, manager.revision)
    await hass.async_block_till_done()
    assert not er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert not devices.async_get_device_by_identifier((DOMAIN, area.id), entry.entry_id)


async def test_validation_is_atomic_and_rejects_halo_members(hass):
    entry, area, manager = await configured(hass)
    saved, revision = deepcopy(manager.config), manager.revision
    invalid = deepcopy(saved)
    invalid["rooms"][area.id]["lux_entity_id"] = "sensor.lux"
    with pytest.raises(HaloError, match="lux_threshold"):
        await manager.async_save_config(invalid, revision)
    assert manager.config == saved
    assert manager.revision == revision
    own_light = next(
        item.entity_id
        for item in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
        if item.domain == "light"
    )
    invalid = deepcopy(saved)
    invalid["rooms"][area.id]["lights"] = [own_light]
    with pytest.raises(HaloError, match="Halo lights"):
        await manager.async_save_config(invalid, revision)
    with pytest.raises(HaloError, match="refresh"):
        await manager.async_save_config(saved, revision - 1)


async def test_runtime_does_not_write_unchanged_snapshots(hass):
    _, _, manager = await configured(hass)
    with patch.object(manager._store, "async_save") as save:
        await manager.async_persist_runtime()
        await manager.async_persist_runtime()
        save.assert_not_called()


async def test_snapshot_during_write_is_consistent(hass, hass_admin_user):
    _, _, manager = await configured(hass)
    new_area = ar.async_get(hass).async_create("Bedroom")
    updated = deepcopy(manager.config)
    updated["rooms"][new_area.id] = {"lights": []}
    entered, release = asyncio.Event(), asyncio.Event()
    original_save = manager._store.async_save

    async def delayed(data):
        entered.set()
        await release.wait()
        await original_save(data)

    with patch.object(manager._store, "async_save", side_effect=delayed):
        task = hass.async_create_task(
            manager.async_save_config(updated, manager.revision)
        )
        await entered.wait()
        snapshot = manager.snapshot(hass_admin_user)
        assert new_area.id not in snapshot["config"]["rooms"]
        assert set(snapshot["status"]) == set(snapshot["config"]["rooms"])
        release.set()
        await task
    snapshot = manager.snapshot(hass_admin_user)
    assert new_area.id in snapshot["status"]


async def test_native_modes_respect_member_permissions(hass):
    _, area, manager = await configured(hass)
    group = await hass.auth.async_get_group(GROUP_ID_READ_ONLY)
    user = MockUser(groups=[group]).add_to_hass(hass)
    context = Context(user_id=user.id)
    with pytest.raises(Unauthorized):
        await manager.async_set_mode(area.id, "automation", True, context)
    with pytest.raises(Unauthorized):
        await manager.async_resume(area.id, context)
    assert not manager.config["rooms"][area.id]["automation_enabled"]


async def test_failed_load_preserves_invalid_saved_data(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, title="Halo", data={})
    entry.add_to_hass(hass)
    invalid = {"config": {"rooms": {"living": {"lights": ["sensor.bad"]}}}}
    with (
        patch("custom_components.halo.manager.Store.async_load", return_value=invalid),
        patch("custom_components.halo.manager.Store.async_save") as save,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        save.assert_not_called()
