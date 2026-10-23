"""Presence recovery preserves an identified command already in progress."""

import asyncio
from datetime import timedelta

from homeassistant.core import Context
from homeassistant.util import dt as dt_util
from test_engine import enable
from test_engine import room_engine as room_engine


async def test_presence_return_does_not_interrupt_identified_turn_on(
    hass, freezer, hass_admin_user, room_engine
):
    engine, _, room, calls = room_engine
    room.update(
        absence_delay=0,
        lux_entity_id=None,
        lighting_fallback={"mode": "always", "turn_off": False},
        manual_control={"mode": "identified", "duration": 7200, "inputs": []},
    )
    await engine.async_reconfigure()
    await enable(hass, engine)
    freezer.move_to(dt_util.utcnow() + timedelta(seconds=139))
    calls.clear()
    started, release = asyncio.Event(), asyncio.Event()

    async def slow_on(call):
        calls.append(call)
        if not started.is_set():
            started.set()
            await release.wait()
        old = hass.states.get(call.data["entity_id"])
        hass.states.async_set(old.entity_id, "on", old.attributes, context=call.context)

    hass.services.async_register("light", "turn_on", slow_on)
    command = asyncio.create_task(
        engine.async_turn_on(Context(user_id=hass_admin_user.id))
    )
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        hold = engine.status["manual_hold"]
        assert hold is not None and hold["command"] == "turn_on"
        hass.states.async_set("binary_sensor.presence", "on")
        # Deliver the event while the first light service holds the engine lock.
        await asyncio.sleep(0)
        await asyncio.sleep(0)
    finally:
        release.set()
        await command
    await hass.async_block_till_done()

    assert [(call.service, call.data["entity_id"]) for call in calls] == [
        ("turn_on", "light.one"),
        ("turn_on", "light.two"),
    ]
    assert all(hass.states.get(entity_id).state == "on" for entity_id in room["lights"])
    assert engine.status["manual_hold"] == hold
    assert engine.status["reason"] == "manual_hold"
