"""A brief detector dropout must preserve a user's manual lighting choice."""

import asyncio
from datetime import timedelta

import pytest
from homeassistant.util import dt as dt_util
from test_engine import advance, enable, scene
from test_engine import room_engine as room_engine

from custom_components.halo.engine import HaloRoomEngine


async def manual_room(hass, room_engine, *, present="on"):
    """Enter a dark room, then deliberately override its automatic ambience."""
    engine, _, _, calls = room_engine
    await engine.async_reconfigure()
    await enable(hass, engine)
    hass.states.async_set("binary_sensor.presence", present)
    await hass.async_block_till_done()
    await engine.async_turn_on()
    assert engine.status["pause_until"] is not None
    calls.clear()
    return engine.status["pause_until"]


async def presence(hass, state, attributes=None):
    hass.states.async_set("binary_sensor.presence", state, attributes)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("window", "local", "elapsed", "keep_pause"),
    [
        (None, 0, 29, True),
        (None, 0, 30, False),
        (30, 0, 29, True),
        (30, 0, 30, False),
        (0, 0, 0, False),
        (0, 15, 14, True),
        (0, 15, 15, False),
        (20, 60, 59, True),
        (20, 60, 60, False),
        (100, 30, 99, True),
        (100, 30, 100, False),
    ],
)
async def test_manual_pause_return_requires_continuous_absence_at_both_thresholds(
    hass, freezer, room_engine, window, local, elapsed, keep_pause
):
    engine, manager, room, _ = room_engine
    room.update(absence_delay=local, allow_off_during_pause=False)
    if window is not None:
        manager.config["presence_return_window"] = window
    until = await manual_room(hass, room_engine)
    await presence(hass, "off")
    await advance(hass, freezer, elapsed)
    # Confirmation alone never clears a pause while the room stays unoccupied.
    assert engine.status["pause_until"] == until
    await presence(hass, "on")
    assert engine.status["pause_until"] == (until if keep_pause else None)


@pytest.mark.parametrize("lux_off", [False, True])
@pytest.mark.parametrize("allow_off", [False, True])
@pytest.mark.parametrize("elapsed", [10, 35])
async def test_pause_confirmation_is_independent_of_lux_and_extinction_policy(
    hass, freezer, room_engine, lux_off, allow_off, elapsed
):
    engine, manager, room, calls = room_engine
    manager.config["presence_return_window"] = 30
    room.update(absence_delay=0, lux_off=lux_off, allow_off_during_pause=allow_off)
    until = await manual_room(hass, room_engine)
    await presence(hass, "off")
    await advance(hass, freezer, elapsed)
    assert engine.status["pause_until"] == until
    assert engine.is_on is not allow_off
    calls.clear()
    await presence(hass, "on")
    if elapsed < 30:
        assert engine.status["pause_until"] == until
        assert engine.is_on is not allow_off
        assert not calls
    else:
        assert engine.status["pause_until"] is None
        assert engine.is_on


async def test_custom_states_and_attribute_updates_preserve_absence_start(
    hass, freezer, room_engine
):
    engine, _, room, _ = room_engine
    room.update(
        absence_delay=0,
        allow_off_during_pause=False,
        presence_states=["occupied", "moving"],
    )
    until = await manual_room(hass, room_engine, present="occupied")
    await advance(hass, freezer, 35)
    await presence(hass, "moving")
    assert engine.status["pause_until"] == until
    await presence(hass, "vacant", {"battery": 100})
    await advance(hass, freezer, 20)
    await presence(hass, "vacant", {"battery": 99})
    await advance(hass, freezer, 10)
    assert engine.status["pause_until"] == until
    await presence(hass, "occupied")
    assert engine.status["pause_until"] is None


@pytest.mark.parametrize("invalid_state", ["unknown", "unavailable"])
@pytest.mark.parametrize("before_interruption", [20, 35])
async def test_unknown_or_unavailable_interrupts_confirmation(
    hass, freezer, room_engine, invalid_state, before_interruption
):
    engine, _, room, _ = room_engine
    room.update(absence_delay=0, allow_off_during_pause=False)
    until = await manual_room(hass, room_engine)
    await presence(hass, "off")
    await advance(hass, freezer, before_interruption)
    await presence(hass, invalid_state)
    await advance(hass, freezer, 35)
    await presence(hass, "on")
    assert engine.status["pause_until"] == until
    # A new, shorter known absence cannot reuse time before the interruption.
    await presence(hass, "off")
    await advance(hass, freezer, 20)
    await presence(hass, "on")
    assert engine.status["pause_until"] == until
    await presence(hass, "off")
    await advance(hass, freezer, 30)
    await presence(hass, "on")
    assert engine.status["pause_until"] is None


async def test_short_dropout_keeps_manual_scene_then_confirmed_return_clears_it(
    hass, freezer, room_engine
):
    engine, _, room, _ = room_engine
    room.update(absence_delay=0, allow_off_during_pause=False, scenes=[scene()])
    hass.states.async_set("media_player.tv", "off")
    await manual_room(hass, room_engine)
    await engine.async_activate_scene("cinema")
    until = engine.status["pause_until"]
    assert engine.lighting_status == {"mode": "scene", "scene_id": "cinema"}
    await presence(hass, "off")
    await advance(hass, freezer, 20)
    await presence(hass, "on")
    assert engine.status["pause_until"] == until
    assert engine.status["scene_id"] == "cinema"
    assert engine.lighting_status == {"mode": "scene", "scene_id": "cinema"}
    await presence(hass, "off")
    await advance(hass, freezer, 30)
    assert engine.status["pause_until"] == until
    await presence(hass, "on")
    assert engine.status["pause_until"] is None
    assert engine.status["scene_id"] is None
    assert engine.lighting_status == {"mode": "manual", "scene_id": None}


@pytest.mark.parametrize("end", ["expiry", "resume"])
async def test_normal_expiry_and_resume_button_still_end_pause(
    hass, freezer, room_engine, end
):
    engine, _, room, _ = room_engine
    room.update(absence_delay=0, allow_off_during_pause=False, manual_pause=20)
    until = await manual_room(hass, room_engine)
    await presence(hass, "off")
    await advance(hass, freezer, 5)
    await presence(hass, "on")
    assert engine.status["pause_until"] == until
    if end == "expiry":
        await advance(hass, freezer, 15)
    else:
        await engine.async_resume()
    assert engine.status["pause_until"] is None
    assert engine.is_on


@pytest.mark.parametrize("elapsed", [20, 30])
async def test_restart_preserves_manual_pause_and_known_absence_duration(
    hass, freezer, room_engine, elapsed
):
    engine, manager, room, _ = room_engine
    room.update(absence_delay=0, allow_off_during_pause=False)
    until = await manual_room(hass, room_engine)
    await presence(hass, "off")
    await advance(hass, freezer, 10)
    await engine.async_stop()
    resumed = HaloRoomEngine(hass, manager, "living")
    try:
        await resumed.async_start()
        assert resumed.status["pause_until"] == until
        await advance(hass, freezer, elapsed - 10)
        await presence(hass, "on")
        assert resumed.status["pause_until"] == (until if elapsed < 30 else None)
    finally:
        await resumed.async_stop()


@pytest.mark.parametrize("followup_presence", [None, "moving", "brief_absence"])
async def test_slow_extinction_does_not_extend_actual_absence_until_lock_release(
    hass, freezer, room_engine, followup_presence
):
    engine, _, room, calls = room_engine
    room.update(
        absence_delay=0,
        allow_off_during_pause=True,
        presence_states=["on", "moving"],
    )
    until = await manual_room(hass, room_engine)
    started, release = asyncio.Event(), asyncio.Event()

    async def slow_off(call):
        calls.append(call)
        started.set()
        await release.wait()
        state = hass.states.get(call.data["entity_id"])
        hass.states.async_set(
            state.entity_id, "off", state.attributes, context=call.context
        )

    hass.services.async_register("light", "turn_off", slow_off)
    hass.states.async_set("binary_sensor.presence", "off")
    await asyncio.wait_for(started.wait(), timeout=1)
    freezer.move_to(dt_util.utcnow() + timedelta(seconds=1))
    hass.states.async_set("binary_sensor.presence", "on")
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    # The return was received after one second, even though the engine cannot
    # acquire its lock until more than thirty seconds after the absence began.
    if followup_presence == "brief_absence":
        freezer.move_to(dt_util.utcnow() + timedelta(seconds=9))
        hass.states.async_set("binary_sensor.presence", "off")
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        freezer.move_to(dt_util.utcnow() + timedelta(seconds=21))
        hass.states.async_set("binary_sensor.presence", "on")
        await asyncio.sleep(0)
        await asyncio.sleep(0)
    else:
        freezer.move_to(dt_util.utcnow() + timedelta(seconds=30))
        if followup_presence:
            hass.states.async_set("binary_sensor.presence", followup_presence)
            await asyncio.sleep(0)
            await asyncio.sleep(0)
    release.set()
    await hass.async_block_till_done()
    assert engine.status["pause_until"] == until
    assert not any(call.service == "turn_on" for call in calls)


async def test_legacy_confirmation_flag_cannot_clear_a_short_manual_pause(
    hass, freezer, room_engine
):
    engine, manager, room, _ = room_engine
    room.update(absence_delay=0, allow_off_during_pause=False)
    until = await manual_room(hass, room_engine)
    await presence(hass, "off")
    # An older stored runtime confirmed absence using only the local off delay.
    manager.runtime_state["living"]["absence_confirmed"] = True
    await advance(hass, freezer, 5)
    await presence(hass, "on")
    assert engine.status["pause_until"] == until
