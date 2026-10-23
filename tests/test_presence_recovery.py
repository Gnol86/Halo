"""Occupancy restores usable light after delayed Hue group feedback."""

import asyncio
from datetime import timedelta

import pytest
from homeassistant.core import Context
from homeassistant.util import dt as dt_util
from test_engine import advance, enable, scene
from test_engine import room_engine as room_engine


async def hall(hass, room_engine, *, absence_delay=0, turn_off=2, turn_on=0, lux=False):
    """Use the observed hall policy with a simulated Hue group and its members."""
    engine, manager, room, calls = room_engine
    room.update(
        lights=["light.one"],
        absence_delay=absence_delay,
        lux_entity_id="sensor.lux" if lux else None,
        lighting_fallback={"mode": "always", "turn_off": False},
        associations=[{"profile_id": "base", "lights": ["light.one"]}],
    )
    manager.config["presence_return_window"] = 30
    manager.config["transitions"] = {
        "turn_on": turn_on,
        "turn_off": turn_off,
        "natural": 60,
        "lux_on": 10,
        "scene": 10,
    }
    manager.config["profiles"]["base"] = {
        "linked": True,
        "morning": {
            "brightness": {
                "low": 40,
                "high": 100,
                "low_elevation": -20,
                "high_elevation": 20,
                "interpolation": "ease_in_out",
            },
            "temperature": {
                "low": 2000,
                "high": 5500,
                "low_elevation": 0,
                "high_elevation": 20,
                "interpolation": "ease_in_out",
            },
        },
    }
    state = hass.states.get("light.one")
    hass.states.async_set(
        "light.one",
        "off",
        {
            **state.attributes,
            "is_hue_group": True,
            "entity_id": ["light.stairs", "light.hallway"],
        },
    )
    hass.states.async_set(
        "sun.sun", "below_horizon", {"elevation": -38.88, "rising": False}
    )
    await engine.async_reconfigure()
    await enable(hass, engine)
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert hass.states.get("light.one").attributes["brightness"] == 102
    calls.clear()


async def depart(hass, room_engine):
    _, _, _, calls = room_engine
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    assert len(calls) == 1 and calls[0].service == "turn_off"
    context = calls[0].context
    calls.clear()
    return context


async def residual_on(hass, context):
    """Hue can report a low on state using the preceding extinction context."""
    old = hass.states.get("light.one")
    hass.states.async_set(
        "light.one", "on", {**old.attributes, "brightness": 3}, context=context
    )
    await hass.async_block_till_done()


@pytest.mark.parametrize("elapsed,turn_on", [(5, 0), (139, 0), (139, 3), (139, None)])
async def test_presence_restores_natural_target_with_presence_transition(
    hass, freezer, room_engine, elapsed, turn_on
):
    engine, _, _, calls = room_engine
    await hall(hass, room_engine, turn_on=turn_on)
    context = await depart(hass, room_engine)
    await residual_on(hass, context)
    assert not calls
    # No periodic evaluation between the residual report and this arrival.
    freezer.move_to(dt_util.utcnow() + timedelta(seconds=elapsed))
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].service == "turn_on"
    expected = {
        "entity_id": "light.one",
        "brightness_pct": 40,
        "color_temp_kelvin": 2000,
    }
    if turn_on is not None:
        expected["transition"] = turn_on
    assert calls[0].data == expected
    assert engine.status["manual_hold"] is None
    assert hass.states.get("light.one").attributes["brightness"] == 102


async def test_same_context_residual_on_is_rechecked_on_tick_after_fade(
    hass, freezer, room_engine
):
    engine, _, _, calls = room_engine
    await hall(hass, room_engine)
    context = await depart(hass, room_engine)
    await residual_on(hass, context)
    assert not calls
    await advance(hass, freezer, 60)
    assert len(calls) == 1
    assert calls[0].service == "turn_off"
    assert calls[0].data["transition"] == 2
    assert not engine.is_on
    calls.clear()
    await advance(hass, freezer, 60)
    assert not calls


@pytest.mark.parametrize("feedback", ["same", "parent", "contextless"])
async def test_long_off_transition_is_not_restarted_by_ticks_or_feedback(
    hass, freezer, room_engine, feedback
):
    await hall(hass, room_engine, turn_off=90)
    _, _, _, calls = room_engine

    async def fading_off(call):
        calls.append(call)
        old = hass.states.get(call.data["entity_id"])
        hass.states.async_set(
            old.entity_id,
            "on",
            {**old.attributes, "brightness": 80},
            context=call.context,
        )

    hass.services.async_register("light", "turn_off", fading_off)
    context = await depart(hass, room_engine)
    if feedback == "parent":
        context = Context(parent_id=context.id)
    elif feedback == "contextless":
        context = Context()
    # Feedback arrives after the service completes, so a contextless report
    # invalidates the command cache while the real fade must still be respected.
    await residual_on(hass, context)
    assert not calls
    for _ in range(2):
        await advance(hass, freezer, 30)
        await residual_on(hass, context)
        assert not calls
    await advance(hass, freezer, 29)
    assert not calls
    await advance(hass, freezer, 31)
    assert len(calls) == 1 and calls[0].service == "turn_off"


async def test_long_presence_return_restores_local_scene_without_relighting_off_lamps(
    hass, freezer, room_engine
):
    await hall(hass, room_engine, turn_on=3)
    engine, _, room, calls = room_engine
    room["lights"].append("light.two")
    room["scenes"] = [scene()]
    hass.states.async_set("media_player.tv", "on")
    await engine.async_reconfigure()
    await hass.async_block_till_done()
    calls.clear()
    context = await depart(hass, room_engine)
    await residual_on(hass, context)
    freezer.move_to(dt_util.utcnow() + timedelta(seconds=139))
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert [(call.service, call.data) for call in calls] == [
        (
            "turn_on",
            {"entity_id": "light.one", "brightness_pct": 20, "transition": 3},
        ),
        ("turn_off", {"entity_id": "light.two", "transition": 3}),
    ]
    assert hass.states.get("light.two").state == "off"
    assert engine.status["reason"] == "scene"


@pytest.mark.parametrize("manual_after_return", [False, True])
async def test_long_return_interrupts_slow_extinction_but_later_manual_off_wins(
    hass, freezer, room_engine, manual_after_return
):
    await hall(hass, room_engine)
    engine, _, room, calls = room_engine
    room["lights"].append("light.two")
    room["associations"][0]["lights"].append("light.two")
    await engine.async_reconfigure()
    await engine.async_turn_on()
    calls.clear()
    started, release = asyncio.Event(), asyncio.Event()

    async def slow_off(call):
        calls.append(call)
        if not started.is_set():
            started.set()
            await release.wait()
        old = hass.states.get(call.data["entity_id"])
        hass.states.async_set(
            old.entity_id, "off", old.attributes, context=call.context
        )

    hass.services.async_register("light", "turn_off", slow_off)
    hass.states.async_set("binary_sensor.presence", "off")
    await asyncio.wait_for(started.wait(), timeout=1)
    freezer.move_to(dt_util.utcnow() + timedelta(seconds=139))
    hass.states.async_set("binary_sensor.presence", "on")
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
        assert not any(
            call.service == "turn_off" and call.data["entity_id"] == "light.two"
            for call in calls
        )
        on_calls = [call for call in calls if call.service == "turn_on"]
        assert len(on_calls) == 2
        assert all(call.data["brightness_pct"] == 40 for call in on_calls)
        assert all(call.data["transition"] == 0 for call in on_calls)
        assert engine.is_on


async def test_short_absence_before_extinction_does_not_recall_ambience(
    hass, freezer, room_engine
):
    await hall(hass, room_engine, absence_delay=60)
    _, _, _, calls = room_engine
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    await advance(hass, freezer, 5)
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert not calls


@pytest.mark.parametrize("previous", ["on", "unknown", "unavailable"])
async def test_presence_attributes_or_sensor_recovery_are_not_new_arrivals(
    hass, room_engine, previous
):
    await hall(hass, room_engine)
    _, _, _, calls = room_engine
    if previous != "on":
        hass.states.async_set("binary_sensor.presence", previous)
        await hass.async_block_till_done()
    await residual_on(hass, Context())
    calls.clear()
    hass.states.async_set("binary_sensor.presence", "on", {"battery": 80})
    await hass.async_block_till_done()
    assert all(call.data.get("transition") != 0 for call in calls)


async def test_long_return_does_not_bypass_bright_lux_permission(
    hass, freezer, room_engine
):
    await hall(hass, room_engine, lux=True)
    engine, _, _, calls = room_engine
    hass.states.async_set("sensor.lux", "200")
    await hass.async_block_till_done()
    context = await depart(hass, room_engine)
    await residual_on(hass, context)
    freezer.move_to(dt_util.utcnow() + timedelta(seconds=139))
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert engine.status["lighting_allowed"] is False
    assert all(call.data.get("transition") != 0 for call in calls)


@pytest.mark.parametrize("suspension", ["manual", "editing", "disabled"])
async def test_presence_recovery_respects_existing_suspensions(
    hass, freezer, room_engine, suspension
):
    await hall(hass, room_engine)
    engine, _, room, calls = room_engine
    context = await depart(hass, room_engine)
    await residual_on(hass, context)
    freezer.move_to(dt_util.utcnow() + timedelta(seconds=139))
    if suspension == "manual":
        room["manual_control"] = {"mode": "identified", "duration": 7200, "inputs": []}
        await engine.async_manual_hold()
    elif suspension == "editing":
        await engine.async_begin_edit("user")
    else:
        await engine.async_set_mode("automation", False)
    calls.clear()
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert not calls
