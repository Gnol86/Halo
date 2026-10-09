"""Fast occupancy returns use real sensor events and simulated light services."""

import asyncio

import pytest
from homeassistant.core import Context
from test_engine import advance, enable, natural_profile, scene
from test_engine import room_engine as room_engine

from custom_components.halo.engine import HaloRoomEngine


async def occupied_bright_room(hass, room_engine):
    """Start in darkness, then let the room's own lights raise its lux reading."""
    engine, manager, room, calls = room_engine
    room["absence_delay"] = 0
    manager.config["presence_return_window"] = 30
    manager.config["transitions"] = {
        "turn_on": 1,
        "turn_off": 5,
        "lux_on": 10,
        "natural": 60,
        "scene": 8,
    }
    await engine.async_reconfigure()
    await enable(hass, engine)
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert engine.is_on
    hass.states.async_set("sensor.lux", "200")
    await hass.async_block_till_done()
    assert engine.status["dark"] is False
    calls.clear()


async def absent(hass, room_engine):
    engine, _, _, calls = room_engine
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    assert not engine.is_on
    assert any(call.service == "turn_off" for call in calls)
    calls.clear()


async def present(hass):
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()


@pytest.mark.parametrize("ambience", ["base", "natural", "scene"])
async def test_return_reapplies_ambience_with_presence_transition(
    hass, room_engine, ambience
):
    engine, manager, room, calls = room_engine
    if ambience == "base":
        room["base"] = {"light.one": {"state": "on", "brightness_pct": 35}}
    elif ambience == "natural":
        manager.config["profiles"]["day"] = natural_profile()
        room["associations"] = [{"profile_id": "day", "lights": ["light.one"]}]
    else:
        room["scenes"] = [scene()]
        hass.states.async_set("media_player.tv", "on")
    room["transitions"]["turn_on"] = 0
    await occupied_bright_room(hass, room_engine)
    await absent(hass, room_engine)
    await present(hass)
    assert engine.is_on
    assert engine.status["dark"] is False
    assert engine.status["lux"] == 200
    assert engine.status["pause_until"] is None
    assert calls and all(call.data.get("transition") == 0 for call in calls)
    first = next(call for call in calls if call.data["entity_id"] == "light.one")
    assert first.service == "turn_on"
    assert (
        first.data["brightness_pct"]
        == {
            "base": 35,
            "natural": 60,
            "scene": 20,
        }[ambience]
    )
    if ambience == "natural":
        assert first.data["color_temp_kelvin"] == 4000
    if ambience == "scene":
        assert hass.states.get("light.two").state == "off"
        assert engine.status["reason"] == "scene"
    # The bypass must not turn the hysteresis memory dark or schedule lux_on later.
    calls.clear()
    hass.states.async_set("sensor.lux", "110")
    await hass.async_block_till_done()
    assert engine.status["dark"] is False
    hass.states.async_set("sensor.lux", "50")
    await hass.async_block_till_done()
    assert engine.status["dark"] is True
    assert not calls


@pytest.mark.parametrize(
    ("duration", "elapsed", "expected"),
    [(30, 29, True), (30, 30, False), (30, 31, False), (0, 0, False)],
)
async def test_return_window_is_strict_and_zero_disables(
    hass, freezer, room_engine, duration, elapsed, expected
):
    engine, manager, _, calls = room_engine
    await occupied_bright_room(hass, room_engine)
    manager.config["presence_return_window"] = duration
    await absent(hass, room_engine)
    await advance(hass, freezer, elapsed)
    await present(hass)
    assert engine.is_on is expected
    assert bool(calls) is expected
    if expected:
        assert all(call.data.get("transition") == 1 for call in calls)


async def test_missing_global_field_uses_default_window(hass, room_engine):
    engine, manager, _, _ = room_engine
    await occupied_bright_room(hass, room_engine)
    manager.config.pop("presence_return_window")
    await absent(hass, room_engine)
    await present(hass)
    assert engine.is_on


@pytest.mark.parametrize("previous_state", ["unknown", "unavailable"])
async def test_sensor_recovery_is_not_a_presence_return(
    hass, room_engine, previous_state
):
    engine, _, _, calls = room_engine
    await occupied_bright_room(hass, room_engine)
    await absent(hass, room_engine)
    hass.states.async_set("binary_sensor.presence", previous_state)
    await hass.async_block_till_done()
    await present(hass)
    assert not engine.is_on
    assert not calls


async def test_presence_attributes_do_not_consume_window(hass, room_engine):
    engine, _, _, calls = room_engine
    await occupied_bright_room(hass, room_engine)
    await absent(hass, room_engine)
    hass.states.async_set("binary_sensor.presence", "off", {"battery": 99})
    await hass.async_block_till_done()
    assert not calls
    await present(hass)
    assert engine.is_on
    calls.clear()
    hass.states.async_set("binary_sensor.presence", "on", {"battery": 98})
    await hass.async_block_till_done()
    assert not calls


async def test_custom_presence_states_are_supported(hass, room_engine):
    engine, _, room, _ = room_engine
    await occupied_bright_room(hass, room_engine)
    room["presence_states"] = ["occupied", "moving"]
    await engine.async_reconfigure()
    hass.states.async_set("sensor.lux", "50")
    hass.states.async_set("binary_sensor.presence", "occupied")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.lux", "200")
    hass.states.async_set("binary_sensor.presence", "empty")
    await hass.async_block_till_done()
    assert not engine.is_on
    hass.states.async_set("binary_sensor.presence", "moving")
    await hass.async_block_till_done()
    assert engine.is_on


@pytest.mark.parametrize("lux_off", [False, True])
async def test_first_bright_entry_is_never_bypassed(hass, room_engine, lux_off):
    engine, manager, room, calls = room_engine
    room.update(absence_delay=0, lux_off=lux_off)
    manager.config["presence_return_window"] = 30
    hass.states.async_set("sensor.lux", "200")
    await enable(hass, engine)
    await present(hass)
    assert not engine.is_on
    assert not calls


async def test_rooms_allowing_lux_off_do_not_bypass(hass, room_engine):
    engine, _, room, calls = room_engine
    await occupied_bright_room(hass, room_engine)
    room["lux_off"] = True
    await engine.async_reconfigure()
    await absent(hass, room_engine)
    await present(hass)
    assert not engine.is_on
    assert not calls


@pytest.mark.parametrize(
    "invalidate",
    ["manual", "physical", "editing", "disabled", "reconfigure", "restart"],
)
async def test_window_is_cleared_by_user_actions_and_lifecycle(
    hass, room_engine, invalidate
):
    engine, manager, _, calls = room_engine
    await occupied_bright_room(hass, room_engine)
    await absent(hass, room_engine)
    if invalidate == "manual":
        await engine.async_turn_off()
    elif invalidate == "physical":
        state = hass.states.get("light.one")
        context = Context(user_id="user")
        hass.states.async_set("light.one", "on", state.attributes, context=context)
        await hass.async_block_till_done()
        hass.states.async_set("light.one", "off", state.attributes, context=context)
        await hass.async_block_till_done()
    elif invalidate == "editing":
        token = await engine.async_begin_edit("user")
        await engine.async_end_edit(token, save=False)
    elif invalidate == "disabled":
        await engine.async_set_mode("automation", False)
        await engine.async_set_mode("automation", True)
    elif invalidate == "reconfigure":
        await engine.async_reconfigure()
    else:
        await engine.async_stop()
        engine = HaloRoomEngine(hass, manager, "living")
        await engine.async_start()
    calls.clear()
    try:
        await present(hass)
        assert not engine.is_on
        assert not calls
    finally:
        if invalidate == "restart":
            await engine.async_stop()


async def test_manual_extinction_never_opens_window(hass, room_engine):
    engine, _, _, calls = room_engine
    await occupied_bright_room(hass, room_engine)
    await engine.async_turn_off()
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    calls.clear()
    await present(hass)
    assert engine.status["pause_until"] is not None
    assert not engine.is_on
    assert not calls


async def test_confirmed_absence_still_ends_manual_pause(hass, freezer, room_engine):
    engine, _, room, calls = room_engine
    await occupied_bright_room(hass, room_engine)
    room["absence_delay"] = 30
    await engine.async_reconfigure()
    await engine.async_turn_on()
    assert engine.status["pause_until"] is not None
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    await advance(hass, freezer, 30)
    assert not engine.is_on
    assert engine.status["pause_until"] is not None
    calls.clear()
    await present(hass)
    assert engine.status["pause_until"] is None
    assert engine.is_on
    assert all(call.data.get("transition") == 1 for call in calls)


@pytest.mark.parametrize("elapsed", [1, 31])
async def test_return_during_fade_forces_on_without_extending_window(
    hass, freezer, room_engine, elapsed
):
    engine, _, _, calls = room_engine
    await occupied_bright_room(hass, room_engine)

    async def fading_off(call):
        calls.append(call)
        # A real transition can leave both entities 'on' until the fade ends.

    hass.services.async_register("light", "turn_off", fading_off)
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    assert engine.is_on
    await advance(hass, freezer, elapsed)
    calls.clear()
    await present(hass)
    on_calls = [call for call in calls if call.service == "turn_on"]
    assert len(on_calls) == (2 if elapsed < 30 else 0)
    assert all(call.data.get("transition") == 1 for call in on_calls)


@pytest.mark.parametrize("manual_after_return", [False, True])
async def test_return_cancels_pending_absence_off_but_new_manual_off_wins(
    hass, room_engine, manual_after_return
):
    engine, _, _, calls = room_engine
    await occupied_bright_room(hass, room_engine)
    started, release = asyncio.Event(), asyncio.Event()

    async def slow_off(call):
        calls.append(call)
        if not started.is_set():
            started.set()
            await release.wait()
        state = hass.states.get(call.data["entity_id"])
        hass.states.async_set(
            state.entity_id, "off", state.attributes, context=call.context
        )

    hass.services.async_register("light", "turn_off", slow_off)
    hass.states.async_set("binary_sensor.presence", "off")
    await asyncio.wait_for(started.wait(), timeout=1)
    hass.states.async_set("binary_sensor.presence", "on")
    # Let the synchronous event callback invalidate the outstanding batch before
    # the blocked service can complete. Do not await HA's pending service here.
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    manual = None
    if manual_after_return:
        manual = asyncio.create_task(engine.async_turn_off())
        await asyncio.sleep(0)
    release.set()
    if manual:
        await manual
    await hass.async_block_till_done()
    if manual_after_return:
        assert not engine.is_on
        assert not any(call.service == "turn_on" for call in calls)
    else:
        assert engine.is_on
        assert not any(
            call.service == "turn_off" and call.data["entity_id"] == "light.two"
            for call in calls
        )
        on_calls = [call for call in calls if call.service == "turn_on"]
        assert len(on_calls) == 2
        assert all(call.data.get("transition") == 1 for call in on_calls)


async def test_window_starts_at_extinction_after_absence_delay(
    hass, freezer, room_engine
):
    engine, _, room, calls = room_engine
    await occupied_bright_room(hass, room_engine)
    room["absence_delay"] = 120
    await engine.async_reconfigure()
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    await advance(hass, freezer, 119)
    assert engine.is_on
    await advance(hass, freezer, 2)
    assert not engine.is_on
    calls.clear()
    await advance(hass, freezer, 10)
    await present(hass)
    assert engine.is_on
    assert all(call.data.get("transition") == 1 for call in calls)


async def test_scene_extinction_does_not_open_a_return_window(hass, room_engine):
    engine, _, room, calls = room_engine
    await occupied_bright_room(hass, room_engine)
    blackout = scene()
    blackout["lights"] = {
        "light.one": {"state": "off"},
        "light.two": {"state": "off"},
    }
    room["scenes"] = [blackout]
    hass.states.async_set("media_player.tv", "off")
    await engine.async_reconfigure()
    hass.states.async_set("media_player.tv", "on")
    await hass.async_block_till_done()
    assert not engine.is_on
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    hass.states.async_set("media_player.tv", "off")
    await hass.async_block_till_done()
    calls.clear()
    await present(hass)
    assert not engine.is_on
    assert not calls
