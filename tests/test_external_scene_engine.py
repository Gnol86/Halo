"""Linked scenes recall native providers without copying their lamp targets."""

import asyncio
from contextlib import nullcontext
from datetime import timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.core import Context, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from test_engine import advance, enable, scene
from test_engine import room_engine as room_engine


def linked_scene(scene_id="native", *, autonomous=True):
    return {
        "id": scene_id,
        "name": "Movie night",
        "type": "home_assistant",
        "scene_entity_id": f"scene.{scene_id}",
        "can_turn_on": autonomous,
        "conditions": {
            "type": "state",
            "entity_id": "media_player.tv",
            "state": "on",
        },
    }


@pytest.fixture
async def linked_engine(hass, room_engine):
    engine, manager, room, light_calls = room_engine
    room["scenes"] = [linked_scene()]
    native_calls = []
    hass.states.async_set("scene.native", "unknown", {"entity_id": ["light.one"]})
    hass.states.async_set("media_player.tv", "off")

    def scene_problem(item):
        source = hass.states.get(item["scene_entity_id"])
        if source is None or source.state == "unavailable":
            return "external_scene_unavailable"
        return None

    manager.scene_problem = Mock(side_effect=scene_problem)
    manager.scene_feedback_lights = Mock(return_value={"light.one"})
    manager.external_scene_context = Mock(side_effect=lambda _context: nullcontext())
    manager.async_authorize_scene = AsyncMock()

    async def recall(call):
        native_calls.append(call)
        attributes = dict(hass.states.get("light.one").attributes)
        attributes.update(brightness=31, effect="candle")
        hass.states.async_set("light.one", "on", attributes, context=call.context)
        # Native scenes can legitimately change lamps outside this Halo room.
        hass.states.async_set("light.outside", "on", context=call.context)
        hass.states.async_set(
            call.data["entity_id"],
            dt_util.utcnow().isoformat(),
            {"entity_id": ["light.one", "light.outside"]},
            context=call.context,
        )

    hass.services.async_register("scene", "turn_on", recall)
    await engine.async_reconfigure()
    await hass.async_block_till_done()
    return engine, manager, room, light_calls, native_calls


async def activate_condition(hass, engine):
    hass.states.async_set("media_player.tv", "on")
    await hass.async_block_till_done()
    await enable(hass, engine)


async def test_native_unknown_scene_full_recall_and_partial_lamps(hass, linked_engine):
    engine, manager, _, light_calls, calls = linked_engine
    await activate_condition(hass, engine)
    assert len(calls) == 1
    assert calls[0].data == {"entity_id": "scene.native"}
    assert not light_calls
    assert hass.states.get("light.one").attributes["effect"] == "candle"
    assert hass.states.get("light.outside").state == "on"
    assert hass.states.get("light.two").state == "off"
    assert not engine.status["pause_until"]
    assert engine.lighting_status == {"mode": "scene", "scene_id": "native"}
    manager.external_scene_context.assert_called_once_with(calls[0].context)


@pytest.mark.parametrize(
    "duration,expected", [(None, None), (0, 0), (12, 12), (604800, 6553)]
)
async def test_native_scene_transition_omission_zero_and_limit(
    hass, linked_engine, duration, expected
):
    engine, manager, _, _, calls = linked_engine
    manager.config["transitions"] = {"scene": duration}
    await activate_condition(hass, engine)
    assert calls[-1].data.get("transition") == expected
    assert ("transition" in calls[-1].data) is (expected is not None)


@pytest.mark.parametrize("trigger,duration", [("presence", 2), ("lux", 8)])
async def test_native_scene_uses_trigger_category(
    hass, linked_engine, trigger, duration
):
    engine, manager, room, _, calls = linked_engine
    room["scenes"][0]["can_turn_on"] = False
    manager.config["transitions"] = {"turn_on": 2, "lux_on": 8, "scene": 12}
    hass.states.async_set("sensor.lux", "200")
    hass.states.async_set(
        "binary_sensor.presence", "off" if trigger == "presence" else "on"
    )
    await activate_condition(hass, engine)
    assert not calls
    if trigger == "presence":
        hass.states.async_set("sensor.lux", "50")
        await hass.async_block_till_done()
        hass.states.async_set("binary_sensor.presence", "on")
    else:
        hass.states.async_set("sensor.lux", "50")
    await hass.async_block_till_done()
    assert calls[-1].data["transition"] == duration


async def test_no_recall_from_ticks_or_native_activation_timestamp(
    hass, freezer, linked_engine
):
    engine, _, _, _, calls = linked_engine
    await activate_condition(hass, engine)
    await advance(hass, freezer, 60)
    hass.states.async_set("scene.native", "2026-10-10T13:00:00+00:00")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_unavailable_falls_through_and_recovery_restores_priority(
    hass, linked_engine
):
    engine, _, room, light_calls, calls = linked_engine
    room["scenes"].append(scene("fallback", autonomous=True))
    hass.states.async_set("scene.native", "unavailable")
    await engine.async_reconfigure()
    await activate_condition(hass, engine)
    assert not calls
    assert light_calls
    assert engine.status["scene_id"] == "fallback"
    assert engine.status["scene_errors"] == {"native": "external_scene_unavailable"}
    hass.states.async_set("scene.native", "unknown")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert engine.status["scene_id"] == "native"
    assert engine.status["scene_errors"] == {}


async def test_removed_source_returns_to_base_without_restoring_outside(
    hass, linked_engine
):
    engine, _, _, light_calls, _ = linked_engine
    await activate_condition(hass, engine)
    hass.states.async_remove("scene.native")
    await hass.async_block_till_done()
    assert engine.status["scene_id"] is None
    assert light_calls
    assert all(call.data["entity_id"] != "light.outside" for call in light_calls)
    assert hass.states.get("light.outside").state == "on"


@pytest.mark.parametrize("error_type", [HomeAssistantError, RuntimeError])
async def test_failed_scene_falls_through_without_tick_or_timestamp_retry(
    hass, freezer, linked_engine, error_type
):
    engine, _, room, light_calls, calls = linked_engine
    room["scenes"].append(scene("fallback", autonomous=True))

    async def fail(call):
        calls.append(call)
        raise error_type("bridge unavailable")

    hass.services.async_register("scene", "turn_on", fail)
    await activate_condition(hass, engine)
    assert len(calls) == 1
    assert light_calls
    assert engine.status["scene_id"] == "fallback"
    assert engine.status["scene_errors"] == {"native": "external_scene_failed"}
    await advance(hass, freezer, 60)
    hass.states.async_set("scene.native", "2026-10-10T13:00:00+00:00")
    await hass.async_block_till_done()
    assert len(calls) == 1
    hass.states.async_set("media_player.tv", "off")
    await hass.async_block_till_done()
    hass.states.async_set("media_player.tv", "on")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert not engine._scene_feedback


async def test_explicit_native_scene_preserves_context_and_name_with_automation_off(
    hass, linked_engine
):
    engine, manager, _, _, calls = linked_engine
    context = Context(user_id="user")
    await engine.async_activate_scene("native", context)
    await hass.async_block_till_done()
    assert calls[0].context.user_id == "user"
    assert calls[0].context.parent_id == context.id
    manager.async_authorize_scene.assert_awaited_once()
    assert engine.status["pause_until"]
    assert engine.lighting_status == {"mode": "scene", "scene_id": "native"}


async def test_explicit_native_scene_failure_does_not_claim_active_scene(
    hass, linked_engine
):
    engine, _, _, _, _ = linked_engine

    async def fail(_call):
        raise HomeAssistantError("cannot recall")

    hass.services.async_register("scene", "turn_on", fail)
    with pytest.raises(HomeAssistantError, match="cannot recall"):
        await engine.async_activate_scene("native")
    assert not engine._runtime.get("manual_scene_id")
    assert not engine._scene_feedback
    assert engine.status["error"] == "cannot recall"


@pytest.mark.parametrize("action", ["scene", "turn_on"])
async def test_explicit_authorization_failure_precedes_pause(
    hass, linked_engine, action
):
    engine, manager, _, _, calls = linked_engine
    hass.states.async_set("media_player.tv", "on")
    await hass.async_block_till_done()
    manager.async_authorize_scene.side_effect = HomeAssistantError("forbidden")
    with pytest.raises(HomeAssistantError, match="forbidden"):
        if action == "scene":
            await engine.async_activate_scene("native", Context(user_id="reader"))
        else:
            await engine.async_turn_on(Context(user_id="reader"))
    assert not calls
    assert not engine.status["pause_until"]


async def test_opaque_feedback_tolerated_only_during_effective_transition(
    hass, freezer, linked_engine
):
    engine, manager, _, _, _ = linked_engine
    manager.config["transitions"] = {"scene": 10}
    await activate_condition(hass, engine)
    await advance(hass, freezer, 14)
    hass.states.async_set("light.one", "on", {"brightness": 100})
    await hass.async_block_till_done()
    assert not engine.status["pause_until"]
    await advance(hass, freezer, 1)
    hass.states.async_set("light.one", "on", {"brightness": 101})
    await hass.async_block_till_done()
    assert engine.status["pause_until"]


@pytest.mark.parametrize(
    "context", [Context(user_id="user"), Context(parent_id="foreign_automation")]
)
async def test_identified_intervention_has_priority_over_feedback_tolerance(
    hass, linked_engine, context
):
    engine, _, _, _, _ = linked_engine
    await activate_condition(hass, engine)
    hass.states.async_set("light.one", "on", {"brightness": 200}, context=context)
    await hass.async_block_till_done()
    assert engine.status["pause_until"]
    assert not engine._scene_feedback


async def test_unaffected_room_lamp_does_not_receive_feedback_tolerance(
    hass, linked_engine
):
    engine, _, _, _, _ = linked_engine
    await activate_condition(hass, engine)
    hass.states.async_set("light.two", "on")
    await hass.async_block_till_done()
    assert engine.status["pause_until"]


@pytest.mark.parametrize(
    "action", ["disable", "edit", "reconfigure", "stop", "manual_off"]
)
async def test_tolerance_cancelled_at_control_boundaries(hass, linked_engine, action):
    engine, _, _, _, _ = linked_engine
    await engine.async_activate_scene("native")
    assert engine._scene_feedback
    if action == "disable":
        await engine.async_set_mode("automation", False)
    elif action == "edit":
        await engine.async_begin_edit("admin")
    elif action == "reconfigure":
        await engine.async_reconfigure()
    elif action == "stop":
        await engine.async_stop()
    else:
        await engine.async_turn_off()
    assert not engine._scene_feedback


async def test_manual_command_queued_during_native_recall_wins(hass, linked_engine):
    engine, _, _, _, calls = linked_engine
    started, finish = asyncio.Event(), asyncio.Event()

    async def slow_recall(call):
        calls.append(call)
        started.set()
        await finish.wait()
        hass.states.async_set("light.one", "on", context=call.context)

    hass.services.async_register("scene", "turn_on", slow_recall)
    task = hass.async_create_task(engine.async_activate_scene("native"))
    await started.wait()
    manual = hass.async_create_task(engine.async_turn_off(Context(user_id="user")))
    await asyncio.sleep(0)
    finish.set()
    await asyncio.gather(task, manual)
    await hass.async_block_till_done()
    assert not engine.is_on
    assert not engine._runtime.get("manual_scene_id")
    assert len(calls) == 1


async def test_own_context_recognized_even_after_fallback_tolerance_expires(
    hass, freezer, linked_engine
):
    engine, _, _, _, calls = linked_engine
    await activate_condition(hass, engine)
    freezer.move_to(dt_util.utcnow() + timedelta(seconds=6))
    old = hass.states.get("light.one")
    assert engine._own_change(
        "light.one",
        old,
        State("light.one", "on", {"brightness": 180}, context=calls[0].context),
    )


async def test_unknown_composition_tolerates_contextless_provider_feedback(
    hass, linked_engine
):
    engine, manager, _, _, calls = linked_engine
    manager.scene_feedback_lights.return_value = {"light.one", "light.two"}
    hass.states.async_set("scene.native", "unknown")

    async def opaque_recall(call):
        calls.append(call)
        for entity_id in ("light.one", "light.two"):
            hass.states.async_set(entity_id, "on", {"brightness": 180})
        await hass.async_block_till_done()

    hass.services.async_register("scene", "turn_on", opaque_recall)
    await activate_condition(hass, engine)
    assert len(calls) == 1
    assert not engine.status["pause_until"]
    assert engine.lighting_status == {"mode": "scene", "scene_id": "native"}


async def test_all_room_lamps_unavailable_does_not_block_native_scene_recall(
    hass, linked_engine
):
    engine, _, _, _, calls = linked_engine
    for entity_id in ("light.one", "light.two"):
        hass.states.async_set(entity_id, "unavailable")
    await hass.async_block_till_done()
    await activate_condition(hass, engine)
    assert len(calls) == 1


async def test_presence_return_recalls_native_scene_once_with_turn_on(
    hass, linked_engine
):
    engine, manager, room, _, calls = linked_engine
    room["scenes"][0]["can_turn_on"] = False
    room["absence_delay"] = 0
    manager.config["transitions"] = {"turn_on": 0, "scene": 10, "lux_on": 60}
    hass.states.async_set("binary_sensor.presence", "on")
    await activate_condition(hass, engine)
    hass.states.async_set("sensor.lux", "200")
    await hass.async_block_till_done()
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    assert not engine.is_on
    calls.clear()
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["transition"] == 0
    assert not engine.status["dark"]
    hass.states.async_set("sensor.lux", "50")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_editor_and_disabled_automation_prevent_conditional_native_recall(
    hass, linked_engine
):
    engine, _, _, _, calls = linked_engine
    hass.states.async_set("media_player.tv", "on")
    await hass.async_block_till_done()
    assert not calls
    await engine.async_begin_edit("admin")
    with pytest.raises(ValueError, match="room_being_edited"):
        await enable(hass, engine)
    assert not calls
    assert engine.status["editing"]


async def test_new_manual_scene_listener_refresh_emits_no_commands(hass, linked_engine):
    engine, manager, room, light_calls, calls = linked_engine
    added = linked_scene("added")
    added["conditions"] = None
    room["scenes"].append(added)
    hass.states.async_set("scene.added", "unknown")
    engine.async_refresh_listeners()
    manager.async_notify.reset_mock()
    hass.states.async_set("scene.added", "unavailable")
    await hass.async_block_till_done()
    manager.async_notify.assert_called()
    assert not calls
    assert not light_calls


async def test_manual_intervention_cancels_fallback_after_failed_inflight_call(
    hass, linked_engine
):
    engine, _, room, light_calls, calls = linked_engine
    room["scenes"].append(scene("fallback", autonomous=True))
    started, finish = asyncio.Event(), asyncio.Event()

    async def slow_failure(call):
        calls.append(call)
        started.set()
        await finish.wait()
        raise HomeAssistantError("failed")

    hass.services.async_register("scene", "turn_on", slow_failure)
    hass.states.async_set("media_player.tv", "on")
    await hass.async_block_till_done()
    task = hass.async_create_task(engine.async_set_mode("automation", True))
    await started.wait()
    manual = hass.async_create_task(engine.async_turn_off(Context(user_id="user")))
    await asyncio.sleep(0)
    finish.set()
    await asyncio.gather(task, manual)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert not any(call.service == "turn_on" for call in light_calls)
    assert not engine.is_on


async def test_native_scene_that_leaves_room_off_is_not_replayed_on_sensor_updates(
    hass, linked_engine
):
    engine, _, room, _, calls = linked_engine
    room["scenes"][0]["can_turn_on"] = False

    async def outside_only(call):
        calls.append(call)
        hass.states.async_set("light.outside", "on", context=call.context)

    hass.services.async_register("scene", "turn_on", outside_only)
    hass.states.async_set("binary_sensor.presence", "on")
    await activate_condition(hass, engine)
    assert len(calls) == 1
    assert not engine.is_on
    hass.states.async_set("sensor.lux", "40")
    hass.states.async_set("binary_sensor.presence", "on", {"battery": 75})
    await hass.async_block_till_done()
    assert len(calls) == 1
