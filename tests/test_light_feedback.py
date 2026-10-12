"""Provider feedback must not pause presence lighting or conditional scenes."""

import pytest
from homeassistant.components.light import LightEntityFeature
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError
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


async def reported_transition(hass, room_engine, start, target, duration=60):
    """A provider reports the target before its physical transition finishes."""
    engine, manager, _, calls = room_engine
    state = hass.states.get("light.one")
    # Establish the starting state through Halo, without a manual intervention.
    await engine._apply(
        {"light.one": {"state": "on", "brightness": 220}},
        None,
        force=True,
        reason="resume",
    )
    hass.states.async_set(
        state.entity_id,
        "on",
        {**state.attributes, **start},
        context=calls[-1].context,
    )
    await hass.async_block_till_done()
    manager.config["transitions"]["natural"] = duration
    calls.clear()
    await engine._apply(
        {"light.one": {"state": "on", **target}},
        "natural",
        force=True,
        reason="natural",
    )
    if "white" in calls[-1].data:
        state = hass.states.get("light.one")
        hass.states.async_set(
            state.entity_id,
            "on",
            {**state.attributes, "brightness": calls[-1].data["white"]},
            context=calls[-1].context,
        )
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is None


@pytest.mark.parametrize(
    "start,target,intermediate",
    [
        (
            {"brightness": 220, "color_temp_kelvin": 3010},
            {"brightness_pct": 84.5, "color_temp_kelvin": 2870},
            {"brightness": 218, "color_temp_kelvin": 2950},
        ),
        (
            {"brightness": 64, "color_temp_kelvin": 2700},
            {"brightness_pct": 80, "color_temp_kelvin": 5000},
            {"brightness": 128, "color_temp_kelvin": 4000},
        ),
        ({"brightness": 220}, {"brightness": 180}, {"brightness": 200}),
        (
            {"supported_color_modes": ["white"], "brightness": 220},
            {"white": 180},
            {"brightness": 200},
        ),
        (
            {"supported_color_modes": ["rgb"], "rgb_color": [200, 100, 20]},
            {"rgb_color": [100, 50, 10]},
            {"rgb_color": [150, 75, 15]},
        ),
        (
            {"supported_color_modes": ["rgbw"], "rgbw_color": [200, 100, 20, 100]},
            {"rgbw_color": [100, 50, 10, 50]},
            {"rgbw_color": [150, 75, 15, 75]},
        ),
        (
            {
                "supported_color_modes": ["rgbww"],
                "rgbww_color": [200, 100, 20, 100, 80],
            },
            {"rgbww_color": [100, 50, 10, 50, 40]},
            {"rgbww_color": [150, 75, 15, 75, 60]},
        ),
        (
            {"supported_color_modes": ["hs"], "hs_color": [40, 80]},
            {"hs_color": [80, 40]},
            {"hs_color": [60, 60]},
        ),
        (
            {"supported_color_modes": ["xy"], "xy_color": [0.5, 0.4]},
            {"xy_color": [0.3, 0.3]},
            {"xy_color": [0.4, 0.35]},
        ),
    ],
    ids=[
        "natural-dimming",
        "natural-brightening",
        "brightness",
        "white",
        "rgb",
        "rgbw",
        "rgbww",
        "hs",
        "xy",
    ],
)
async def test_intermediate_feedback_after_target_does_not_pause(
    hass, freezer, room_engine, start, target, intermediate
):
    engine, _, _, calls = room_engine
    await reported_transition(hass, room_engine, start, target)
    final_state = hass.states.get("light.one")
    # HA light entities stop retaining command context after five seconds.
    for values in (intermediate, dict(final_state.attributes), intermediate):
        await advance(hass, freezer, 7)
        hass.states.async_set(
            "light.one", "on", {**final_state.attributes, **values}, context=Context()
        )
        await hass.async_block_till_done()
        assert engine.status["pause_until"] is None
    assert len(calls) == 1


@pytest.mark.parametrize("origin", ["user", "automation"])
@pytest.mark.parametrize(
    "state,values",
    [
        ("on", {"brightness": 218}),
        ("on", {"color_temp_kelvin": 2950}),
        ("on", {"effect": "candle"}),
        ("off", {}),
    ],
    ids=["brightness", "white-temperature", "effect", "turn-off"],
)
async def test_identified_manual_action_during_transition_still_pauses(
    hass, freezer, room_engine, origin, state, values
):
    engine, _, _, _ = room_engine
    await reported_transition(
        hass,
        room_engine,
        {"brightness": 220, "color_temp_kelvin": 3010},
        {"brightness_pct": 84.5, "color_temp_kelvin": 2870},
    )
    await advance(hass, freezer, 7)
    context = (
        Context(user_id="user")
        if origin == "user"
        else Context(parent_id="foreign-automation")
    )
    old = hass.states.get("light.one")
    hass.states.async_set(
        old.entity_id, state, {**old.attributes, **values}, context=context
    )
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is not None


@pytest.mark.parametrize(
    "values,elapsed",
    [
        ({"brightness": 245}, 7),
        ({"brightness": 180}, 7),
        ({"color_temp_kelvin": 4000}, 7),
        ({"color_temp_kelvin": 2500}, 7),
        ({"effect": "candle"}, 7),
        ({"brightness": 218}, 65),
        ({"brightness": 218}, 66),
    ],
    ids=["too-bright", "too-dim", "too-cool", "too-warm", "effect", "deadline", "late"],
)
async def test_unidentified_override_or_expired_transition_still_pauses(
    hass, freezer, room_engine, values, elapsed
):
    engine, _, _, _ = room_engine
    await reported_transition(
        hass,
        room_engine,
        {"brightness": 220, "color_temp_kelvin": 3010},
        {"brightness_pct": 84.5, "color_temp_kelvin": 2870},
    )
    await advance(hass, freezer, elapsed)
    old = hass.states.get("light.one")
    hass.states.async_set(
        old.entity_id, "on", {**old.attributes, **values}, context=Context()
    )
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is not None


@pytest.mark.parametrize(
    "duration,supports_transition", [(None, True), (0, True), (60, False)]
)
async def test_no_effective_transition_does_not_hide_intermediate_manual_value(
    hass, room_engine, duration, supports_transition
):
    engine, _, _, calls = room_engine
    await reported_transition(
        hass,
        room_engine,
        {
            "brightness": 220,
            "supported_features": LightEntityFeature.TRANSITION
            if supports_transition
            else 0,
        },
        {"brightness": 180},
        duration,
    )
    assert not calls[-1].data.get("transition")
    old = hass.states.get("light.one")
    hass.states.async_set(
        old.entity_id, "on", {**old.attributes, "brightness": 200}, context=Context()
    )
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is not None


async def test_manual_intervention_invalidates_old_transition_for_later_feedback(
    hass, freezer, room_engine
):
    engine, _, _, _ = room_engine
    await reported_transition(
        hass, room_engine, {"brightness": 220}, {"brightness": 180}
    )
    old = hass.states.get("light.one")
    hass.states.async_set(
        old.entity_id,
        "on",
        {**old.attributes, "brightness": 210},
        context=Context(user_id="user"),
    )
    await hass.async_block_till_done()
    first_pause = engine.status["pause_until"]
    assert first_pause is not None
    await advance(hass, freezer, 7)
    hass.states.async_set(
        old.entity_id, "on", {**old.attributes, "brightness": 200}, context=Context()
    )
    await hass.async_block_till_done()
    assert engine.status["pause_until"] > first_pause


async def test_new_command_replaces_old_transition_bounds(hass, freezer, room_engine):
    engine, _, _, _ = room_engine
    await reported_transition(
        hass, room_engine, {"brightness": 220}, {"brightness": 180}
    )
    await engine._apply(
        {"light.one": {"state": "on", "brightness": 100}},
        "natural",
        reason="natural",
    )
    await hass.async_block_till_done()
    await advance(hass, freezer, 7)
    old = hass.states.get("light.one")
    hass.states.async_set(
        old.entity_id, "on", {**old.attributes, "brightness": 150}, context=Context()
    )
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is None
    hass.states.async_set(
        old.entity_id, "on", {**old.attributes, "brightness": 210}, context=Context()
    )
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is not None


async def test_failed_command_does_not_hide_a_manual_change(hass, freezer, room_engine):
    engine, _, _, _ = room_engine
    await reported_transition(
        hass, room_engine, {"brightness": 220}, {"brightness": 180}
    )

    async def fail(call):
        raise HomeAssistantError("provider unavailable")

    hass.services.async_register("light", "turn_on", fail)
    await engine._apply(
        {"light.one": {"state": "on", "brightness": 100}},
        "natural",
        reason="natural",
    )
    await advance(hass, freezer, 7)
    old = hass.states.get("light.one")
    hass.states.async_set(
        old.entity_id, "on", {**old.attributes, "brightness": 150}, context=Context()
    )
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is not None


async def test_fading_off_accepts_reordered_brightness_but_manual_on_wins(
    hass, freezer, room_engine
):
    engine, manager, _, calls = room_engine
    await reported_transition(
        hass, room_engine, {"brightness": 220}, {"brightness": 220}
    )
    manager.config["transitions"]["turn_off"] = 60

    async def begin_fade(call):
        calls.append(call)
        old = hass.states.get(call.data["entity_id"])
        hass.states.async_set(
            old.entity_id,
            "on",
            {**old.attributes, "brightness": 2},
            context=call.context,
        )

    hass.services.async_register("light", "turn_off", begin_fade)
    await engine._apply({"light.one": {"state": "off"}}, "turn_off", reason="absence")
    await hass.async_block_till_done()
    await advance(hass, freezer, 7)
    old = hass.states.get("light.one")
    hass.states.async_set(
        old.entity_id, "on", {**old.attributes, "brightness": 100}, context=Context()
    )
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is None
    hass.states.async_set(
        old.entity_id, "off", {**old.attributes, "brightness": None}, context=Context()
    )
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is None
    # A new physical turn-on cannot be hidden by the preceding off transition.
    hass.states.async_set(
        old.entity_id, "on", {**old.attributes, "brightness": 100}, context=Context()
    )
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is not None


async def test_contextless_manual_off_interrupts_a_transition(hass, room_engine):
    engine, _, _, _ = room_engine
    await reported_transition(
        hass, room_engine, {"brightness": 220}, {"brightness": 180}
    )
    old = hass.states.get("light.one")
    hass.states.async_set(
        old.entity_id, "off", {**old.attributes, "brightness": None}, context=Context()
    )
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is not None


async def test_feedback_does_not_extend_transition_deadline(hass, freezer, room_engine):
    engine, _, _, _ = room_engine
    await reported_transition(
        hass, room_engine, {"brightness": 220}, {"brightness": 180}
    )
    await advance(hass, freezer, 64)
    old = hass.states.get("light.one")
    hass.states.async_set(
        old.entity_id, "on", {**old.attributes, "brightness": 200}, context=Context()
    )
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is None
    await advance(hass, freezer, 1)
    hass.states.async_set(
        old.entity_id, "on", {**old.attributes, "brightness": 201}, context=Context()
    )
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is not None


async def test_missing_departure_value_does_not_widen_after_first_report(
    hass, room_engine
):
    engine, _, _, _ = room_engine
    await reported_transition(
        hass, room_engine, {"brightness": None}, {"brightness": 180}
    )
    old = hass.states.get("light.one")
    hass.states.async_set(
        old.entity_id, "on", {**old.attributes, "brightness": 140}, context=Context()
    )
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is not None


@pytest.mark.parametrize(
    "mode,attribute,start,target,manual",
    [
        ("rgb", "rgb_color", [200, 100, 20], [100, 50, 10], [20, 20, 200]),
        (
            "rgbw",
            "rgbw_color",
            [200, 100, 20, 100],
            [100, 50, 10, 50],
            [150, 75, 15, 200],
        ),
        (
            "rgbww",
            "rgbww_color",
            [200, 100, 20, 100, 80],
            [100, 50, 10, 50, 40],
            [150, 75, 15, 75, 200],
        ),
        ("hs", "hs_color", [40, 80], [80, 40], [180, 60]),
        ("xy", "xy_color", [0.5, 0.4], [0.3, 0.3], [0.1, 0.1]),
    ],
)
async def test_physical_color_override_outside_transition_still_pauses(
    hass, freezer, room_engine, mode, attribute, start, target, manual
):
    engine, _, _, _ = room_engine
    await reported_transition(
        hass,
        room_engine,
        {"supported_color_modes": [mode], attribute: start},
        {attribute: target},
    )
    await advance(hass, freezer, 7)
    old = hass.states.get("light.one")
    hass.states.async_set(
        old.entity_id, "on", {**old.attributes, attribute: manual}, context=Context()
    )
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is not None
