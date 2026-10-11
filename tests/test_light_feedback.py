"""Provider feedback must not pause presence lighting or conditional scenes."""

import pytest
from homeassistant.core import Context
from homeassistant.util import color
from test_engine import advance, enable, natural_profile, scene
from test_engine import room_engine as room_engine
from test_nightlight_engine import configured, depart


@pytest.mark.parametrize("kelvin", [2001, 2700, 4500, 5500, 6000])
async def test_hue_white_rounding_does_not_pause_or_block_tv(hass, room_engine, kelvin):
    engine, manager, room, calls = room_engine
    manager.config["profiles"]["day"] = natural_profile()
    manager.config["profiles"]["day"]["morning"]["temperature"]["high"] = kelvin
    manager.config["transitions"]["natural"] = 60
    room["associations"] = [{"profile_id": "day", "lights": room["lights"]}]
    room["scenes"] = [scene()]
    hass.states.async_set("sun.sun", "above_horizon", {"elevation": 0})
    await engine.async_reconfigure()
    await enable(hass, engine)
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()

    async def hue_feedback(call):
        calls.append(call)
        old = hass.states.get(call.data["entity_id"])
        attrs = dict(old.attributes)
        if "color_temp_kelvin" in call.data:
            # Hue receives integer mireds and reports their Kelvin equivalent,
            # which can differ by tens of Kelvin from Halo's requested white.
            attrs["color_temp_kelvin"] = color.color_temperature_mired_to_kelvin(
                color.color_temperature_kelvin_to_mired(call.data["color_temp_kelvin"])
            )
        if "brightness_pct" in call.data:
            attrs["brightness"] = round(call.data["brightness_pct"] * 255 / 100)
        hass.states.async_set(
            old.entity_id,
            "on" if call.service == "turn_on" else "off",
            attrs,
            context=Context(),
        )

    hass.services.async_register("light", "turn_on", hue_feedback)
    hass.services.async_register("light", "turn_off", hue_feedback)
    hass.states.async_set("sun.sun", "above_horizon", {"elevation": 10})
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is None
    assert all(hass.states.get(entity_id).state == "on" for entity_id in room["lights"])
    assert calls[-1].data["transition"] == 60

    hass.states.async_set("media_player.tv", "on")
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is None
    assert engine.lighting_status == {"mode": "scene", "scene_id": "cinema"}
    assert hass.states.get("light.one").attributes["brightness"] == 51
    assert hass.states.get("light.two").state == "off"


async def test_contextless_return_from_nightlight_with_empty_off_attributes(
    hass, freezer, room_engine
):
    engine, _, room, calls = room_engine
    await configured(hass, room_engine)
    await depart(hass, freezer, room_engine)
    old = hass.states.get("light.two")
    # Home Assistant removes brightness and color values from an off lamp.
    hass.states.async_set(
        old.entity_id,
        "off",
        {**old.attributes, "brightness": None, "color_temp_kelvin": None},
        context=old.context,
    )
    await hass.async_block_till_done()
    calls.clear()

    async def contextless_feedback(call):
        calls.append(call)
        old = hass.states.get(call.data["entity_id"])
        attrs = {
            **old.attributes,
            "brightness": round(call.data["brightness_pct"] * 255 / 100),
        }
        hass.states.async_set(old.entity_id, "on", attrs, context=Context())

    hass.services.async_register("light", "turn_on", contextless_feedback)
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is None
    assert {call.data["entity_id"] for call in calls} == set(room["lights"])
    assert hass.states.get("light.two").attributes["brightness"] == 230


@pytest.mark.parametrize(
    "context", [Context(user_id="user"), Context(parent_id="other-automation")]
)
async def test_identified_intervention_wins_over_matching_light_feedback(
    hass, room_engine, context
):
    engine, manager, room, _ = room_engine
    room["base"] = {"light.one": {"state": "on", "brightness_pct": 80}}
    manager.config["transitions"]["turn_on"] = 30
    await enable(hass, engine)
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    old = hass.states.get("light.one")
    hass.states.async_set(
        old.entity_id, "on", {**old.attributes, "brightness": 203}, context=context
    )
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is not None


@pytest.mark.parametrize(
    "desired,feedback",
    [
        ({"brightness": 128}, {"brightness": 128}),
        ({"color_temp_kelvin": 2700}, {"color_temp_kelvin": 2702}),
        ({"rgb_color": [120, 40, 10]}, {"rgb_color": [120, 40, 10]}),
    ],
)
async def test_contextless_first_on_accepts_only_matching_missing_attributes(
    hass, room_engine, desired, feedback
):
    engine, _, room, _ = room_engine
    old = hass.states.get("light.one")
    attrs = {
        **old.attributes,
        "supported_color_modes": ["color_temp", "rgb"],
        "brightness": None,
        "color_temp_kelvin": None,
        "rgb_color": None,
    }
    hass.states.async_set(old.entity_id, "off", attrs)
    await hass.async_block_till_done()
    await engine.async_resume()
    room["base"] = {"light.one": {"state": "on", **desired}}

    async def report_target(call):
        old = hass.states.get(call.data["entity_id"])
        hass.states.async_set(old.entity_id, "on", {**old.attributes, **feedback})

    hass.services.async_register("light", "turn_on", report_target)
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is None


async def test_missing_previous_value_does_not_accept_unrelated_feedback(
    hass, room_engine
):
    engine, _, room, _ = room_engine
    old = hass.states.get("light.one")
    hass.states.async_set(old.entity_id, "off", {**old.attributes, "brightness": None})
    await hass.async_block_till_done()
    await engine.async_resume()
    room["base"] = {"light.one": {"state": "on", "brightness_pct": 80}}

    async def report_other_target(call):
        old = hass.states.get(call.data["entity_id"])
        hass.states.async_set(old.entity_id, "on", {**old.attributes, "brightness": 10})

    hass.services.async_register("light", "turn_on", report_other_target)
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is not None


@pytest.mark.parametrize("elapsed,kelvin", [(1, 4500), (6, 4001)])
async def test_white_override_or_late_feedback_still_pauses(
    hass, freezer, room_engine, elapsed, kelvin
):
    engine, _, room, _ = room_engine
    room["base"] = {"light.one": {"state": "on", "color_temp_kelvin": 4000}}
    await enable(hass, engine)
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    await advance(hass, freezer, elapsed)
    old = hass.states.get("light.one")
    hass.states.async_set(
        old.entity_id, "on", {**old.attributes, "color_temp_kelvin": kelvin}
    )
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is not None
