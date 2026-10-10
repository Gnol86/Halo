"""Adversarial room checks from the complete local acceptance review."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from test_engine import enable, scene
from test_engine import room_engine as room_engine


@pytest.mark.parametrize("elapsed,remaining", [(8, 2), (12, 0)])
async def test_slow_service_does_not_extend_an_existing_absence_deadline(
    hass, freezer, room_engine, elapsed, remaining
):
    """A service that consumes eight seconds leaves two of a ten-second timer."""
    engine, _, room, calls = room_engine
    room["absence_delay"] = 10
    room["scenes"] = [scene(autonomous=True)]
    hass.states.async_set("media_player.tv", "on")
    await engine.async_reconfigure()
    await hass.async_block_till_done()

    async def slow_on(call):
        calls.append(call)
        if len(calls) == 1:
            freezer.move_to(dt_util.utcnow() + timedelta(seconds=elapsed))
        state = hass.states.get(call.data["entity_id"])
        hass.states.async_set(
            state.entity_id, "on", state.attributes, context=call.context
        )

    hass.services.async_register("light", "turn_on", slow_on)
    with patch("custom_components.halo.engine.async_call_later") as timer:
        # A scene permitted to turn on can run during this empty-room period.
        # Its service latency must not delay the existing timer's evaluation.
        await enable(hass, engine)
    assert timer.call_args.args[1] == remaining


async def test_one_failed_lamp_is_not_hidden_by_another_successful_lamp(
    hass, room_engine
):
    engine, _, _, calls = room_engine
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()

    async def fail_first(call):
        calls.append(call)
        if call.data["entity_id"] == "light.one":
            raise HomeAssistantError("Simulated lamp offline")
        state = hass.states.get(call.data["entity_id"])
        hass.states.async_set(
            state.entity_id, "on", state.attributes, context=call.context
        )

    hass.services.async_register("light", "turn_on", fail_first)
    await enable(hass, engine)
    assert hass.states.get("light.two").state == "on"
    assert engine.status["error"] == "Simulated lamp offline"
    # A later successful preview of a different lamp must not erase this error.
    token = await engine.async_begin_edit("owner")
    await engine.async_preview(token, {"light.two": {"state": "on"}})
    assert engine.status["error"] == "Simulated lamp offline"
    await engine.async_end_edit(token, save=True)

    async def recovered(call):
        state = hass.states.get(call.data["entity_id"])
        hass.states.async_set(
            state.entity_id, "on", state.attributes, context=call.context
        )

    hass.services.async_register("light", "turn_on", recovered)
    await engine.async_resume()
    await hass.async_block_till_done()
    assert engine.status["error"] is None
    assert hass.states.get("light.one").state == "on"


async def test_local_scene_intentionally_off_is_not_repeated_by_input_updates(
    hass, room_engine
):
    engine, _, room, calls = room_engine
    room["absence_delay"] = 0
    selected = scene()
    selected["lights"] = {"light.one": {"state": "off"}}
    room["scenes"] = [selected]
    hass.states.async_set("media_player.tv", "on")
    hass.states.async_set("binary_sensor.presence", "on")
    await engine.async_reconfigure()
    await hass.async_block_till_done()
    await enable(hass, engine)
    assert len(calls) == 1
    calls.clear()
    hass.states.async_set("sensor.lux", "40")
    hass.states.async_set("binary_sensor.presence", "on", {"battery": 75})
    await hass.async_block_till_done()
    assert not calls
    # A genuine departure still closes the scene application, so the next
    # eligible entry can apply it once again.
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    assert not calls
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert len(calls) == 1
