"""Lamp reports are state information, never an automation suspension."""

from datetime import timedelta

import pytest
from homeassistant.core import Context
from homeassistant.util import dt as dt_util
from test_engine import enable, natural_profile, scene
from test_engine import room_engine as room_engine


@pytest.mark.parametrize("origin", ["user", "automation", "unidentified"])
@pytest.mark.parametrize(
    "power,attributes",
    [
        ("on", {"brightness": 42}),
        ("off", {}),
        ("on", {"color_temp_kelvin": 5500}),
        ("on", {"effect": "candle"}),
        (
            "on",
            {
                "color_temp_kelvin": None,
                "color_mode": "xy",
                "xy_color": (0.5267, 0.4133),
            },
        ),
    ],
)
async def test_lamp_reports_do_not_interrupt_conditional_scenes(
    hass, room_engine, origin, power, attributes
):
    engine, manager, room, calls = room_engine
    room["scenes"] = [scene(autonomous=True)]
    await engine.async_reconfigure()
    await enable(hass, engine)
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    calls.clear()
    generation = engine._generation
    context = (
        Context(user_id="user")
        if origin == "user"
        else Context(parent_id="external")
        if origin == "automation"
        else Context()
    )
    old = hass.states.get("light.one")
    hass.states.async_set(
        old.entity_id, power, {**old.attributes, **attributes}, context=context
    )
    await hass.async_block_till_done()
    assert not calls
    assert engine._generation == generation
    assert "pause_until" not in engine.status
    assert "pause_until" not in manager.runtime_state["living"]
    assert engine.is_on == any(
        hass.states.get(light).state == "on" for light in room["lights"]
    )
    hass.states.async_set("media_player.tv", "on")
    await hass.async_block_till_done()
    assert calls
    assert engine.lighting_status == {"mode": "scene", "scene_id": "cinema"}
    assert hass.states.get("light.one").attributes["brightness"] == 51


async def test_captured_late_hue_rounding_and_bahut_changes_do_not_block_natural(
    hass, freezer, room_engine
):
    engine, manager, room, calls = room_engine
    manager.config["profiles"]["day"] = natural_profile()
    room["associations"] = [{"profile_id": "day", "lights": room["lights"]}]
    await engine.async_reconfigure()
    await enable(hass, engine)
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    calls.clear()
    for seconds, brightness in [(148, 127), (4 * 3600, 131), (144, 203)]:
        freezer.move_to(dt_util.utcnow() + timedelta(seconds=seconds))
        old = hass.states.get("light.one")
        hass.states.async_set(
            old.entity_id, "on", {**old.attributes, "brightness": brightness}
        )
        await hass.async_block_till_done()
        assert "pause_until" not in engine.status
    hass.states.async_set("sun.sun", "above_horizon", {"elevation": 8, "rising": True})
    await hass.async_block_till_done()
    assert calls
    assert engine.lighting_status == {"mode": "natural", "scene_id": None}
    assert hass.states.get("light.one").attributes["color_temp_kelvin"] == 5200


async def test_hue_group_off_fallback_does_not_block_presence_return(hass, room_engine):
    engine, _, room, calls = room_engine
    room["absence_delay"] = 0
    old = hass.states.get("light.one")
    attrs = {**old.attributes, "is_hue_group": True, "entity_id": ["light.member"]}
    hass.states.async_set("light.one", "off", attrs)
    hass.states.async_set("light.member", "off", old.attributes)
    await enable(hass, engine)
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    calls.clear()
    hass.states.async_set(
        "light.one",
        "on",
        {
            **attrs,
            "color_temp_kelvin": None,
            "color_mode": "xy",
            "xy_color": (0.5267, 0.4133),
        },
    )
    hass.states.async_set("light.one", "off", attrs)
    await hass.async_block_till_done()
    assert not calls
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert calls
    assert engine.is_on
    assert "pause_until" not in engine.status


async def test_bureau_off_ack_after_8_seconds_does_not_block_next_presence(
    hass, freezer, room_engine
):
    """Replay the observed 8.357 s acknowledgement of a 2 s off transition."""
    from test_engine import advance

    engine, manager, room, calls = room_engine
    room["lights"] = ["light.one"]
    room["absence_delay"] = 0
    manager.config["transitions"]["turn_off"] = 2
    await engine.async_reconfigure()
    await enable(hass, engine)
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()

    async def delayed_off(call):
        calls.append(call)

    hass.services.async_register("light", "turn_off", delayed_off)
    calls.clear()
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    assert len(calls) == 1 and calls[0].data["transition"] == 2
    assert engine.is_on
    await advance(hass, freezer, 8.357)
    calls.clear()
    old = hass.states.get("light.one")
    hass.states.async_set(old.entity_id, "off", old.attributes, context=Context())
    await hass.async_block_till_done()
    assert not calls
    assert not engine.is_on
    assert "pause_until" not in engine.status
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert len(calls) == 1 and calls[0].service == "turn_on"
    assert engine.is_on


async def test_salon_reordered_92_66_92_feedback_keeps_conditional_scene_active(
    hass, freezer, room_engine
):
    """Replay the reported intermediate value after an initial target report."""
    from test_engine import advance

    engine, manager, room, calls = room_engine
    room["lights"] = ["light.one"]
    room["absence_delay"] = 300
    selected = scene(autonomous=True)
    selected["lights"].pop("light.two")
    room["scenes"] = [selected]
    manager.config["transitions"]["natural"] = 60
    await engine.async_reconfigure()
    await enable(hass, engine)
    assert not engine.is_on
    await engine._apply(
        {"light.one": {"state": "on", "brightness": 92}},
        "natural",
        force=True,
        reason="natural",
    )
    await hass.async_block_till_done()
    assert calls[-1].data["transition"] == 60
    assert hass.states.get("light.one").attributes["brightness"] == 92
    for elapsed, brightness in [(7.26, 66), (117 - 7.26, 92)]:
        await advance(hass, freezer, elapsed)
        calls.clear()
        old = hass.states.get("light.one")
        hass.states.async_set(
            old.entity_id,
            "on",
            {**old.attributes, "brightness": brightness},
            context=Context(),
        )
        await hass.async_block_till_done()
        assert not calls
        assert "pause_until" not in engine.status
    hass.states.async_set("media_player.tv", "on")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert hass.states.get("light.one").attributes["brightness"] == 51
    assert engine.lighting_status == {"mode": "scene", "scene_id": "cinema"}
