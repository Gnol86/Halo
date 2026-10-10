"""Nightlight arbitration with real HA state events and simulated room lamps."""

import asyncio

import pytest
from homeassistant.core import Context
from test_engine import advance, enable, natural_profile, scene
from test_engine import room_engine as room_engine

from custom_components.halo.engine import HaloRoomEngine


async def configured(hass, room_engine, *, sensor=True):
    engine, manager, room, calls = room_engine
    room.update(
        absence_delay=10,
        lux_off_delay=20,
        nightlight={
            "enabled": True,
            "lights": {"light.one": {"state": "on", "brightness_pct": 5}},
        },
        base={
            "light.one": {"state": "on", "brightness_pct": 80},
            "light.two": {"state": "on", "brightness_pct": 90},
        },
    )
    if not sensor:
        room["lux_entity_id"] = None
    manager.config["transitions"] = {
        "turn_on": 1,
        "turn_off": 2,
        "lux_on": 10,
        "natural": 60,
        "scene": 8,
    }
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    await engine.async_reconfigure()
    await enable(hass, engine)
    calls.clear()


async def depart(hass, freezer, room_engine):
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    await advance(hass, freezer, 10)


async def assert_nightlight(hass, engine):
    await hass.async_block_till_done()
    assert hass.states.get("light.one").state == "on"
    assert hass.states.get("light.one").attributes["brightness"] == 13
    assert hass.states.get("light.two").state == "off"
    assert engine.status["reason"] == "nightlight"
    assert engine.lighting_status == {"mode": "nightlight", "scene_id": None}


@pytest.mark.parametrize("sensor", [True, False])
async def test_absence_uses_fixed_nightlight_and_returns_full_ambience(
    hass, freezer, room_engine, sensor
):
    engine, _, _, calls = room_engine
    await configured(hass, room_engine, sensor=sensor)
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    await advance(hass, freezer, 9)
    assert not calls
    await advance(hass, freezer, 1)
    await assert_nightlight(hass, engine)
    assert all(call.data["transition"] == 2 for call in calls)
    assert engine._absence_off_started_at is None
    calls.clear()
    await advance(hass, freezer, 60)
    assert not calls
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert {call.data["entity_id"] for call in calls} == {"light.one", "light.two"}
    assert all(call.data["transition"] == 1 for call in calls)
    assert hass.states.get("light.one").attributes["brightness"] == 204
    assert hass.states.get("light.two").state == "on"
    assert engine.lighting_status["mode"] != "nightlight"


async def test_empty_room_darkening_and_independent_bright_extinction(
    hass, freezer, room_engine
):
    engine, _, _, calls = room_engine
    await configured(hass, room_engine)
    hass.states.async_set("sensor.lux", "200")
    await hass.async_block_till_done()
    await depart(hass, freezer, room_engine)
    assert not engine.is_on
    assert engine._absence_off_started_at is None
    calls.clear()
    hass.states.async_set("sensor.lux", "50")
    await hass.async_block_till_done()
    await assert_nightlight(hass, engine)
    assert len(calls) == 1 and calls[0].data["transition"] == 10
    calls.clear()
    hass.states.async_set("sensor.lux", "110")
    await hass.async_block_till_done()
    await advance(hass, freezer, 30)
    assert not calls
    hass.states.async_set("sensor.lux", "120")
    await hass.async_block_till_done()
    await advance(hass, freezer, 19)
    assert engine.is_on and not calls
    await advance(hass, freezer, 1)
    assert not engine.is_on
    assert len(calls) == 1 and calls[0].data["transition"] == 2
    assert engine.lighting_status["mode"] == "off"


async def test_return_waits_for_darkness_without_using_presence_return_window(
    hass, freezer, room_engine
):
    engine, _, _, calls = room_engine
    await configured(hass, room_engine)
    await depart(hass, freezer, room_engine)
    hass.states.async_set("sensor.lux", "200")
    await hass.async_block_till_done()
    calls.clear()
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert not calls
    assert engine.status["reason"] == "nightlight"
    await advance(hass, freezer, 20)
    assert not engine.is_on
    calls.clear()
    hass.states.async_set("sensor.lux", "50")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert all(call.data["transition"] == 10 for call in calls)
    calls.clear()
    hass.states.async_set("sensor.lux", "55")
    await hass.async_block_till_done()
    assert not calls


@pytest.mark.parametrize("autonomous", [True, False])
async def test_only_autonomous_scene_takes_priority_over_nightlight(
    hass, freezer, room_engine, autonomous
):
    engine, _, room, calls = room_engine
    await configured(hass, room_engine)
    room["scenes"] = [scene(autonomous=autonomous)]
    hass.states.async_set("media_player.tv", "on")
    await engine.async_reconfigure()
    await depart(hass, freezer, room_engine)
    if autonomous:
        assert engine.status["reason"] == "scene"
        assert hass.states.get("light.one").attributes["brightness"] == 51
    else:
        await assert_nightlight(hass, engine)
        calls.clear()
        hass.states.async_set("binary_sensor.presence", "on")
        await hass.async_block_till_done()
        assert engine.status["reason"] == "scene"
        assert calls[0].data["transition"] == 1
        assert hass.states.get("light.one").attributes["brightness"] == 51


async def test_natural_updates_do_not_touch_nightlights_but_resume_fully(
    hass, freezer, room_engine
):
    engine, manager, room, calls = room_engine
    await configured(hass, room_engine)
    manager.config["profiles"]["day"] = natural_profile()
    room["associations"] = [{"profile_id": "day", "lights": room["lights"]}]
    await engine.async_reconfigure()
    await depart(hass, freezer, room_engine)
    calls.clear()
    hass.states.async_set("sun.sun", "above_horizon", {"elevation": 10})
    await hass.async_block_till_done()
    assert not calls
    await assert_nightlight(hass, engine)
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert all(call.data["brightness_pct"] == 100 for call in calls)
    assert all(call.data["transition"] == 1 for call in calls)
    assert engine.lighting_status["mode"] == "natural"


@pytest.mark.parametrize("allow", [True, False])
async def test_manual_pause_uses_nightlight_only_when_off_is_allowed(
    hass, freezer, room_engine, allow
):
    engine, _, room, calls = room_engine
    await configured(hass, room_engine)
    room["allow_off_during_pause"] = allow
    await engine.async_turn_on(Context(user_id="test-user"))
    pause = engine.status["pause_until"]
    calls.clear()
    await depart(hass, freezer, room_engine)
    assert engine.status["pause_until"] == pause
    if allow:
        await assert_nightlight(hass, engine)
        calls.clear()
        hass.states.async_set("binary_sensor.presence", "on")
        await hass.async_block_till_done()
        assert engine.status["pause_until"] == pause
        assert not calls
        # A longer, confirmed absence still ends the manual hold normally.
        hass.states.async_set("binary_sensor.presence", "off")
        await hass.async_block_till_done()
        await advance(hass, freezer, 31)
        hass.states.async_set("binary_sensor.presence", "on")
        await hass.async_block_till_done()
        assert engine.status["pause_until"] is None
        assert hass.states.get("light.two").state == "on"
    else:
        assert not calls
        assert hass.states.get("light.two").state == "on"


async def test_explicit_room_off_blocks_nightlight_across_restart_until_pause_ends(
    hass, freezer, room_engine
):
    engine, manager, _, calls = room_engine
    await configured(hass, room_engine)
    await depart(hass, freezer, room_engine)
    await engine.async_turn_off(Context(user_id="test-user"))
    assert not engine.is_on
    assert manager.runtime_state["living"]["nightlight_blocked"] is True
    await engine.async_stop()
    restored = HaloRoomEngine(hass, manager, "living")
    calls.clear()
    try:
        await restored.async_start()
        await hass.async_block_till_done()
        assert not calls and not restored.is_on
        await advance(hass, freezer, 900)
        await assert_nightlight(hass, restored)
        assert "nightlight_blocked" not in manager.runtime_state["living"]
    finally:
        await restored.async_stop()


@pytest.mark.parametrize("entity_id", ["sensor.lux", "binary_sensor.presence"])
async def test_unavailable_inputs_freeze_nightlight_decisions(
    hass, freezer, room_engine, entity_id
):
    engine, _, _, calls = room_engine
    await configured(hass, room_engine)
    await depart(hass, freezer, room_engine)
    calls.clear()
    hass.states.async_set(entity_id, "unavailable")
    await hass.async_block_till_done()
    await advance(hass, freezer, 60)
    assert not calls
    assert engine.status["reason"] == "unavailable"
    assert engine.is_on
    hass.states.async_set(entity_id, "50" if entity_id == "sensor.lux" else "off")
    await hass.async_block_till_done()
    await advance(hass, freezer, 10)
    await assert_nightlight(hass, engine)


async def test_edit_and_disabled_automation_suspend_nightlight(
    hass, freezer, room_engine
):
    engine, _, _, calls = room_engine
    await configured(hass, room_engine)
    token = await engine.async_begin_edit("owner")
    await depart(hass, freezer, room_engine)
    assert not calls and engine.status["reason"] == "editing"
    await engine.async_end_edit(token, False)
    await engine.async_set_mode("automation", False)
    calls.clear()
    await advance(hass, freezer, 30)
    assert not calls
    await engine.async_set_mode("automation", True)
    await assert_nightlight(hass, engine)


async def test_presence_return_interrupts_pending_nightlight_sequence(
    hass, freezer, room_engine
):
    engine, _, _, calls = room_engine
    await configured(hass, room_engine)
    pending, release = asyncio.Event(), asyncio.Event()

    async def delayed(call):
        calls.append(call)
        if call.data.get("brightness_pct") == 5:
            pending.set()
            await release.wait()
        state = hass.states.get(call.data["entity_id"])
        attrs = dict(state.attributes)
        if "brightness_pct" in call.data:
            attrs["brightness"] = round(call.data["brightness_pct"] * 255 / 100)
        hass.states.async_set(state.entity_id, "on", attrs, context=call.context)

    hass.services.async_register("light", "turn_on", delayed)
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    advance_task = asyncio.create_task(advance(hass, freezer, 10))
    await pending.wait()
    hass.states.async_set("binary_sensor.presence", "on")
    await asyncio.sleep(0)
    release.set()
    await advance_task
    await hass.async_block_till_done()
    assert not any(call.service == "turn_off" for call in calls)
    assert [call.data.get("brightness_pct") for call in calls] == [5, 80, 90]
    assert calls[-1].data["transition"] == 1
    assert engine.status["pause_until"] is None


async def test_manual_command_interrupts_pending_nightlight_sequence(
    hass, freezer, room_engine
):
    engine, _, _, calls = room_engine
    await configured(hass, room_engine)
    pending, release = asyncio.Event(), asyncio.Event()

    async def delayed(call):
        calls.append(call)
        pending.set()
        await release.wait()
        state = hass.states.get(call.data["entity_id"])
        hass.states.async_set(
            state.entity_id, "on", state.attributes, context=call.context
        )

    hass.services.async_register("light", "turn_on", delayed)
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    advance_task = asyncio.create_task(advance(hass, freezer, 10))
    await pending.wait()
    off_task = asyncio.create_task(engine.async_turn_off())
    await asyncio.sleep(0)
    release.set()
    await advance_task
    await off_task
    await hass.async_block_till_done()
    assert not engine.is_on
    calls.clear()
    await advance(hass, freezer, 30)
    assert not calls


async def test_nightlight_recovers_fixed_targets_after_restart(
    hass, freezer, room_engine
):
    engine, manager, _, calls = room_engine
    await configured(hass, room_engine)
    await depart(hass, freezer, room_engine)
    await engine.async_stop()
    restored = HaloRoomEngine(hass, manager, "living")
    try:
        await restored.async_start()
        await assert_nightlight(hass, restored)
        calls.clear()
        await advance(hass, freezer, 60)
        assert not calls
    finally:
        await restored.async_stop()


async def test_one_lamp_room_restores_normal_brightness(hass, freezer, room_engine):
    engine, _, room, calls = room_engine
    room["lights"] = ["light.one"]
    await configured(hass, room_engine)
    await depart(hass, freezer, room_engine)
    assert engine.lighting_status["mode"] == "nightlight"
    calls.clear()
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["brightness_pct"] == 80
    assert calls[0].data["transition"] == 1


async def test_known_group_composition_drift_never_commands_conflicting_targets(
    hass, freezer, room_engine
):
    engine, _, room, calls = room_engine
    await configured(hass, room_engine)
    state = hass.states.get("light.two")
    hass.states.async_set(
        "light.two", state.state, {**state.attributes, "entity_id": ["light.one"]}
    )
    await hass.async_block_till_done()
    await depart(hass, freezer, room_engine)
    assert not calls
    assert engine.status["error"] == "nightlight_group_conflict"
    assert engine.status["reason"] == "unavailable"


async def test_fixed_native_color_and_effect_survive_nightlight_application(
    hass, freezer, room_engine
):
    from homeassistant.components.light import LightEntityFeature

    engine, _, room, calls = room_engine
    await configured(hass, room_engine)
    attributes = {
        "supported_color_modes": ["rgbw"],
        "color_mode": "rgbw",
        "rgbw_color": [255, 0, 0, 0],
        "brightness": 204,
        "supported_features": LightEntityFeature.TRANSITION | LightEntityFeature.EFFECT,
        "effect_list": ["Candle"],
    }
    hass.states.async_set("light.one", "on", attributes)
    await hass.async_block_till_done()
    await engine.async_resume()
    room["nightlight"]["lights"]["light.one"] = {
        "state": "on",
        "brightness_pct": 5,
        "rgbw_color": [1, 2, 3, 4],
        "effect": "Candle",
    }
    calls.clear()
    await depart(hass, freezer, room_engine)
    first = next(call for call in calls if call.data["entity_id"] == "light.one")
    assert first.data["rgbw_color"] == [1, 2, 3, 4]
    assert first.data["effect"] == "Candle"
    assert first.data["brightness_pct"] == 5
    assert first.data["transition"] == 2


async def test_missing_lux_never_starts_nightlight(hass, freezer, room_engine):
    engine, _, _, calls = room_engine
    await configured(hass, room_engine)
    hass.states.async_set("sensor.lux", "unknown")
    await hass.async_block_till_done()
    await depart(hass, freezer, room_engine)
    assert not calls
    assert engine.status["reason"] == "unavailable"
    hass.states.async_set("sensor.lux", "50")
    await hass.async_block_till_done()
    await assert_nightlight(hass, engine)


async def test_reconfiguration_updates_only_fixed_nightlight_targets(
    hass, freezer, room_engine
):
    engine, _, room, calls = room_engine
    await configured(hass, room_engine)
    await depart(hass, freezer, room_engine)
    room["nightlight"]["lights"]["light.one"]["brightness_pct"] = 7
    calls.clear()
    await engine.async_reconfigure()
    assert len(calls) == 1
    assert calls[0].data["brightness_pct"] == 7
    assert hass.states.get("light.two").state == "off"
    assert engine.lighting_status["mode"] == "nightlight"


async def test_physical_whole_room_off_blocks_absence_nightlight(
    hass, freezer, room_engine
):
    engine, _, _, calls = room_engine
    await configured(hass, room_engine)
    for entity_id in ("light.one", "light.two"):
        state = hass.states.get(entity_id)
        hass.states.async_set(
            entity_id, "off", state.attributes, context=Context(user_id="user")
        )
    await hass.async_block_till_done()
    calls.clear()
    await depart(hass, freezer, room_engine)
    assert not calls
    assert not engine.is_on
    assert engine._runtime["nightlight_blocked"] is True
    await engine.async_resume()
    await assert_nightlight(hass, engine)


async def test_nightlight_restores_unavailable_lamp_when_it_recovers(
    hass, freezer, room_engine
):
    engine, _, _, calls = room_engine
    await configured(hass, room_engine)
    await depart(hass, freezer, room_engine)
    attributes = dict(hass.states.get("light.one").attributes)
    hass.states.async_set("light.one", "unavailable", attributes)
    await hass.async_block_till_done()
    calls.clear()
    hass.states.async_set("light.one", "off", attributes)
    await hass.async_block_till_done()
    await assert_nightlight(hass, engine)
    assert len(calls) == 1
    assert calls[0].data["brightness_pct"] == 5


async def test_custom_presence_states_control_nightlight(hass, freezer, room_engine):
    engine, _, room, calls = room_engine
    await configured(hass, room_engine)
    room["presence_states"] = ["occupied"]
    hass.states.async_set("binary_sensor.presence", "occupied")
    await engine.async_reconfigure()
    calls.clear()
    hass.states.async_set("binary_sensor.presence", "empty")
    await hass.async_block_till_done()
    await advance(hass, freezer, 10)
    await assert_nightlight(hass, engine)
    calls.clear()
    hass.states.async_set("binary_sensor.presence", "occupied")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert all(call.data["transition"] == 1 for call in calls)
