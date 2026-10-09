"""Verify solar interpolation and real lamp capability boundaries."""

from copy import deepcopy

import pytest
from homeassistant.core import State

from custom_components.halo.natural import interpolate, lamp_parameters, natural_values


def profile():
    morning = {
        "brightness": {
            "low_elevation": -5.5,
            "high_elevation": 10.5,
            "low": 20,
            "high": 100,
        },
        "temperature": {
            "low_elevation": -10,
            "high_elevation": 20,
            "low": 2000,
            "high": 6500,
        },
    }
    return {
        "id": "day",
        "linked": True,
        "morning": morning,
        "evening": deepcopy(morning),
    }


def test_independent_curves_fractional_elevation_and_relative_offset():
    configured = profile()
    result = natural_values(configured, 2.5, True, -30)
    assert result == {"brightness_pct": 42, "color_temp_kelvin": 3875}
    assert configured["morning"]["brightness"]["high"] == 100
    assert natural_values(configured, -100, True)["brightness_pct"] == 20
    assert natural_values(configured, 100, True, 50)["brightness_pct"] == 100


def test_linked_and_separate_evening():
    configured = profile()
    configured["evening"]["temperature"]["high"] = 5000
    assert natural_values(configured, 20, False)["color_temp_kelvin"] == 6500
    configured["linked"] = False
    assert natural_values(configured, 20, False)["color_temp_kelvin"] == 5000
    assert natural_values(configured, 20, True)["color_temp_kelvin"] == 6500


@pytest.mark.parametrize(
    ("interpolation", "expected"),
    [
        ("linear", [20, 20, 40, 60, 80, 100, 100]),
        ("ease_in", [20, 20, 25, 40, 65, 100, 100]),
    ],
)
def test_curve_modes_keep_solar_bounds_and_plateaus(interpolation, expected):
    curve = profile()["morning"]["brightness"] | {"interpolation": interpolation}
    assert [
        interpolate(curve, elevation)
        for elevation in (-20, -5.5, -1.5, 2.5, 6.5, 10.5, 30)
    ] == expected
    # Acceleration depends on the solar interval, including a decreasing value.
    descending = curve | {"low": 100, "high": 20}
    assert interpolate(descending, 2.5) == 120 - expected[3]


def test_independent_interpolation_modes_periods_and_offset():
    configured = profile()
    configured["morning"]["brightness"]["interpolation"] = "ease_in"
    configured["evening"]["temperature"]["interpolation"] = "ease_in"
    assert natural_values(configured, 2.5, True, -30) == {
        "brightness_pct": 28,
        "color_temp_kelvin": 3875,
    }
    # Linked periods use the morning modes even on a descending sun.
    assert natural_values(configured, 2.5, False, -30) == {
        "brightness_pct": 28,
        "color_temp_kelvin": 3875,
    }
    configured["linked"] = False
    assert natural_values(configured, 2.5, False, -30) == {
        "brightness_pct": 42,
        "color_temp_kelvin": 2781,
    }


@pytest.mark.parametrize("interpolation", [None, "ease_out", [], {}, 0, True])
def test_unknown_curve_interpolation_rejected(interpolation):
    curve = profile()["morning"]["brightness"] | {"interpolation": interpolation}
    with pytest.raises(ValueError, match="interpolation"):
        interpolate(curve, 0)


@pytest.mark.parametrize("elevation", [float("nan"), float("inf")])
def test_nonfinite_elevation_is_not_zero(elevation):
    with pytest.raises(ValueError):
        interpolate(profile()["morning"]["brightness"], elevation)


def test_degenerate_curve_rejected():
    with pytest.raises(ValueError):
        interpolate({"low_elevation": 0, "high_elevation": 0, "low": 0, "high": 100}, 0)


def test_lamp_capabilities_and_native_white_preference():
    desired = {"brightness_pct": 130, "color_temp_kelvin": 1800}
    assert (
        lamp_parameters(
            State("light.basic", "on", {"supported_color_modes": ["onoff"]}), desired
        )
        == {}
    )
    assert lamp_parameters(
        State("light.dimmer", "on", {"supported_color_modes": ["brightness"]}), desired
    ) == {"brightness_pct": 100}
    dual = State(
        "light.white",
        "on",
        {
            "supported_color_modes": ["color_temp", "rgb"],
            "min_color_temp_kelvin": 2500,
            "max_color_temp_kelvin": 5000,
        },
    )
    assert lamp_parameters(dual, desired) == {
        "brightness_pct": 100,
        "color_temp_kelvin": 2500,
    }
    assert lamp_parameters(dual, {"color_temp_kelvin": 8000}) == {
        "color_temp_kelvin": 5000
    }


@pytest.mark.parametrize(
    "mode,key",
    [
        ("rgb", "rgb_color"),
        ("rgbw", "rgbw_color"),
        ("rgbww", "rgbww_color"),
        ("hs", "hs_color"),
        ("xy", "xy_color"),
    ],
)
def test_color_only_white_approximation(mode, key):
    state = State("light.color", "on", {"supported_color_modes": [mode]})
    values = lamp_parameters(state, {"brightness_pct": 50, "color_temp_kelvin": 2700})
    assert values["brightness_pct"] == 50
    assert key in values
    assert "color_temp_kelvin" not in values


def test_scene_color_conversion_and_native_rgbw_restore():
    rgb = State("light.rgb", "on", {"supported_color_modes": ["rgb"]})
    assert lamp_parameters(rgb, {"hs_color": [0, 100]}) == {"rgb_color": [255, 0, 0]}
    rgbw = State("light.rgbw", "on", {"supported_color_modes": ["rgbw"]})
    assert lamp_parameters(rgbw, {"rgbw_color": [10, 20, 30, 40]}) == {
        "rgbw_color": [10, 20, 30, 40]
    }
