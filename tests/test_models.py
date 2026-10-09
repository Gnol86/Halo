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
    assert room["absence_delay"] == 0
    assert room["manual_pause"] == 7200
    assert room["transitions"] == {
        "turn_on": 0,
        "turn_off": None,
        "scene": "inherit",
        "natural": "inherit",
        "lux_on": "inherit",
    }
    assert "absence_delay" not in config["rooms"]["living"]


def test_new_global_transition_defaults_are_independent():
    expected = {"turn_on": 0, "lux_on": 10, "natural": 60, "scene": 10, "turn_off": 2}
    assert default_config()["transitions"] == expected
    assert validate_config({"transitions": {}})["transitions"] == expected
    changed = default_config()
    changed["transitions"]["natural"] = None
    assert default_config()["transitions"] == expected


def test_presence_return_default_normalizes_older_configs():
    old = {"rooms": {"living": {"lights": ["light.floor"]}}}
    assert default_config()["presence_return_window"] == 30
    assert validate_config(old)["presence_return_window"] == 30
    assert "presence_return_window" not in old


@pytest.mark.parametrize("value", [0, 30, 45.5, 604800])
def test_presence_return_window_preserves_explicit_values(value):
    config = configuration() | {"presence_return_window": value}
    assert validate_config(config)["presence_return_window"] == value


@pytest.mark.parametrize(
    "value", [-1, 604800.1, float("inf"), float("nan"), True, "30", None]
)
def test_presence_return_window_rejects_invalid_values(value):
    with pytest.raises(ValueError, match="presence_return_window"):
        validate_config(configuration() | {"presence_return_window": value})


def test_normalization_preserves_existing_durations_and_explicit_omissions():
    config = configuration()
    transitions = {
        "turn_on": None,
        "lux_on": 0,
        "natural": None,
        "scene": 3.5,
        "turn_off": 0,
    }
    config["transitions"] = transitions
    config["rooms"]["living"].update(
        absence_delay=120,
        manual_pause=900,
        transitions={"turn_on": None, "lux_on": 0, "natural": 4.25},
    )
    normalized = validate_config(config)
    assert normalized["transitions"] == transitions
    room = normalized["rooms"]["living"]
    assert room["absence_delay"] == 120
    assert room["manual_pause"] == 900
    assert room["transitions"] == {
        "turn_on": None,
        "lux_on": 0,
        "natural": 4.25,
        "scene": "inherit",
        "turn_off": "inherit",
    }


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


@pytest.mark.parametrize(
    "settings",
    [
        {"brightness": 123, "effect": "candle", "color_mode": "brightness"},
        {"rgbw_color": [20, 30, 40, 50], "color_mode": "rgbw"},
        {"rgbww_color": [20, 30, 40, 50, 60], "color_mode": "rgbww"},
        {"brightness": 87, "color_mode": "white"},
        {"white": 87},
        {"effect": "off"},
    ],
)
def test_native_light_settings_are_preserved(settings):
    value = {"light.floor": {"state": "on", **settings}}
    assert validate_lamp_states(value, ["light.floor"]) == value


@pytest.mark.parametrize(
    "settings",
    [
        {"effect": ["candle"]},
        {"brightness": 256},
        {"brightness": 123.5},
        {"brightness": 123, "brightness_pct": 50},
        {"rgbw_color": [1, 2, 3]},
        {"rgbww_color": [1, 2, 3, 4, float("nan")]},
        {"color_mode": "unknown"},
        {"color_mode": "white", "rgb_color": [1, 2, 3]},
        {"white": True},
        {"effect_list": ["candle", "off"]},
        {"rgbw_color": [1, 2, 3, 4], "rgb_color": [1, 2, 3]},
    ],
)
def test_native_light_validation_rejects_ambiguous_or_read_only_data(settings):
    with pytest.raises(ValueError):
        validate_lamp_states(
            {"light.floor": {"state": "on", **settings}}, ["light.floor"]
        )
