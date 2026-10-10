"""A valid automation-off request preempts native recall across manager locks."""

import asyncio
from copy import deepcopy
from unittest.mock import patch

import pytest
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from test_external_scenes import linked
from test_manager import configured

from custom_components.halo.manager import HaloError


@pytest.mark.parametrize("initial_action", ["enable", "resume"])
async def test_disable_preempts_slow_recall_and_queued_evaluation(hass, initial_action):
    entry, area, manager = await configured(hass)
    hass.states.async_set("scene.native", "unknown", {"entity_id": ["light.bulb"]})
    hass.states.async_set("input_boolean.tv", "on")
    condition = {"type": "state", "entity_id": "input_boolean.tv", "state": "on"}
    config = deepcopy(manager.config)
    config["rooms"][area.id]["scenes"] = [
        linked() | {"conditions": condition, "can_turn_on": True},
        {
            "id": "fallback",
            "name": "Fallback",
            "conditions": condition,
            "can_turn_on": True,
            "lights": {"light.bulb": {"state": "on"}},
        },
    ]
    await manager.async_save_config(config, manager.revision)
    started, finish = asyncio.Event(), asyncio.Event()
    native_calls, lamp_calls = [], []

    async def recall(call):
        native_calls.append(call)
        started.set()
        await finish.wait()
        raise HomeAssistantError("bridge failed after waiting")

    async def lamp(call):
        lamp_calls.append(call)

    hass.services.async_register("scene", "turn_on", recall)
    hass.services.async_register("light", "turn_on", lamp)
    operation = (
        manager.async_set_mode(area.id, "automation", True)
        if initial_action == "enable"
        else manager.async_resume(area.id)
    )
    active = hass.async_create_task(operation)
    await started.wait()
    engine = manager.engines[area.id]
    assert engine._scene_feedback
    disable = hass.async_create_task(
        manager.async_set_mode(area.id, "automation", False)
    )
    await asyncio.sleep(0)
    assert not disable.done()
    assert manager.config["rooms"][area.id]["automation_enabled"]
    assert not engine._scene_feedback
    # Queue another reevaluation behind the engine lock. Merely invalidating
    # the in-flight generation would not prevent this from running a fallback.
    hass.states.async_set("input_boolean.tv", "on", {"sample": 1})
    finish.set()
    await asyncio.gather(active, disable)
    await hass.async_block_till_done()
    assert len(native_calls) == 1
    assert not lamp_calls
    assert not engine._automation_suspensions
    assert not engine._scene_feedback
    assert not manager.config["rooms"][area.id]["automation_enabled"]
    assert engine.status["reason"] == "disabled"
    await hass.config_entries.async_unload(entry.entry_id)


async def test_cancelled_disable_request_releases_temporary_suspension(hass):
    entry, area, manager = await configured(hass)
    engine = manager.engines[area.id]
    await manager.async_set_mode(area.id, "automation", True)
    await manager._config_lock.acquire()
    try:
        pending = hass.async_create_task(
            manager.async_set_mode(area.id, "automation", False)
        )
        await asyncio.sleep(0)
        assert engine._automation_suspensions
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert not engine._automation_suspensions
    finally:
        manager._config_lock.release()
    await hass.async_block_till_done()
    assert manager.config["rooms"][area.id]["automation_enabled"]
    assert engine.status["reason"] != "disabled"
    await hass.config_entries.async_unload(entry.entry_id)


async def test_disable_checks_authorization_and_editor_before_invalidation(hass):
    entry, area, manager = await configured(hass)
    engine = manager.engines[area.id]
    with patch.object(engine, "async_suspend_pending_automation") as invalidate:
        with pytest.raises(Unauthorized):
            await manager.async_set_mode(
                area.id, "automation", False, Context(user_id="nonexistent")
            )
        invalidate.assert_not_called()
        token = await manager.async_begin_edit(area.id, "owner")
        with pytest.raises(HaloError, match="editor"):
            await manager.async_set_mode(area.id, "automation", False)
        invalidate.assert_not_called()
    await manager.async_end_edit(area.id, token, "owner", False)
    await hass.config_entries.async_unload(entry.entry_id)
