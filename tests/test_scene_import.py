"""Native scene conversion is detached, exact and matches HA color priorities."""

from copy import deepcopy

import pytest

from custom_components.halo.scene_import import normalize_scene_import


def convert(settings):
    return normalize_scene_import(
        {"name": "Native", "entities": {"light.lamp": settings}}, ["light.lamp"]
    )["scene"]["lights"]["light.lamp"]


@pytest.mark.parametrize(
    ("source", "expected"),
    [(True, "on"), (False, "off"), ("on", "on"), ("off", "off")],
)
def test_simple_states_and_yaml_booleans(source, expected):
    assert convert(source) == {"state": expected}
    assert convert({"state": source}) == {"state": expected}


@pytest.mark.parametrize(
    ("mode", "attribute", "value"),
    [
        ("hs", "hs_color", [31, 51]),
        ("color_temp", "color_temp_kelvin", 3200),
        ("rgb", "rgb_color", [18, 19, 20]),
        ("rgbw", "rgbw_color", [18, 19, 20, 21]),
        ("rgbww", "rgbww_color", [18, 19, 20, 21, 22]),
        ("xy", "xy_color", [0.3, 0.5]),
    ],
)
def test_only_active_native_color_is_retained(mode, attribute, value):
    source = {
        "state": "on",
        "color_mode": mode,
        "brightness": 137,
        "effect": "Candle",
        "hs_color": [0, 0],
        "rgb_color": [0, 0, 0],
        "xy_color": [0, 0],
        "color_temp_kelvin": 4000,
        "supported_features": 44,
        "friendly_name": "Lamp",
        "effect_list": ["Candle"],
        "transition": 50,
        attribute: value,
    }
    before = deepcopy(source)
    assert convert(source) == {
        "state": "on",
        "brightness": 137,
        "effect": "Candle",
        "color_mode": mode,
        attribute: value,
    }
    assert source == before


def test_white_uses_brightness_and_null_attributes_are_ignored():
    assert convert(
        {"state": True, "color_mode": "white", "brightness": 52, "effect": None}
    ) == {"state": "on", "brightness": 52, "color_mode": "white", "white": 52}
    assert convert(
        {
            "state": False,
            "color_mode": None,
            "brightness": None,
            "effect": None,
            "color_temp_kelvin": None,
        }
    ) == {"state": "off"}


def test_off_state_does_not_validate_or_reproduce_stale_color_attributes():
    assert convert(
        {"state": "off", "color_mode": "color_temp", "color_temp_kelvin": None}
    ) == {"state": "off"}
    assert convert(
        {"state": False, "brightness": "stale", "effect": [], "rgb_color": [900]}
    ) == {"state": "off"}


@pytest.mark.parametrize("mode", [None, "unknown"])
def test_legacy_color_priority_matches_native_scene_reproduction(mode):
    attributes = {
        "hs_color": [33, 40],
        "color_temp_kelvin": 2400,
        "rgb_color": [10, 20, 30],
        "rgbw_color": [10, 20, 30, 40],
        "rgbww_color": [10, 20, 30, 40, 50],
        "xy_color": [0.2, 0.3],
    }
    for key, value in list(attributes.items()):
        assert convert({"state": "on", "color_mode": mode, **attributes}) == {
            "state": "on",
            key: value,
        }
        del attributes[key]


@pytest.mark.parametrize(
    "settings",
    [
        "unavailable",
        0,
        {"brightness": 123},
        {"state": "on", "brightness": True},
        {"state": "on", "brightness": 255.1},
        {"state": "on", "brightness": 256},
        {"state": "on", "effect": 12},
        {"state": "on", "effect": ""},
        {"state": "on", "color_mode": "rgb", "rgb_color": [1, 2]},
        {"state": "on", "color_mode": "rgb", "rgb_color": [1, 2, 256]},
        {"state": "on", "color_mode": "color_temp", "rgb_color": [1, 2, 3]},
        {"state": "on", "color_mode": "white"},
        {"state": "on", "color_mode": "invalid"},
        {"state": "on", "color_mode": []},
    ],
)
def test_invalid_retained_settings_identify_the_lamp(settings):
    with pytest.raises(ValueError, match=r"light\.lamp:"):
        convert(settings)


def test_filter_before_validation_without_implicit_group_expansion():
    source = {
        "id": "source-id",
        "name": "Cinema",
        "entities": {
            "light.group": {"state": "on", "entity_id": ["light.member"]},
            "light.member": {"state": "invalid"},
            "light.outside": None,
            "switch.tv": "invalid",
        },
    }
    before = deepcopy(source)
    result = normalize_scene_import(source, ["light.group", "light.unlisted"])
    assert result["ignored_entities"] == 3
    assert result["scene"] == {
        "id": result["scene"]["id"],
        "name": "Cinema",
        "conditions": None,
        "can_turn_on": False,
        "lights": {"light.group": {"state": "on"}},
    }
    assert result["scene"]["id"] != source["id"]
    assert (
        normalize_scene_import(source, ["light.group"])["scene"]["id"]
        != result["scene"]["id"]
    )
    assert source == before
