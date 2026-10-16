"""Hue aggregate reports must be checked against their physical members."""

from unittest.mock import AsyncMock

import pytest
from homeassistant.core import Context
from test_engine import advance
from test_engine import room_engine as room_engine


async def group_command(hass, room_engine, target, transition=2, members=1):
    engine, manager, _, _ = room_engine
    # Establish an on group through a command owned by Halo.
    await engine._apply(
        {"light.one": {"state": "on", "brightness": 242, "color_temp_kelvin": 4491}},
        None,
        reason="resume",
    )
    await hass.async_block_till_done()
    group = hass.states.get("light.one")
    ids = [f"light.member_{index}" for index in range(members)]
    for entity_id in ids:
        hass.states.async_set(entity_id, "on", dict(group.attributes))
    hass.states.async_set(
        group.entity_id,
        "on",
        {**group.attributes, "is_hue_group": True, "entity_id": ids},
        context=group.context,
    )
    await hass.async_block_till_done()
    # Hue delivers member and aggregate feedback independently of the service.
    hass.services.async_register("light", "turn_off", AsyncMock())
    hass.services.async_register("light", "turn_on", AsyncMock())
    manager.config["transitions"]["natural"] = transition
    await engine._apply({"light.one": target}, "natural", reason="natural", force=True)
    await hass.async_block_till_done()
    return engine, ids


async def report(hass, entity_id, state, changes, context=None):
    old = hass.states.get(entity_id)
    hass.states.async_set(
        entity_id, state, {**old.attributes, **changes}, context=context or Context()
    )
    await hass.async_block_till_done()


@pytest.mark.parametrize("elapsed", [5.187, 8.23])
async def test_wc_group_color_fallback_after_member_off_does_not_pause(
    hass, freezer, room_engine, elapsed
):
    """October 16: member off, group still on and changing color_temp to xy."""
    engine, members = await group_command(hass, room_engine, {"state": "off"})
    await advance(hass, freezer, elapsed)
    await report(hass, members[0], "off", {"brightness": None, "color_mode": None})
    await report(
        hass,
        "light.one",
        "on",
        {
            "color_temp_kelvin": None,
            "color_mode": "xy",
            "xy_color": (0.5267, 0.4133),
        },
    )
    assert engine.status["pause_until"] is None
    await advance(hass, freezer, 0.864)
    await report(hass, "light.one", "off", {"brightness": None, "color_mode": None})
    assert engine.status["pause_until"] is None


async def test_late_group_average_accepts_only_members_reaching_the_target(
    hass, freezer, room_engine
):
    engine, members = await group_command(
        hass, room_engine, {"state": "on", "color_temp_kelvin": 4405}, 60, 3
    )
    await advance(hass, freezer, 133)
    for index, entity_id in enumerate(members):
        await report(hass, entity_id, "on", {"color_temp_kelvin": 4405})
        average = round((4405 * (index + 1) + 4491 * (2 - index)) / 3)
        await report(hass, "light.one", "on", {"color_temp_kelvin": average})
        assert engine.status["pause_until"] is None


async def test_late_group_member_change_cannot_hide_inside_aggregate_rounding(
    hass, freezer, room_engine
):
    engine, members = await group_command(
        hass, room_engine, {"state": "on", "brightness": 242}, 60, 3
    )
    await advance(hass, freezer, 133)
    # The average moves by just one, but the actual bulb moved by four.
    await report(hass, members[0], "on", {"brightness": 238})
    await report(hass, "light.one", "on", {"brightness": 241})
    assert engine.status["pause_until"] is not None


@pytest.mark.parametrize("origin", ["user", "automation"])
@pytest.mark.parametrize("identified_on", ["group", "member"])
async def test_identified_action_wins_over_group_feedback(
    hass, freezer, room_engine, origin, identified_on
):
    engine, members = await group_command(hass, room_engine, {"state": "off"})
    await advance(hass, freezer, 5.187)
    foreign = (
        Context(user_id="user") if origin == "user" else Context(parent_id="other")
    )
    await report(
        hass,
        members[0],
        "off",
        {"brightness": None},
        foreign if identified_on == "member" else None,
    )
    await report(
        hass,
        "light.one",
        "on",
        {"color_temp_kelvin": None, "color_mode": "xy", "xy_color": (0.5267, 0.4133)},
        foreign if identified_on == "group" else None,
    )
    assert engine.status["pause_until"] is not None


@pytest.mark.parametrize("member_state", ["on", "unavailable", "unknown", None])
async def test_group_color_change_is_not_ignored_without_confirmed_off_members(
    hass, freezer, room_engine, member_state
):
    engine, members = await group_command(hass, room_engine, {"state": "off"})
    await advance(hass, freezer, 5.187)
    if member_state is None:
        hass.states.async_remove(members[0])
    else:
        await report(hass, members[0], member_state, {})
    await report(
        hass,
        "light.one",
        "on",
        {"color_temp_kelvin": None, "color_mode": "xy", "xy_color": (0.5267, 0.4133)},
    )
    assert engine.status["pause_until"] is not None


async def test_group_feedback_cannot_hide_new_physical_turn_on(
    hass, freezer, room_engine
):
    engine, members = await group_command(hass, room_engine, {"state": "off"})
    await report(hass, members[0], "off", {"brightness": None})
    await report(hass, "light.one", "off", {"brightness": None})
    assert engine.status["pause_until"] is None
    await advance(hass, freezer, 8)
    await report(hass, members[0], "on", {"brightness": 242})
    await report(hass, "light.one", "on", {"brightness": 242})
    assert engine.status["pause_until"] is not None


async def test_group_member_expectations_are_replaced_by_new_command(
    hass, freezer, room_engine
):
    engine, members = await group_command(
        hass, room_engine, {"state": "on", "color_temp_kelvin": 4405}, 60, 3
    )
    await advance(hass, freezer, 133)
    await engine._apply(
        {"light.one": {"state": "on", "color_temp_kelvin": 3000}}, None, reason="resume"
    )
    await report(hass, members[0], "on", {"color_temp_kelvin": 4405})
    await report(hass, "light.one", "on", {"color_temp_kelvin": 4462})
    assert engine.status["pause_until"] is not None


async def test_group_snapshot_does_not_treat_old_user_context_as_new_action(
    hass, freezer, room_engine
):
    engine, members = await group_command(
        hass, room_engine, {"state": "on", "color_temp_kelvin": 4405}, 60, 3
    )
    old = hass.states.get(members[1])
    hass.states.async_set(
        members[1], "on", old.attributes, context=Context(user_id="old")
    )
    await advance(hass, freezer, 133)
    await report(hass, members[0], "on", {"color_temp_kelvin": 4405})
    await report(hass, "light.one", "on", {"color_temp_kelvin": 4462})
    assert engine.status["pause_until"] is None


async def test_member_feedback_does_not_excuse_unrelated_group_change(
    hass, freezer, room_engine
):
    engine, members = await group_command(
        hass, room_engine, {"state": "on", "color_temp_kelvin": 4405}, 60, 3
    )
    await advance(hass, freezer, 133)
    await report(hass, members[0], "on", {"color_temp_kelvin": 4405})
    # The temperature is the expected average, but the brightness is not.
    await report(
        hass, "light.one", "on", {"color_temp_kelvin": 4462, "brightness": 180}
    )
    assert engine.status["pause_until"] is not None


async def test_group_turn_on_accepts_matching_physical_members(hass, room_engine):
    engine, members = await group_command(hass, room_engine, {"state": "off"})
    await report(hass, members[0], "off", {"brightness": None})
    await report(hass, "light.one", "off", {"brightness": None})
    await engine._apply(
        {"light.one": {"state": "on", "brightness": 180}}, None, reason="presence"
    )
    await report(hass, members[0], "on", {"brightness": 180})
    await report(hass, "light.one", "on", {"brightness": 180})
    assert engine.status["pause_until"] is None


async def test_group_feedback_keeps_final_target_tolerance_anchored(
    hass, freezer, room_engine
):
    engine, members = await group_command(
        hass, room_engine, {"state": "on", "brightness": 240}, 60
    )
    await advance(hass, freezer, 133)
    for value in (240, 239):
        await report(hass, members[0], "on", {"brightness": value})
        await report(hass, "light.one", "on", {"brightness": value})
        assert engine.status["pause_until"] is None
    await report(hass, members[0], "on", {"brightness": 238})
    await report(hass, "light.one", "on", {"brightness": 238})
    assert engine.status["pause_until"] is not None


async def test_group_owned_acknowledgment_advances_member_observation(
    hass, freezer, room_engine
):
    engine, members = await group_command(
        hass, room_engine, {"state": "on", "color_temp_kelvin": 4405}, 60, 3
    )
    own_id = next(reversed(engine._own_contexts))
    own = Context(id=own_id, user_id="halo-caller")
    await report(hass, members[0], "on", {"color_temp_kelvin": 4405}, own)
    await report(hass, "light.one", "on", {"color_temp_kelvin": 4462}, own)
    await advance(hass, freezer, 133)
    await report(hass, members[1], "on", {"color_temp_kelvin": 4405})
    await report(hass, "light.one", "on", {"color_temp_kelvin": 4434})
    assert engine.status["pause_until"] is None
