"""Room behavior tests using HA events/services and simulated physical lamps."""

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.components.light import LightEntityFeature
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.halo.engine import HaloRoomEngine
from custom_components.halo.scene_import import normalize_scene_import


@pytest.fixture
async def room_engine(hass: HomeAssistant):
    """Keep realistic state feedback while never touching real hardware."""
    room = {
        "id": "living",
        "lights": ["light.one", "light.two"],
        "presence_entity_id": "binary_sensor.presence",
        "presence_states": ["on"],
        "lux_entity_id": "sensor.lux",
        "lux_threshold": 100,
        "lux_hysteresis": 20,
        "lux_off": False,
        "absence_delay": 120,
        "manual_pause": 900,
        "lux_off_delay": 30,
        "allow_off_during_pause": True,
        "automation_enabled": False,
        "natural_enabled": True,
        "base": {},
        "associations": [],
        "scenes": [],
        "transitions": {},
    }
    manager = SimpleNamespace(
        config={
            "rooms": {"living": room},
            "profiles": {},
            "transitions": {},
            "sun_entity_id": "sun.sun",
        },
        runtime_state={},
        async_notify=Mock(),
        async_persist_runtime=AsyncMock(),
    )
    attributes = {
        "supported_color_modes": ["color_temp"],
        "supported_features": LightEntityFeature.TRANSITION,
        "brightness": 128,
        "color_temp_kelvin": 3000,
        "color_mode": "color_temp",
        "min_color_temp_kelvin": 2000,
        "max_color_temp_kelvin": 6500,
    }
    for entity_id in room["lights"]:
        hass.states.async_set(entity_id, "off", attributes)
    hass.states.async_set("binary_sensor.presence", "off")
    hass.states.async_set("sensor.lux", "50")
    hass.states.async_set("sun.sun", "above_horizon", {"elevation": 5, "rising": True})
    calls = []

    async def light_service(call):
        calls.append(call)
        old = hass.states.get(call.data["entity_id"])
        attrs = dict(old.attributes)
        for key, value in call.data.items():
            if key == "brightness_pct":
                attrs["brightness"] = round(value * 255 / 100)
            elif key not in ("entity_id", "transition"):
                attrs[key] = value
        hass.states.async_set(
            old.entity_id,
            "on" if call.service == "turn_on" else "off",
            attrs,
            context=call.context,
        )

    hass.services.async_register("light", "turn_on", light_service)
    hass.services.async_register("light", "turn_off", light_service)
    engine = HaloRoomEngine(hass, manager, "living")
    await engine.async_start()
    await hass.async_block_till_done()
    yield engine, manager, room, calls
    await engine.async_stop()


async def advance(hass, freezer, seconds):
    now = dt_util.utcnow() + timedelta(seconds=seconds)
    freezer.move_to(now)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()


async def enable(hass, engine):
    await engine.async_set_mode("automation", True)
    await hass.async_block_till_done()


def natural_profile():
    return {
        "id": "day",
        "linked": True,
        "morning": {
            "brightness": {
                "low_elevation": 0,
                "high_elevation": 10,
                "low": 20,
                "high": 100,
            },
            "temperature": {
                "low_elevation": 0,
                "high_elevation": 10,
                "low": 2000,
                "high": 6000,
            },
        },
    }


def scene(scene_id="cinema", *, autonomous=False):
    return {
        "id": scene_id,
        "name": scene_id,
        "can_turn_on": autonomous,
        "conditions": {"type": "state", "entity_id": "media_player.tv", "state": "on"},
        "lights": {
            "light.one": {"state": "on", "brightness_pct": 20},
            "light.two": {"state": "off"},
        },
    }


async def test_disabled_start_and_real_aggregated_state(hass, room_engine):
    engine, _, _, calls = room_engine
    assert not calls
    assert engine.status["reason"] == "disabled"
    hass.states.async_set("light.one", "on")
    await hass.async_block_till_done()
    assert engine.is_on and engine.available
    for light in ("light.one", "light.two"):
        hass.states.async_set(light, "unavailable")
    await hass.async_block_till_done()
    assert not engine.available


async def test_presence_absence_cancellation_and_timeout(hass, freezer, room_engine):
    engine, _, _, calls = room_engine
    await enable(hass, engine)
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert engine.is_on
    assert engine.status["pause_until"] is None
    assert len(calls) == 2
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    await advance(hass, freezer, 60)
    assert engine.is_on
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    await advance(hass, freezer, 90)
    assert engine.is_on
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    await advance(hass, freezer, 121)
    assert not engine.is_on
    assert engine.status["reason"] == "absence"


async def test_lux_drop_hysteresis_and_event_transition(hass, room_engine):
    engine, manager, _, calls = room_engine
    manager.config["transitions"] = {"turn_on": 2, "lux_on": 8}
    hass.states.async_set("sensor.lux", "200")
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    await enable(hass, engine)
    assert not engine.is_on
    hass.states.async_set("sensor.lux", "90")
    await hass.async_block_till_done()
    assert engine.is_on and engine.status["dark"] is True
    assert calls[-1].data["transition"] == 8
    hass.states.async_set("sensor.lux", "110")
    await hass.async_block_till_done()
    assert engine.status["dark"] is True
    hass.states.async_set("sensor.lux", "121")
    await hass.async_block_till_done()
    assert engine.status["dark"] is False
    hass.states.async_set("sensor.lux", "110")
    await hass.async_block_till_done()
    assert engine.status["dark"] is False


@pytest.mark.parametrize("allow", [False, True])
async def test_manual_pause_absence_policy_and_return(
    hass, freezer, room_engine, allow
):
    engine, _, room, _ = room_engine
    room["allow_off_during_pause"] = allow
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    await enable(hass, engine)
    await engine.async_turn_on()
    assert engine.status["pause_until"]
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    await advance(hass, freezer, 121)
    assert engine.is_on is not allow
    assert engine.status["pause_until"]
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is None
    assert engine.is_on


@pytest.mark.parametrize("allow", [False, True])
async def test_manual_pause_high_lux_policy(hass, freezer, room_engine, allow):
    engine, _, room, _ = room_engine
    room.update(lux_off=True, allow_off_during_pause=allow)
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    await enable(hass, engine)
    await engine.async_turn_on()
    hass.states.async_set("sensor.lux", "200")
    await hass.async_block_till_done()
    await advance(hass, freezer, 29)
    assert engine.is_on
    await advance(hass, freezer, 2)
    assert engine.is_on is not allow


async def test_manual_off_holds_and_survives_restart(hass, freezer, room_engine):
    engine, manager, _, _ = room_engine
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    await enable(hass, engine)
    await engine.async_turn_off()
    assert not engine.is_on
    deadline = engine.status["pause_until"]
    await engine.async_stop()
    replacement = HaloRoomEngine(hass, manager, "living")
    await replacement.async_start()
    assert replacement.status["pause_until"] == deadline
    assert not replacement.is_on
    await advance(hass, freezer, 901)
    assert replacement.is_on
    assert replacement.status["pause_until"] is None
    await replacement.async_stop()


async def test_manual_color_and_halo_feedback_are_distinct(hass, room_engine):
    engine, _, _, _ = room_engine
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    await enable(hass, engine)
    assert engine.status["pause_until"] is None
    state = hass.states.get("light.one")
    hass.states.async_set(
        "light.one",
        "on",
        {**state.attributes, "brightness": 40},
        context=Context(user_id="test-user"),
    )
    await hass.async_block_till_done()
    assert engine.status["pause_until"]
    await engine.async_resume()
    assert engine.status["pause_until"] is None


async def test_priority_autonomous_scene_and_natural_exit(hass, room_engine):
    engine, manager, room, calls = room_engine
    first, second = scene("first", autonomous=True), scene("second", autonomous=True)
    second["lights"]["light.one"]["brightness_pct"] = 80
    room["scenes"] = [first, second]
    room["associations"] = [
        {"profile_id": "day", "lights": room["lights"], "brightness_offset": 0}
    ]
    manager.config["profiles"]["day"] = natural_profile()
    await engine.async_reconfigure()
    await enable(hass, engine)
    hass.states.async_set("media_player.tv", "on")
    await hass.async_block_till_done()
    assert engine.status["scene_id"] == "first"
    assert hass.states.get("light.one").attributes["brightness"] == 51
    assert hass.states.get("light.two").state == "off"
    room["scenes"] = [second, first]
    await engine.async_reconfigure()
    assert engine.status["scene_id"] == "second"
    assert hass.states.get("light.one").attributes["brightness"] == 204
    hass.states.async_set("binary_sensor.presence", "on")
    hass.states.async_set("media_player.tv", "off")
    await hass.async_block_till_done()
    assert engine.status["scene_id"] is None
    assert hass.states.get("light.one").attributes["color_temp_kelvin"] == 4000
    assert calls


async def test_scene_without_power_permission_waits_for_presence(hass, room_engine):
    engine, _, room, calls = room_engine
    room["scenes"] = [scene()]
    await engine.async_reconfigure()
    await enable(hass, engine)
    hass.states.async_set("media_player.tv", "on")
    await hass.async_block_till_done()
    assert not calls
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert engine.is_on
    assert hass.states.get("light.two").state == "off"
    await engine.async_set_mode("automation", False)
    await engine.async_activate_scene("cinema")
    assert engine.status["pause_until"]
    assert room["automation_enabled"] is False


@pytest.mark.parametrize("conditional", [False, True])
async def test_imported_partial_scene_leaves_other_room_lights_unchanged(
    hass, room_engine, conditional
):
    engine, _, room, calls = room_engine
    imported = normalize_scene_import(
        {
            "name": "Native",
            "entities": {"light.one": {"state": "on", "brightness": 50}},
        },
        room["lights"],
    )["scene"]
    room["scenes"] = [imported]
    room["base"] = {"light.two": {"state": "on", "brightness_pct": 80}}
    before = hass.states.get("light.two")
    if conditional:
        imported["conditions"] = {
            "type": "state",
            "entity_id": "media_player.tv",
            "state": "on",
        }
        imported["can_turn_on"] = True
        await engine.async_reconfigure()
        await enable(hass, engine)
        hass.states.async_set("media_player.tv", "on")
        await hass.async_block_till_done()
    else:
        await engine.async_activate_scene(imported["id"])
        await hass.async_block_till_done()
    assert hass.states.get("light.one").attributes["brightness"] == 50
    assert hass.states.get("light.two") == before
    assert calls and {call.data["entity_id"] for call in calls} == {"light.one"}


async def test_natural_adjusts_only_on_members_and_suspends_without_sun(
    hass, room_engine
):
    engine, manager, room, calls = room_engine
    room["presence_entity_id"] = None
    room["associations"] = [
        {"profile_id": "day", "lights": room["lights"], "brightness_offset": -30}
    ]
    manager.config["profiles"]["day"] = natural_profile()
    await engine.async_reconfigure()
    await enable(hass, engine)
    await engine.async_turn_on()
    await engine.async_resume()
    initial = hass.states.get("light.two")
    # A lamp already off when normal natural updates begin must stay off.
    hass.states.async_set(
        "light.two", "off", initial.attributes, context=calls[-1].context
    )
    await hass.async_block_till_done()
    calls.clear()
    hass.states.async_set("sun.sun", "above_horizon", {"elevation": 8, "rising": True})
    await hass.async_block_till_done()
    assert all(call.data["entity_id"] == "light.one" for call in calls)
    assert hass.states.get("light.two").state == "off"
    calls.clear()
    hass.states.async_set("sun.sun", "unavailable")
    await hass.async_block_till_done()
    assert not calls
    assert engine.status["reason"] == "unavailable"


@pytest.mark.parametrize(
    ("interpolation", "brightness", "temperature"),
    [("linear", 28, 3000), ("ease_in_out", 22.75, 2625), ("ease_in", 22.75, 2625)],
)
async def test_natural_curve_mode_reaches_lamp_commands(
    hass, room_engine, interpolation, brightness, temperature
):
    engine, manager, room, calls = room_engine
    room["associations"] = [
        {"profile_id": "day", "lights": room["lights"], "brightness_offset": -30}
    ]
    profile = natural_profile()
    for curve in profile["morning"].values():
        curve["interpolation"] = interpolation
    manager.config["profiles"]["day"] = profile
    manager.config["transitions"]["turn_on"] = 7.5
    hass.states.async_set(
        "sun.sun", "above_horizon", {"elevation": 2.5, "rising": True}
    )
    await engine.async_reconfigure()
    await enable(hass, engine)
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert {call.data["entity_id"] for call in calls} == set(room["lights"])
    for call in calls:
        assert call.service == "turn_on"
        assert call.data["brightness_pct"] == brightness
        assert call.data["color_temp_kelvin"] == temperature
        assert call.data["transition"] == 7.5


async def test_unavailable_lux_does_not_turn_on_and_recovers(hass, room_engine):
    engine, _, _, calls = room_engine
    hass.states.async_set("binary_sensor.presence", "on")
    hass.states.async_set("sensor.lux", "unavailable")
    await hass.async_block_till_done()
    await enable(hass, engine)
    assert not calls
    assert engine.status["dark"] is None
    hass.states.async_set("sensor.lux", "10")
    await hass.async_block_till_done()
    assert engine.is_on


@pytest.mark.parametrize(
    "local,expected", [("inherit", 5), (None, None), (0, 0), (3, 3)]
)
async def test_transition_inherit_absent_zero_and_unsupported(
    hass, room_engine, local, expected
):
    engine, manager, room, calls = room_engine
    manager.config["transitions"]["turn_on"] = 5
    room["transitions"]["turn_on"] = local
    state = hass.states.get("light.two")
    hass.states.async_set(
        "light.two", "off", {**state.attributes, "supported_features": 0}
    )
    await hass.async_block_till_done()
    await engine.async_turn_on()
    assert calls[-2].data.get("transition") == expected
    assert ("transition" in calls[-2].data) is (expected is not None)
    assert "transition" not in calls[-1].data
    assert "brightness_pct" not in calls[-1].data


async def test_live_preview_exclusivity_cancel_and_expiry(hass, freezer, room_engine):
    engine, _, room, _ = room_engine
    token = await engine.async_begin_edit("one")
    with pytest.raises(ValueError, match="room_being_edited"):
        await engine.async_begin_edit("two")
    await engine.async_preview(
        token, {"light.one": {"state": "on", "brightness_pct": 10}}
    )
    assert engine.is_on
    assert engine.status["editing"]
    assert not engine.status["pause_until"]
    await engine.async_end_edit(token, save=False)
    assert not engine.is_on
    assert not room["automation_enabled"]
    token = await engine.async_begin_edit("one")
    await engine.async_preview(token, {"light.one": {"state": "on"}})
    await advance(hass, freezer, 121)
    assert not engine.status["editing"]
    assert not engine.is_on


async def test_edit_suspends_absence_and_save_preserves_disabled_mode(
    hass, freezer, room_engine
):
    engine, _, room, _ = room_engine
    token = await engine.async_begin_edit("one")
    await engine.async_preview(token, {"light.one": {"state": "on"}})
    await advance(hass, freezer, 100)
    await engine.async_touch_edit(token)
    await advance(hass, freezer, 50)
    assert engine.is_on
    await engine.async_end_edit(token, save=True)
    assert room["automation_enabled"] is False
    assert engine.is_on


async def test_unload_releases_listeners_and_timers(hass, freezer, room_engine):
    engine, _, _, calls = room_engine
    await enable(hass, engine)
    await engine.async_stop()
    hass.states.async_set("binary_sensor.presence", "on")
    await advance(hass, freezer, 1000)
    assert not calls


async def test_profile_edit_and_natural_toggle_keep_off_lamps_off(hass, room_engine):
    engine, manager, room, calls = room_engine
    room["presence_entity_id"] = None
    room["associations"] = [
        {"profile_id": "day", "lights": room["lights"], "brightness_offset": 0}
    ]
    manager.config["profiles"]["day"] = natural_profile()
    state = hass.states.get("light.one")
    hass.states.async_set("light.one", "on", state.attributes)
    await hass.async_block_till_done()
    await engine.async_resume()
    # Establish a mixed room without an intervention currently holding automation.
    state = hass.states.get("light.two")
    hass.states.async_set(
        "light.two", "off", state.attributes, context=calls[-1].context
    )
    await hass.async_block_till_done()
    manager.config["profiles"]["day"]["morning"]["temperature"]["high"] = 5000
    await engine.async_reconfigure()
    assert hass.states.get("light.two").state == "off"
    assert hass.states.get("light.one").attributes["color_temp_kelvin"] == 3500
    await engine.async_set_mode("natural", False)
    await engine.async_set_mode("natural", True)
    assert hass.states.get("light.two").state == "off"


@pytest.mark.parametrize(
    "trigger,expected", [("presence", 2), ("lux", 8), ("condition", 12)]
)
async def test_autonomous_scene_uses_actual_turn_on_cause(
    hass, room_engine, trigger, expected
):
    engine, manager, room, calls = room_engine
    room["scenes"] = [scene(autonomous=True)]
    manager.config["transitions"] = {"turn_on": 2, "lux_on": 8, "scene": 12}
    if trigger == "presence":
        room["scenes"][0]["conditions"] = {
            "type": "state",
            "entity_id": "binary_sensor.presence",
            "state": "on",
        }
    elif trigger == "lux":
        hass.states.async_set("binary_sensor.presence", "on")
        hass.states.async_set("sensor.lux", "200")
        room["scenes"][0]["conditions"] = {
            "type": "numeric",
            "entity_id": "sensor.lux",
            "below": 100,
        }
    await engine.async_reconfigure()
    await enable(hass, engine)
    if trigger == "presence":
        hass.states.async_set("binary_sensor.presence", "on")
    elif trigger == "lux":
        hass.states.async_set("sensor.lux", "90")
    else:
        hass.states.async_set("media_player.tv", "on")
    await hass.async_block_till_done()
    assert calls[0].data["transition"] == expected


async def test_preview_cancel_restores_initial_on_brightness_and_color(
    hass, room_engine
):
    engine, _, _, _ = room_engine
    state = hass.states.get("light.one")
    hass.states.async_set("light.one", "on", state.attributes)
    await hass.async_block_till_done()
    token = await engine.async_begin_edit("one")
    await engine.async_preview(
        token,
        {"light.one": {"state": "on", "brightness_pct": 10, "color_temp_kelvin": 5000}},
    )
    await engine.async_end_edit(token, save=False)
    result = hass.states.get("light.one")
    assert result.state == "on"
    assert result.attributes["brightness"] == 128
    assert result.attributes["color_temp_kelvin"] == 3000


@pytest.mark.parametrize("expired", [False, True])
async def test_native_editor_cancel_and_expiry_restore_effect_exact_rgbww(
    hass, freezer, room_engine, expired
):
    engine, _, _, calls = room_engine
    initial = {
        "brightness": 123,
        "effect": "candle",
        "color_mode": "rgbww",
        "rgbww_color": [13, 27, 82, 54, 201],
        "rgb_color": [255, 250, 200],
        "supported_color_modes": ["rgbww"],
        "supported_features": LightEntityFeature.EFFECT,
    }
    hass.states.async_set("light.one", "on", initial)
    await hass.async_block_till_done()
    token = await engine.async_begin_edit("owner")
    # The native HA dialog changes the real entity directly, without Halo preview.
    hass.states.async_set(
        "light.one", "on", {**initial, "effect": "off", "brightness": 19}
    )
    await hass.async_block_till_done()
    assert engine.status["editing"]
    if expired:
        await advance(hass, freezer, 121)
    else:
        await engine.async_end_edit(token, save=False)
    restored = next(call for call in calls if call.data["entity_id"] == "light.one")
    assert restored.data == {
        "entity_id": "light.one",
        "brightness": 123,
        "effect": "candle",
        "rgbww_color": [13, 27, 82, 54, 201],
    }
    assert not engine.status["editing"]
    # The other lamp was initially off: no attempt to restore color by turning it on.
    other = [call for call in calls if call.data["entity_id"] == "light.two"]
    assert len(other) == 1 and other[0].service == "turn_off"
    assert other[0].data == {"entity_id": "light.two"}


def test_effect_transition_feedback_and_manual_effect_change(room_engine):
    engine, _, _, _ = room_engine
    engine._expected["light.one"] = {
        "until": dt_util.utcnow().timestamp() + 60,
        "target": {
            "state": "on",
            "brightness": 180,
            "effect": "candle",
            "rgbw_color": [50, 60, 70, 80],
        },
    }
    initial = {"brightness": 128, "effect": "off", "rgbw_color": [10, 20, 30, 40]}
    old = State("light.one", "on", initial)
    feedback = State(
        "light.one",
        "on",
        {
            **initial,
            "brightness": 150,
            "effect": "candle",
            "rgbw_color": [30, 40, 50, 60],
        },
    )
    assert engine._own_change("light.one", old, feedback)
    different = State("light.one", "on", {**feedback.attributes, "effect": "colorloop"})
    assert not engine._own_change("light.one", feedback, different)


def test_white_transition_feedback_is_not_a_manual_override(room_engine):
    engine, _, _, _ = room_engine
    engine._expected["light.one"] = {
        "until": dt_util.utcnow().timestamp() + 60,
        "target": {"state": "on", "white": 180},
    }
    old = State(
        "light.one",
        "on",
        {"brightness": 128, "color_mode": "rgb", "rgb_color": [255, 0, 0]},
    )
    feedback = State("light.one", "on", {"brightness": 150, "color_mode": "white"})
    assert engine._own_change("light.one", old, feedback)


def test_effect_can_clear_native_colors_without_manual_override(room_engine):
    engine, _, _, _ = room_engine
    engine._expected["light.one"] = {
        "until": dt_util.utcnow().timestamp() + 60,
        "target": {"state": "on", "effect": "candle"},
    }
    old = State(
        "light.one",
        "on",
        {"effect": "off", "color_mode": "rgb", "rgb_color": [255, 0, 0]},
    )
    feedback = State("light.one", "on", {"effect": "candle", "color_mode": "onoff"})
    assert engine._own_change("light.one", old, feedback)


async def test_manual_effect_change_starts_room_pause(hass, room_engine):
    engine, _, _, _ = room_engine
    state = hass.states.get("light.one")
    await enable(hass, engine)
    hass.states.async_set(
        "light.one", state.state, {**state.attributes, "effect": "candle"}
    )
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is not None


def test_natural_values_replace_native_base_brightness_and_white_mode(room_engine):
    engine, manager, room, _ = room_engine
    room["base"] = {
        "light.one": {
            "state": "on",
            "brightness": 12,
            "color_mode": "white",
            "effect": "candle",
            "white": 12,
        }
    }
    room["associations"] = [{"profile_id": "day", "lights": ["light.one"]}]
    manager.config["profiles"]["day"] = natural_profile()
    assert engine._ambience()["light.one"] == {
        "state": "on",
        "brightness_pct": 60,
        "color_temp_kelvin": 4000,
    }


async def test_new_off_command_cancels_pending_old_turn_on_members(hass, room_engine):
    engine, _, _, calls = room_engine
    started, release = asyncio.Event(), asyncio.Event()

    async def slow_on(call):
        calls.append(call)
        started.set()
        await release.wait()
        state = hass.states.get(call.data["entity_id"])
        hass.states.async_set(
            state.entity_id, "on", state.attributes, context=call.context
        )

    hass.services.async_register("light", "turn_on", slow_on)
    turn_on = asyncio.create_task(engine.async_turn_on())
    await started.wait()
    turn_off = asyncio.create_task(engine.async_turn_off())
    await asyncio.sleep(0)
    release.set()
    await asyncio.gather(turn_on, turn_off)
    await hass.async_block_till_done()
    assert not engine.is_on
    assert not any(
        call.service == "turn_on" and call.data["entity_id"] == "light.two"
        for call in calls
    )


async def test_transition_feedback_without_context_and_real_override(hass, room_engine):
    engine, manager, room, _ = room_engine
    room["base"] = {
        "light.one": {"state": "on", "brightness_pct": 80, "color_temp_kelvin": 5000}
    }
    manager.config["transitions"]["turn_on"] = 30

    async def begin_transition(call):
        state = hass.states.get(call.data["entity_id"])
        hass.states.async_set(
            state.entity_id, "on", state.attributes, context=call.context
        )

    hass.services.async_register("light", "turn_on", begin_transition)
    await enable(hass, engine)
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    state = hass.states.get("light.one")
    hass.states.async_set(
        "light.one",
        "on",
        {
            **state.attributes,
            "brightness": 160,
            "color_temp_kelvin": 4000,
            "rgb_color": [255, 210, 180],
        },
    )
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is None
    state = hass.states.get("light.one")
    hass.states.async_set("light.one", "on", {**state.attributes, "brightness": 40})
    await hass.async_block_till_done()
    assert engine.status["pause_until"]


async def test_stop_during_command_prevents_remaining_members_and_safe_room_removal(
    hass, room_engine
):
    engine, manager, _, calls = room_engine
    started, release = asyncio.Event(), asyncio.Event()

    async def slow_on(call):
        calls.append(call)
        started.set()
        await release.wait()
        state = hass.states.get(call.data["entity_id"])
        hass.states.async_set(
            state.entity_id, "on", state.attributes, context=call.context
        )

    hass.services.async_register("light", "turn_on", slow_on)
    task = asyncio.create_task(engine.async_turn_on())
    await started.wait()
    manager.config["rooms"].pop("living")
    await engine.async_stop()
    release.set()
    await task
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_atomic_preview_commit_can_cross_expiry_and_subscribes_new_conditions(
    hass, freezer, room_engine
):
    engine, _, room, _ = room_engine
    token = await engine.async_begin_edit("owner")
    await engine.async_preview(token, {"light.one": {"state": "on"}})

    async def commit():
        # Simulate disk persistence crossing the lease deadline while the editor
        # lock prevents an expiry callback from restoring the old snapshot.
        now = dt_util.utcnow() + timedelta(seconds=121)
        freezer.move_to(now)
        async_fire_time_changed(hass, now)
        room["scenes"] = [scene(autonomous=True)]
        room["automation_enabled"] = True

    await engine.async_commit_edit(token, commit)
    await hass.async_block_till_done()
    assert not engine.status["editing"]
    hass.states.async_set("media_player.tv", "on")
    await hass.async_block_till_done()
    assert engine.status["scene_id"] == "cinema"
    assert engine.is_on


async def test_failed_preview_commit_preserves_editor_for_retry(
    hass, freezer, room_engine
):
    engine, _, _, _ = room_engine
    token = await engine.async_begin_edit("owner")

    async def fail():
        freezer.move_to(dt_util.utcnow() + timedelta(seconds=121))
        raise OSError("disk unavailable")

    with pytest.raises(OSError, match="disk unavailable"):
        await engine.async_commit_edit(token, fail)
    assert engine.status["editing"]
    await engine.async_preview(token, {"light.one": {"state": "on"}})
    await engine.async_end_edit(token, save=False)
    assert not engine.status["editing"]


async def test_explicit_scene_status_tracks_actual_manual_scene_until_resume(
    hass, room_engine
):
    engine, _, room, _ = room_engine
    room["scenes"] = [scene("conditional"), scene("explicit")]
    room["scenes"][1]["conditions"] = None
    await engine.async_reconfigure()
    hass.states.async_set("media_player.tv", "on")
    await hass.async_block_till_done()
    await engine.async_activate_scene("explicit")
    assert engine.status["scene_id"] == "explicit"
    assert engine.status["pause_until"]
    await engine.async_resume()
    assert engine.status["scene_id"] == "conditional"


async def test_unknown_presence_does_not_count_as_absence(hass, freezer, room_engine):
    engine, _, _, _ = room_engine
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    await enable(hass, engine)
    hass.states.async_set("binary_sensor.presence", "unavailable")
    await hass.async_block_till_done()
    await advance(hass, freezer, 200)
    assert engine.is_on
    assert engine.status["presence"] is None
    assert engine.status["absence_deadline"] is None
    assert engine.status["reason"] == "unavailable"
