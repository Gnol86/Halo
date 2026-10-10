"""Adversarial manager lifecycle checks for the local pre-release review."""

import asyncio
from copy import deepcopy
from unittest.mock import patch

import pytest
from test_manager import configured

from custom_components.halo.manager import HaloError


@pytest.mark.parametrize("command", ["automation", "natural", "resume"])
async def test_storage_failure_before_mode_change_preserves_saved_state(hass, command):
    """A failed durable write must not publish a new mode or clear a pause."""
    entry, area, manager = await configured(hass)
    manager.runtime_state[area.id]["pause_until"] = 4102444800
    manager.runtime_state[area.id]["nightlight_blocked"] = True
    await manager.async_persist_runtime()
    original = deepcopy(manager.config)
    runtime = deepcopy(manager.runtime_state)
    revision = manager.revision
    engine = manager.engines[area.id]
    with patch.object(manager._store, "async_save", side_effect=OSError("disk full")):
        with pytest.raises(OSError, match="disk full"):
            if command == "resume":
                await manager.async_resume(area.id)
            else:
                await manager.async_set_mode(area.id, command, command == "automation")
        assert manager.config == original
        assert manager.runtime_state == runtime
        assert manager.revision == revision
        assert not engine._automation_suspensions
    await hass.config_entries.async_unload(entry.entry_id)


async def test_failed_room_removal_keeps_engine_listening(hass):
    """Even a failure while stopping a room must leave its existing engine active."""
    entry, area, manager = await configured(hass)
    manager.runtime_state[area.id]["pause_until"] = 4102444800
    original = deepcopy(manager.config)
    revision = manager.revision
    removed = deepcopy(original)
    removed["rooms"].clear()
    with patch.object(manager._store, "async_save", side_effect=OSError("disk full")):
        with pytest.raises(OSError, match="disk full"):
            await manager.async_save_config(removed, revision)
        assert manager.config == original
        assert manager.revision == revision
        assert not manager.engines[area.id]._stopped
        assert manager.engines[area.id]._unsubscribers
    await hass.config_entries.async_unload(entry.entry_id)


async def test_room_removal_commits_without_deleted_runtime(hass):
    """The deletion transaction cannot leave a stale manual hold on disk."""
    entry, area, manager = await configured(hass)
    manager.runtime_state[area.id]["pause_until"] = 4102444800
    manager.runtime_state[area.id]["nightlight_blocked"] = True
    await manager.async_persist_runtime()
    removed = deepcopy(manager.config)
    removed["rooms"].clear()
    await manager.async_save_config(removed, manager.revision)
    stored = await manager._store.async_load()
    assert area.id not in stored["config"]["rooms"]
    assert area.id not in stored["runtime"]
    await hass.config_entries.async_unload(entry.entry_id)


async def test_concurrent_saves_accept_only_one_revision(hass):
    """Two valid browser drafts with the same revision cannot silently overwrite."""
    entry, _, manager = await configured(hass)
    first, second = deepcopy(manager.config), deepcopy(manager.config)
    first["presence_return_window"] = 41
    second["presence_return_window"] = 59
    revision = manager.revision
    results = await asyncio.gather(
        manager.async_save_config(first, revision),
        manager.async_save_config(second, revision),
        return_exceptions=True,
    )
    assert sum(result is None for result in results) == 1
    errors = [result for result in results if isinstance(result, HaloError)]
    assert len(errors) == 1
    assert errors[0].code == "conflict"
    assert manager.revision == revision + 1
    stored = await manager._store.async_load()
    assert stored["config"] == manager.config
    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("command", ["automation", "natural", "resume"])
async def test_mode_is_not_published_during_delayed_storage(
    hass, hass_admin_user, command
):
    """Subscribers see either the old complete state or the durable new state."""
    entry, area, manager = await configured(hass)
    manager.runtime_state[area.id]["pause_until"] = 4102444800
    manager.runtime_state[area.id]["nightlight_blocked"] = True
    await manager.async_persist_runtime()
    original = manager.snapshot(hass_admin_user)
    started, finish = asyncio.Event(), asyncio.Event()
    save = manager._store.async_save

    async def delayed(data):
        started.set()
        await finish.wait()
        await save(data)

    with patch.object(manager._store, "async_save", side_effect=delayed):
        operation = (
            manager.async_resume(area.id)
            if command == "resume"
            else manager.async_set_mode(area.id, command, command == "automation")
        )
        pending = hass.async_create_task(operation)
        await started.wait()
        during = manager.snapshot(hass_admin_user)
        assert during["revision"] == original["revision"]
        assert during["config"] == original["config"]
        assert manager.runtime_state[area.id]["pause_until"] == 4102444800
        finish.set()
        await pending
    after = manager.snapshot(hass_admin_user)
    assert after["revision"] == original["revision"] + 1
    stored = await manager._store.async_load()
    assert stored["config"] == after["config"]
    if command == "resume":
        assert "pause_until" not in stored["runtime"][area.id]
        assert "nightlight_blocked" not in stored["runtime"][area.id]
    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("mode, enabled", [("invalid", True), ("automation", 1)])
async def test_invalid_mode_does_not_change_revision(hass, mode, enabled):
    entry, area, manager = await configured(hass)
    revision = manager.revision
    with pytest.raises(HaloError, match="Invalid room mode"):
        await manager.async_set_mode(area.id, mode, enabled)
    assert manager.revision == revision
    await hass.config_entries.async_unload(entry.entry_id)


async def test_resume_commit_preserves_presence_event_during_storage(hass, freezer):
    """A detector's event timestamp survives a slow durable pause reset."""
    entry, area, manager = await configured(hass)
    hass.states.async_set("binary_sensor.presence", "on")
    config = deepcopy(manager.config)
    config["rooms"][area.id].update(
        presence_entity_id="binary_sensor.presence", absence_delay=30
    )
    await manager.async_save_config(config, manager.revision)
    manager.runtime_state[area.id]["pause_until"] = 4102444800
    await manager.async_persist_runtime()
    started, finish = asyncio.Event(), asyncio.Event()
    save = manager._store.async_save

    async def delayed(data):
        started.set()
        await finish.wait()
        await save(data)

    with patch.object(manager._store, "async_save", side_effect=delayed):
        pending = hass.async_create_task(manager.async_resume(area.id))
        await started.wait()
        hass.states.async_set("binary_sensor.presence", "off")
        absence_started = hass.states.get(
            "binary_sensor.presence"
        ).last_changed.timestamp()
        for _ in range(3):
            await asyncio.sleep(0)
        assert manager.runtime_state[area.id]["absent_since"] == absence_started
        freezer.tick(10)
        finish.set()
        await pending
        await hass.async_block_till_done()
    runtime = manager.runtime_state[area.id]
    assert runtime["absent_since"] == absence_started
    assert manager.engines[area.id]._absence_deadline == absence_started + 30
    assert (await manager._store.async_load())["runtime"][area.id] == runtime
    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("command", ["natural", "resume"])
async def test_failed_mode_commit_does_not_strand_preempted_lamps(hass, command):
    """A rejected mode request cannot leave an interrupted old all-on half done."""
    entry, area, manager = await configured(hass)
    hass.states.async_set(
        "light.second", "off", {"supported_color_modes": ["brightness"]}
    )
    hass.states.async_set("binary_sensor.presence", "off")
    config = deepcopy(manager.config)
    config["rooms"][area.id].update(
        lights=["light.bulb", "light.second"],
        presence_entity_id="binary_sensor.presence",
        automation_enabled=True,
    )
    await manager.async_save_config(config, manager.revision)
    revision = manager.revision
    started, finish = asyncio.Event(), asyncio.Event()
    calls = []

    async def lamp(call):
        entity_id = call.data["entity_id"]
        calls.append(entity_id)
        if entity_id == "light.bulb" and len(calls) == 1:
            started.set()
            await finish.wait()
        hass.states.async_set(
            entity_id,
            "on",
            {"supported_color_modes": ["brightness"]},
            context=call.context,
        )

    hass.services.async_register("light", "turn_on", lamp)
    save = manager._store.async_save

    async def reject_new_config(data):
        if data["revision"] > revision:
            raise OSError("disk full")
        await save(data)

    hass.states.async_set("binary_sensor.presence", "on")
    await started.wait()
    with patch.object(manager._store, "async_save", side_effect=reject_new_config):
        operation = (
            manager.async_resume(area.id)
            if command == "resume"
            else manager.async_set_mode(area.id, "natural", False)
        )
        pending = hass.async_create_task(operation)
        for _ in range(3):
            await asyncio.sleep(0)
        finish.set()
        with pytest.raises(OSError, match="disk full"):
            await pending
        await hass.async_block_till_done()
    assert manager.revision == revision
    assert manager.config["rooms"][area.id]["natural_enabled"] is True
    assert hass.states.get("light.bulb").state == "on"
    assert hass.states.get("light.second").state == "on"
    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("command", ["natural", "resume"])
async def test_failed_mode_recovery_never_overrides_new_manual_off(hass, command):
    """A newer manual intention cancels recovery of the rejected mode request."""
    entry, area, manager = await configured(hass)
    hass.states.async_set(
        "light.second", "off", {"supported_color_modes": ["brightness"]}
    )
    hass.states.async_set("binary_sensor.presence", "off")
    config = deepcopy(manager.config)
    config["rooms"][area.id].update(
        lights=["light.bulb", "light.second"],
        presence_entity_id="binary_sensor.presence",
        automation_enabled=True,
    )
    await manager.async_save_config(config, manager.revision)
    revision = manager.revision
    started, finish = asyncio.Event(), asyncio.Event()
    committing, reject = asyncio.Event(), asyncio.Event()
    calls = []

    async def lamp(call):
        entity_id = call.data["entity_id"]
        calls.append((entity_id, call.service))
        if len(calls) == 1:
            started.set()
            await finish.wait()
        hass.states.async_set(
            entity_id,
            "on" if call.service == "turn_on" else "off",
            {"supported_color_modes": ["brightness"]},
            context=call.context,
        )

    hass.services.async_register("light", "turn_on", lamp)
    hass.services.async_register("light", "turn_off", lamp)
    save = manager._store.async_save

    async def reject_new_config(data):
        if data["revision"] > revision:
            committing.set()
            await reject.wait()
            raise OSError("disk full")
        await save(data)

    hass.states.async_set("binary_sensor.presence", "on")
    await started.wait()
    with patch.object(manager._store, "async_save", side_effect=reject_new_config):
        operation = (
            manager.async_resume(area.id)
            if command == "resume"
            else manager.async_set_mode(area.id, "natural", False)
        )
        pending = hass.async_create_task(operation)
        for _ in range(3):
            await asyncio.sleep(0)
        finish.set()
        await committing.wait()
        manual = hass.async_create_task(manager.async_room_command(area.id, "turn_off"))
        for _ in range(3):
            await asyncio.sleep(0)
        reject.set()
        with pytest.raises(OSError, match="disk full"):
            await pending
        await manual
        await hass.async_block_till_done()
    assert manager.revision == revision
    assert hass.states.get("light.bulb").state == "off"
    assert hass.states.get("light.second").state == "off"
    assert [target for target, service in calls if service == "turn_on"] == [
        "light.bulb"
    ]
    assert manager.runtime_state[area.id]["pause_until"]
    await hass.config_entries.async_unload(entry.entry_id)
