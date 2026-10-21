"""Identified intent pauses a room; device feedback never creates an intent."""

import asyncio
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.core import Context
from homeassistant.util import dt as dt_util
from test_engine import advance, enable, natural_profile, scene
from test_engine import room_engine as room_engine

from custom_components.halo.engine import HaloRoomEngine


async def identified(hass, room_engine, *, duration=1800):
    engine, _, room, calls = room_engine
    room["manual_control"] = {"mode": "identified", "duration": duration, "inputs": []}
    hass.states.async_set("binary_sensor.presence", "on")
    await engine.async_reconfigure()
    await enable(hass, engine)
    calls.clear()


async def test_disabled_default_keeps_explicit_commands_punctual(
    hass, hass_admin_user, room_engine
):
    engine, _, _, _ = room_engine
    await enable(hass, engine)
    await engine.async_turn_on(Context(user_id=hass_admin_user.id))
    assert engine.status["manual_hold"] is None


@pytest.mark.parametrize("command", ["turn_on", "turn_off", "scene"])
async def test_direct_halo_command_holds_room(
    hass, hass_admin_user, room_engine, command
):
    engine, _, room, calls = room_engine
    await identified(hass, room_engine)
    context = Context(user_id=hass_admin_user.id)
    if command == "scene":
        room["scenes"] = [scene()]
        await engine.async_activate_scene("cinema", context)
    else:
        await getattr(engine, f"async_{command}")(context)
    await hass.async_block_till_done()
    hold = engine.status["manual_hold"]
    assert hold["source"] == "halo"
    assert hold["command"] == ("scene:cinema" if command == "scene" else command)
    assert engine.status["reason"] == "manual_hold"
    assert "context_id" not in hold
    calls.clear()
    hass.states.async_set("sun.sun", "above_horizon", {"elevation": 7})
    await hass.async_block_till_done()
    assert not calls
    assert engine.status["manual_hold"] == hold


async def test_service_without_state_change_still_holds(
    hass, hass_admin_user, room_engine
):
    engine, _, _, calls = room_engine
    await identified(hass, room_engine)
    state = hass.states.get("light.one")
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.one"},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )
    await hass.async_block_till_done()
    assert hass.states.get("light.one").state == state.state
    assert engine.status["manual_hold"]["source"] == "user"
    assert len(calls) == 1


@pytest.mark.parametrize("parent,user", [(None, False), ("script", True)])
async def test_automation_does_not_hold_but_explicit_action_can(
    hass, hass_admin_user, room_engine, parent, user
):
    engine, _, _, _ = room_engine
    await identified(hass, room_engine)
    context = Context(parent_id=parent, user_id=hass_admin_user.id if user else None)
    await engine.async_turn_off(context)
    await hass.async_block_till_done()
    assert engine.status["manual_hold"] is None
    await engine.async_manual_hold(context)
    assert engine.status["manual_hold"]["source"] == "automation"


async def test_historical_feedback_and_reused_user_context_never_pause(
    hass, freezer, hass_admin_user, room_engine
):
    engine, _, _, _ = room_engine
    await identified(hass, room_engine)
    for elapsed, power, attrs in [
        (0, "off", {"brightness": None}),
        (0, "on", {"brightness": 92}),
        (7.26, "on", {"brightness": 66}),
        (0, "on", {"brightness": 92}),
        (8.357, "off", {}),
        (148, "on", {"brightness": 127}),
        (0, "off", {"is_hue_group": True, "xy_color": (0.5, 0.4)}),
    ]:
        freezer.move_to(dt_util.utcnow() + timedelta(seconds=elapsed))
        hass.states.async_set(
            "light.one", power, attrs, context=Context(user_id=hass_admin_user.id)
        )
        await hass.async_block_till_done()
        assert engine.status["manual_hold"] is None


async def test_feedback_does_not_renew_and_new_command_does(
    hass, freezer, hass_admin_user, room_engine
):
    engine, _, _, _ = room_engine
    await identified(hass, room_engine)
    context = Context(user_id=hass_admin_user.id)
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": "light.one"},
        blocking=True,
        context=context,
    )
    await hass.async_block_till_done()
    until = engine.status["manual_hold"]["until"]
    await advance(hass, freezer, 20)
    for brightness in (92, 66, 92):
        hass.states.async_set(
            "light.one", "on", {"brightness": brightness}, context=context
        )
    await hass.async_block_till_done()
    assert engine.status["manual_hold"]["until"] == until
    await engine.async_turn_off(Context(user_id=hass_admin_user.id))
    assert engine.status["manual_hold"]["until"] > until


@pytest.mark.parametrize("release", ["expiry", "resume", "disable_detection"])
async def test_resume_reevaluates_once(hass, freezer, room_engine, release):
    engine, _, room, calls = room_engine
    await identified(hass, room_engine, duration=60)
    await engine.async_manual_hold()
    await engine.async_turn_off()
    calls.clear()
    if release == "expiry":
        await advance(hass, freezer, 60)
    elif release == "resume":
        await engine.async_manual_resume()
    else:
        room["manual_control"]["mode"] = "disabled"
        await engine.async_reconfigure()
    await hass.async_block_till_done()
    assert engine.status["manual_hold"] is None
    assert engine.is_on
    assert len(calls) == 2
    calls.clear()
    await engine._async_wakeup("tick")
    assert not calls


async def test_natural_scenes_and_nightlight_are_blocked_by_hold(hass, room_engine):
    engine, manager, room, calls = room_engine
    await identified(hass, room_engine)
    manager.config["profiles"]["day"] = natural_profile()
    room["associations"] = [{"profile_id": "day", "lights": room["lights"]}]
    room["scenes"] = [scene(autonomous=True)]
    room["nightlight"] = {"enabled": True, "lights": {"light.one": {"state": "on"}}}
    await engine.async_reconfigure()
    await engine.async_manual_hold()
    calls.clear()
    hass.states.async_set("media_player.tv", "on")
    hass.states.async_set("sun.sun", "above_horizon", {"elevation": 9})
    await hass.async_block_till_done()
    assert not calls
    assert engine.lighting_status == {"mode": "manual", "scene_id": None}


async def test_preexisting_absence_does_not_release_hold_or_relight_nightlight(
    hass, freezer, hass_admin_user, room_engine
):
    engine, _, room, calls = room_engine
    await identified(hass, room_engine)
    room["absence_delay"] = 0
    room["nightlight"] = {
        "enabled": True,
        "lights": {"light.one": {"state": "on", "brightness_pct": 10}},
    }
    await engine.async_reconfigure()
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    await advance(hass, freezer, 40)
    await engine.async_turn_off(Context(user_id=hass_admin_user.id))
    calls.clear()
    await advance(hass, freezer, 60)
    assert engine.status["manual_hold"]
    assert not engine.is_on
    assert not calls
    await engine.async_manual_resume()
    assert engine.status["manual_hold"] is None
    assert engine.lighting_status["mode"] == "nightlight"


async def test_new_absence_waits_for_delay_and_dropout_protection(
    hass, freezer, room_engine
):
    engine, manager, room, _ = room_engine
    await identified(hass, room_engine)
    room["absence_delay"] = 10
    manager.config["presence_return_window"] = 30
    await engine.async_manual_hold()
    await advance(hass, freezer, 1)
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    await advance(hass, freezer, 20)
    assert engine.status["manual_hold"]
    hass.states.async_set("binary_sensor.presence", "unavailable")
    await hass.async_block_till_done()
    await advance(hass, freezer, 30)
    assert engine.status["manual_hold"]
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    await advance(hass, freezer, 29)
    assert engine.status["manual_hold"]
    await advance(hass, freezer, 1)
    assert engine.status["manual_hold"] is None


async def test_allowed_extinction_works_during_hold(hass, freezer, room_engine):
    engine, _, room, _ = room_engine
    await identified(hass, room_engine)
    room["lux_off"] = True
    room["lux_off_delay"] = 1
    await engine.async_manual_hold()
    hass.states.async_set("sensor.lux", "200")
    await hass.async_block_till_done()
    await advance(hass, freezer, 1)
    assert not engine.is_on
    assert engine.status["manual_hold"]


async def test_editing_stays_distinct_and_expiry_cannot_override_editor(
    hass, freezer, hass_admin_user, room_engine
):
    engine, _, _, calls = room_engine
    await identified(hass, room_engine, duration=30)
    await engine.async_manual_hold()
    token = await engine.async_begin_edit("owner")
    await engine.async_preview(token, {"light.one": {"state": "on", "brightness": 88}})
    calls.clear()
    with pytest.raises(ValueError, match="room_being_edited"):
        await engine.async_manual_resume()
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": "light.two"},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    calls.clear()
    await advance(hass, freezer, 31)
    assert engine.status["editing"]
    assert engine.status["reason"] == "editing"
    assert engine.status["manual_hold"] is None
    assert not calls
    await engine.async_end_edit(token, False)


async def test_restart_preserves_deadline_and_disable_clears_hold(
    hass, freezer, room_engine
):
    engine, manager, room, _ = room_engine
    await identified(hass, room_engine, duration=120)
    await engine.async_manual_hold()
    hold = deepcopy(manager.runtime_state["living"]["identified_hold"])
    await engine.async_stop()
    await advance(hass, freezer, 30)
    restored = HaloRoomEngine(hass, manager, "living")
    try:
        await restored.async_start()
        assert manager.runtime_state["living"]["identified_hold"] == hold
        assert restored.status["manual_hold"]
        await restored.async_set_mode("automation", False)
        assert "identified_hold" not in manager.runtime_state["living"]
        assert restored.status["reason"] == "disabled"
        await restored.async_set_mode("automation", True)
        assert restored.status["manual_hold"] is None
    finally:
        await restored.async_stop()


async def test_external_intent_interrupts_slow_service_before_next_lamp(
    hass, hass_admin_user, room_engine
):
    engine, _, _, calls = room_engine
    await identified(hass, room_engine)
    started, finish = asyncio.Event(), asyncio.Event()

    async def slow(call):
        calls.append(call)
        started.set()
        await finish.wait()

    hass.services.async_register("light", "turn_on", slow)
    task = hass.async_create_task(engine._async_wakeup("refresh"))
    await started.wait()
    try:
        await hass.services.async_call(
            "light",
            "turn_off",
            {"entity_id": "light.one"},
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
        # Let the event listener authorize the user, without waiting for the
        # room lock held by the deliberately blocked service.
        for _ in range(20):
            if engine.status["manual_hold"]:
                break
            await asyncio.sleep(0)
        assert engine.status["manual_hold"]
    finally:
        finish.set()
        await task
    await hass.async_block_till_done()
    assert not any(call.data["entity_id"] == "light.two" for call in calls)
    assert engine.status["reason"] == "manual_hold"


@pytest.mark.parametrize("newer_intent", ["resume", "edit", "direct"])
async def test_pending_authorization_cannot_override_newer_intent(
    hass, hass_admin_user, room_engine, newer_intent
):
    engine, _, _, _ = room_engine
    await identified(hass, room_engine)
    await engine.async_manual_hold()
    started, finish = asyncio.Event(), asyncio.Event()

    async def delayed_user(_user_id):
        started.set()
        await finish.wait()
        return hass_admin_user

    token = None
    with patch.object(type(hass.auth), "async_get_user", side_effect=delayed_user):
        await hass.services.async_call(
            "light",
            "turn_off",
            {"entity_id": "light.one"},
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
        await started.wait()
        if newer_intent == "resume":
            await engine.async_manual_resume()
        elif newer_intent == "edit":
            token = await engine.async_begin_edit("owner")
            await engine.async_end_edit(token, False)
            token = None
        else:
            await engine.async_turn_off(Context(user_id=hass_admin_user.id))
        expected = deepcopy(engine.status["manual_hold"])
        finish.set()
        await hass.async_block_till_done()
    assert engine.status["manual_hold"] == expected
    if token:
        await engine.async_end_edit(token, False)
