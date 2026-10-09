"""Reject configurations that could dispatch conflicting or invalid commands."""

from copy import deepcopy

import pytest

from custom_components.halo.models import (
    default_config,
    validate_condition,
    validate_config,
    validate_lamp_states,
)


def configuration():
    config = default_config()
    config["rooms"] = {"living": {"lights": ["light.floor", "light.ceiling"]}}
    return config


def test_defaults_and_transition_semantics():
    config = configuration()
    config["rooms"]["living"]["transitions"] = {
        "turn_on": 0,
        "turn_off": None,
        "scene": "inherit",
    }
    room = validate_config(config)["rooms"]["living"]
    assert room["automation_enabled"] is False
    assert room["allow_off_during_pause"] is True
    assert room["absence_delay"] == 120
    assert room["manual_pause"] == 900
    assert room["transitions"] == {
        "turn_on": 0,
        "turn_off": None,
        "scene": "inherit",
        "natural": "inherit",
        "lux_on": "inherit",
    }
    assert "absence_delay" not in config["rooms"]["living"]


@pytest.mark.parametrize("bad", [-1, float("inf"), float("nan"), True, "10"])
def test_reject_invalid_durations(bad):
    config = configuration()
    config["rooms"]["living"]["absence_delay"] = bad
    with pytest.raises(ValueError):
        validate_config(config)


def test_unique_members_and_scene_scope():
    config = configuration()
    config["rooms"]["bedroom"] = {"lights": ["light.floor"]}
    with pytest.raises(ValueError, match="one Halo room"):
        validate_config(config)
    with pytest.raises(ValueError, match="outside its room"):
        validate_lamp_states({"light.outside": {"state": "on"}}, ["light.floor"])


def test_lux_sensor_requires_explicit_threshold():
    config = configuration()
    config["rooms"]["living"]["lux_entity_id"] = "sensor.lux"
    with pytest.raises(ValueError, match="lux_threshold"):
        validate_config(config)
    config["rooms"]["living"]["lux_threshold"] = 20
    assert validate_config(config)["rooms"]["living"]["lux_threshold"] == 20


def test_solar_bounds_precision_and_profile_associations():
    config = configuration()
    config["profiles"] = {
        "warm": {
            "id": "warm",
            "name": "Mon profil",
            "linked": True,
            "morning": {
                "brightness": {
                    "low_elevation": -6.25,
                    "high_elevation": 40.5,
                    "low": 20,
                    "high": 100,
                },
                "temperature": {
                    "low_elevation": -8.1,
                    "high_elevation": 20.2,
                    "low": 2200,
                    "high": 5500,
                },
            },
        }
    }
    group = {"profile_id": "warm", "lights": ["light.floor"], "brightness_offset": -30}
    config["rooms"]["living"]["associations"] = [group]
    normalized = validate_config(config)
    assert (
        normalized["profiles"]["warm"]["morning"]["brightness"]["low_elevation"]
        == -6.25
    )
    config["rooms"]["living"]["associations"].append(deepcopy(group))
    with pytest.raises(ValueError, match="one natural profile"):
        validate_config(config)
    config["rooms"]["living"]["associations"].pop()
    config["profiles"]["warm"]["morning"]["brightness"]["high_elevation"] = -6.25
    with pytest.raises(ValueError, match="ordered"):
        validate_config(config)


@pytest.mark.parametrize(
    "node",
    [
        {"type": "template", "value": "{{ arbitrary_code }}"},
        {"type": "not"},
        {"type": "and", "conditions": []},
        {"type": "numeric", "entity_id": "sensor.lux"},
        {"type": "time", "after": "25:00", "before": "12:00"},
    ],
)
def test_invalid_conditions(node):
    with pytest.raises(ValueError):
        validate_condition(node)


def test_color_and_service_data_validation():
    with pytest.raises(ValueError, match="one color"):
        validate_lamp_states(
            {
                "light.floor": {
                    "state": "on",
                    "color_temp_kelvin": 3000,
                    "rgb_color": [255, 0, 0],
                }
            },
            ["light.floor"],
        )
    with pytest.raises(ValueError, match="lamp state"):
        validate_lamp_states(
            {"light.floor": {"state": "on", "entity_id": "light.outside"}},
            ["light.floor"],
        )
