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


@pytest.mark.parametrize(
    ("absence_delay", "manual_pause", "transitions"),
    [
        (
            120,
            900,
            dict.fromkeys(("turn_on", "lux_on", "natural", "scene", "turn_off")),
        ),
        (
            0,
            0,
            {
                "turn_on": None,
                "lux_on": 0,
                "natural": None,
                "scene": 6.5,
                "turn_off": None,
            },
        ),
    ],
)
async def test_saved_defaults_are_not_replaced_when_reloading(
    hass, absence_delay, manual_pause, transitions
):
    entry, area, manager = await configured(hass)
    assert manager.config["rooms"][area.id]["absence_delay"] == 0
    assert manager.config["rooms"][area.id]["manual_pause"] == 7200
    saved = deepcopy(manager.config)
    saved["transitions"] = transitions
    saved["rooms"][area.id].update(
        absence_delay=absence_delay,
        manual_pause=manual_pause,
        transitions={
            "turn_on": None,
            "lux_on": 0,
            "natural": "inherit",
            "scene": 4.5,
            "turn_off": "inherit",
        },
    )
    await manager.async_save_config(saved, manager.revision)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.config == saved


async def test_light_catalogue_identifies_groups_and_direct_membership(
    hass, hass_admin_user
):
    _, _, manager = await configured(hass)
    registry_group = er.async_get(hass).async_get_or_create(
        "light", "group", "registry-group", suggested_object_id="registry_group"
    )
    hass.states.async_set(registry_group.entity_id, "unavailable")
    hass.states.async_set("light.other", "off")
    hass.states.async_set(
        "light.desk", "on", {"entity_id": ["light.bulb", "light.other"]}
    )
    hass.states.async_set("group.room", "on", {"entity_id": ["light.desk"]})
    hass.states.async_set("light.nested", "on", {"entity_id": ("light.desk",)})
    snapshot = manager.snapshot(hass_admin_user)
    lights = {light["entity_id"]: light for light in snapshot["lights"]}
    assert lights[registry_group.entity_id]["is_group"] is True
    assert lights[registry_group.entity_id]["group_members"] == []
    assert lights["light.bulb"]["is_group"] is False
    assert lights["light.bulb"]["group_members"] == []
    assert lights["light.bulb"]["member_of"] == ["light.desk"]
    assert lights["light.desk"]["is_group"] is True
    assert lights["light.desk"]["group_members"] == ["light.bulb", "light.other"]
    assert lights["light.desk"]["member_of"] == ["group.room", "light.nested"]
    assert lights["light.nested"]["group_members"] == ["light.desk"]
    # Metadata returned to a browser must not mutate Home Assistant's state.
    lights["light.desk"]["group_members"].clear()
    assert hass.states.get("light.desk").attributes["entity_id"] == [
        "light.bulb",
        "light.other",
    ]


async def test_group_catalogue_does_not_expose_unreadable_members_or_groups(hass):
    _, _, manager = await configured(hass)
    hass.states.async_set("light.secret", "off")
    hass.states.async_set(
        "light.visible_group", "on", {"entity_id": ["light.bulb", "light.secret"]}
    )
    hass.states.async_set("light.hidden_group", "on", {"entity_id": ["light.bulb"]})
    user = MockUser().add_to_hass(hass)
    user.mock_policy(
        {"entities": {"entity_ids": {"light.bulb": True, "light.visible_group": True}}}
    )
    snapshot = manager.snapshot(user)
    lights = {light["entity_id"]: light for light in snapshot["lights"]}
    assert set(lights) == {"light.bulb", "light.visible_group"}
    assert lights["light.bulb"]["member_of"] == ["light.visible_group"]
    assert lights["light.visible_group"]["group_members"] == ["light.bulb"]
    entities = {entity["entity_id"]: entity for entity in snapshot["entities"]}
    assert entities["light.visible_group"]["attributes"]["entity_id"] == ["light.bulb"]
    assert "light.secret" not in repr(snapshot)
    assert "light.hidden_group" not in repr(snapshot)
