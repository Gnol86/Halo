"""Validate opt-in controls independently from device feedback and old pauses."""

from copy import deepcopy

import pytest

from custom_components.halo.models import validate_config, validate_identified_hold


def room(**changes):
    return validate_config({"rooms": {"living": changes}})["rooms"]["living"]


def enabled_room():
    return room(
        lights=["light.lamp"],
        automation_enabled=True,
        manual_control={"mode": "identified", "inputs": ["event.remote"]},
    )


def hold(**changes):
    return {
        "version": 1,
        "started_at": 1000,
        "until": 2800,
        "source": "user",
        "entity_id": "light.lamp",
        "command": "light.turn_on",
        "context_id": "context",
    } | changes


def test_manual_detection_defaults_off_without_aliasing_or_legacy_activation():
    original = {"rooms": {"living": {"manual_pause": 7200}}}
    result = validate_config(original)["rooms"]["living"]
    assert result["manual_control"] == {
        "mode": "disabled",
        "duration": 7200,
        "inputs": [],
    }
    assert "manual_pause" not in result
    result["manual_control"]["inputs"].append("event.remote")
    assert room()["manual_control"]["inputs"] == []
    assert original == {"rooms": {"living": {"manual_pause": 7200}}}


@pytest.mark.parametrize(
    "settings",
    [
        None,
        {"mode": "extended"},
        {"mode": True},
        {"duration": 0},
        {"duration": 0.5},
        {"duration": -1},
        {"duration": True},
        {"duration": "30"},
        {"duration": float("nan")},
        {"duration": float("inf")},
        {"duration": 604801},
        {"inputs": "event.remote"},
        {"inputs": ["event.remote", "event.remote"]},
        {"inputs": ["light.lamp"]},
        {"inputs": ["binary_sensor.remote"]},
        {"unexpected": True},
    ],
)
def test_manual_detection_rejects_ambiguous_or_invalid_configuration(settings):
    with pytest.raises(ValueError):
        room(manual_control=settings)


@pytest.mark.parametrize("duration", [1, 1.5, 1800, 604800])
def test_manual_duration_is_explicit_and_bounded(duration):
    settings = {
        "mode": "identified",
        "duration": duration,
        "inputs": ["event.remote", "input_button.wall"],
    }
    assert room(manual_control=settings)["manual_control"] == settings


def test_default_duration_does_not_replace_an_existing_explicit_setting():
    existing = room(manual_control={"mode": "identified", "duration": 1800})
    assert validate_config({"rooms": {"living": existing}})["rooms"]["living"][
        "manual_control"
    ] == {"mode": "identified", "duration": 1800, "inputs": []}


def test_new_hold_preserves_absolute_deadline_and_is_detached():
    original = hold()
    result = validate_identified_hold(original, enabled_room(), now=1500)
    assert result == original
    assert result["until"] == 2800
    result["until"] = 3000
    assert original["until"] == 2800


def test_subsecond_hold_does_not_restore():
    assert (
        validate_identified_hold(hold(until=1000.5), enabled_room(), now=1000.25)
        is None
    )


@pytest.mark.parametrize(
    "value",
    [
        None,
        {"pause_until": 2800},
        hold(version=True),
        hold(version=2),
        hold(started_at=float("nan")),
        hold(started_at=True),
        hold(started_at=1600),
        hold(until=1500),
        hold(until=float("inf")),
        hold(until=700000),
        hold(source="unknown"),
        hold(source="input", entity_id=None),
        hold(source="input", entity_id="event.removed"),
        hold(entity_id="light.removed"),
        hold(command=""),
        hold(context_id=[]),
        hold(unexpected=True),
    ],
)
def test_old_expired_invalid_or_inapplicable_holds_do_not_restore(value):
    assert validate_identified_hold(value, enabled_room(), now=1500) is None


def test_hold_only_restores_for_the_explicitly_enabled_room_and_existing_input():
    settings = enabled_room()
    assert (
        validate_identified_hold(
            hold(source="input", entity_id="event.remote"), settings, now=1500
        )
        is not None
    )
    disabled = deepcopy(settings)
    disabled["manual_control"]["mode"] = "disabled"
    assert validate_identified_hold(hold(), disabled, now=1500) is None
    disabled = deepcopy(settings)
    disabled["automation_enabled"] = False
    assert validate_identified_hold(hold(), disabled, now=1500) is None
