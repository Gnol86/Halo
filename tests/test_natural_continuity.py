"""Continuous solar profiles on schematic and actual astronomical cycles."""

from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from math import ceil, cos, floor, isfinite, pi
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from astral import Observer
from astral.sun import elevation as astral_elevation
from astral.sun import midnight, noon
from homeassistant.core import HomeAssistant, State

from custom_components.halo.engine import HaloRoomEngine
from custom_components.halo.models import ROOM_DEFAULTS
from custom_components.halo.natural import continuous_curve, interpolate, natural_values
from custom_components.halo.solar import (
    SolarArc,
    actual_solar_cycle,
    schematic_cycle,
    solar_anchor,
)


def separate_profile():
    """Keep independently chosen brightness and white-temperature thresholds."""
    return {
        "id": "separate",
        "linked": False,
        "morning": {
            "brightness": {
                "low_elevation": -20,
                "high_elevation": 20,
                "low": 20,
                "high": 100,
                "interpolation": "linear",
            },
            "temperature": {
                "low_elevation": -10,
                "high_elevation": 25,
                "low": 2000,
                "high": 6500,
                "interpolation": "ease_in_out",
            },
        },
        "evening": {
            "brightness": {
                "low_elevation": -20,
                "high_elevation": 20,
                "low": 10,
                "high": 40,
                "interpolation": "ease_in_out",
            },
            "temperature": {
                "low_elevation": -15,
                "high_elevation": 10,
                "low": 1500,
                "high": 4000,
                "interpolation": "linear",
            },
        },
    }


def schematic_values(profile, position):
    position %= 1
    elevation = -90 * cos(2 * pi * position)
    return natural_values(profile, elevation, position <= 0.5)


def test_schematic_day_and_night_have_continuous_connectors():
    profile = separate_profile()
    assert schematic_values(profile, 0.5)["brightness_pct"] == pytest.approx(70)
    assert schematic_values(profile, 0)["brightness_pct"] == pytest.approx(15)
    for boundary in (0, 0.5, 1):
        before = schematic_values(profile, boundary - 0.000001)
        after = schematic_values(profile, boundary + 0.000001)
        assert abs(before["brightness_pct"] - after["brightness_pct"]) < 0.001
        assert abs(before["color_temp_kelvin"] - after["color_temp_kelvin"]) <= 1
    assert schematic_values(profile, 0) == schematic_values(profile, 1)


@pytest.mark.parametrize("kind", ["brightness", "temperature"])
@pytest.mark.parametrize("rising", [True, False])
def test_reachable_ramps_keep_elevation_interpolation_and_their_exact_endpoints(
    kind, rising
):
    profile = separate_profile()
    selected = profile["morning" if rising else "evening"][kind]
    for fraction in (0, 0.1, 0.25, 0.5, 0.9, 1):
        elevation = selected["low_elevation"] + fraction * (
            selected["high_elevation"] - selected["low_elevation"]
        )
        result = continuous_curve(
            profile["morning"][kind],
            profile["evening"][kind],
            elevation,
            schematic_cycle(elevation, rising),
        )
        assert result == pytest.approx(interpolate(selected, elevation))


def test_connectors_have_zero_slope_at_their_endpoints():
    profile = separate_profile()
    curve = profile["morning"]["brightness"]
    start, _ = solar_anchor(SolarArc(0, 0.5, -90, 90, True), curve["high_elevation"])
    at_start = schematic_values(profile, start)["brightness_pct"]
    nearby = schematic_values(profile, start + 0.000001)["brightness_pct"]
    assert abs(nearby - at_start) < 0.000001
    assert nearby <= at_start


def test_linked_profiles_keep_existing_plateaus_and_ignore_inactive_evening():
    profile = separate_profile()
    profile["linked"] = True
    profile.pop("evening")
    for rising in (True, False):
        for elevation in (-90, -20, 0, 25, 90):
            result = natural_values(profile, elevation, rising, -20)
            assert result["brightness_pct"] == pytest.approx(
                interpolate(profile["morning"]["brightness"], elevation) * 0.8
            )
            assert result["color_temp_kelvin"] == round(
                interpolate(profile["morning"]["temperature"], elevation)
            )


def test_exactly_coincident_schematic_anchors_share_a_mean_without_mutating_profile():
    profile = separate_profile()
    for period in ("morning", "evening"):
        profile[period]["brightness"].update(low_elevation=-90, high_elevation=90)
    original = deepcopy(profile)
    assert schematic_values(profile, 0.5)["brightness_pct"] == pytest.approx(70)
    assert schematic_values(profile, 0)["brightness_pct"] == pytest.approx(15)
    assert schematic_values(profile, 0.25)["brightness_pct"] == pytest.approx(42.5)
    assert schematic_values(profile, 0.75)["brightness_pct"] == pytest.approx(42.5)
    assert profile == original


def test_nearby_fractional_thresholds_are_not_merged_and_offsets_follow_smoothing():
    profile = separate_profile()
    profile["morning"]["brightness"].update(
        low_elevation=12.345678, high_elevation=12.345679
    )
    for bound in ("low", "high"):
        curve = profile["morning"]["brightness"]
        actual = natural_values(profile, curve[f"{bound}_elevation"], True)
        assert actual["brightness_pct"] == pytest.approx(curve[bound])
    profile = separate_profile()
    assert natural_values(profile, 90, True, 50)["brightness_pct"] == 100
    assert natural_values(profile, 90, True, -50)["brightness_pct"] == pytest.approx(35)


def native_sun(observer, now, rising):
    return State(
        "sun.sun",
        "above_horizon",
        {
            "elevation": astral_elevation(observer, now),
            "rising": rising,
            "next_noon": noon(observer, now.date() + timedelta(days=1)).isoformat(),
            "next_midnight": midnight(
                observer, now.date() + timedelta(days=1)
            ).isoformat(),
        },
    )


@pytest.fixture
def observer(hass: HomeAssistant):
    hass.config.latitude = 50.85
    hass.config.longitude = 4.35
    hass.config.elevation = 30
    return Observer(50.85, 4.35, 30)


@pytest.mark.parametrize("event", [noon, midnight])
async def test_real_turning_points_are_continuous_at_non_extreme_elevations(
    hass: HomeAssistant, observer, event
):
    profile = separate_profile()
    turn = event(observer, date(2026, 10, 21))
    height = astral_elevation(observer, turn)
    assert -80 < height < 80
    results = []
    for seconds in (-0.001, 0, 0.001):
        now = turn + timedelta(seconds=seconds)
        rising = seconds < 0 if event is noon else seconds >= 0
        sun = native_sun(observer, now, rising)
        cycle = actual_solar_cycle(hass, sun, now)
        assert cycle is not None
        results.append(
            natural_values(profile, sun.attributes["elevation"], rising, cycle=cycle)
        )
    assert (
        max(result["brightness_pct"] for result in results)
        - min(result["brightness_pct"] for result in results)
        < 0.001
    )
    assert (
        max(result["color_temp_kelvin"] for result in results)
        - min(result["color_temp_kelvin"] for result in results)
        <= 1
    )
    assert results[1]["brightness_pct"] == pytest.approx(
        69.88 if event is noon else 15, abs=0.02
    )


@pytest.mark.parametrize("event", [noon, midnight])
async def test_unreachable_thresholds_use_the_mean_attainable_value_at_real_turns(
    hass: HomeAssistant, observer, event
):
    profile = separate_profile()
    for period in ("morning", "evening"):
        for kind in ("brightness", "temperature"):
            profile[period][kind].update(low_elevation=-90, high_elevation=90)
    turn = event(observer, date(2026, 12, 21))
    elevation = astral_elevation(observer, turn)
    expected = {
        kind: (
            interpolate(profile["morning"][kind], elevation)
            + interpolate(profile["evening"][kind], elevation)
        )
        / 2
        for kind in ("brightness", "temperature")
    }
    for seconds in (-0.001, 0, 0.001):
        now = turn + timedelta(seconds=seconds)
        rising = seconds < 0 if event is noon else seconds >= 0
        sun = native_sun(observer, now, rising)
        cycle = actual_solar_cycle(hass, sun, now)
        assert cycle is not None
        result = natural_values(
            profile, sun.attributes["elevation"], rising, cycle=cycle
        )
        assert result["brightness_pct"] == pytest.approx(
            expected["brightness"], abs=0.01
        )
        assert result["color_temp_kelvin"] == pytest.approx(
            round(expected["temperature"]), abs=1
        )


@pytest.mark.parametrize("latitude", [-90, -80, 80, 90])
@pytest.mark.parametrize("day", [date(2026, 6, 21), date(2026, 12, 21)])
async def test_polar_days_and_nights_need_no_sunrise_or_sunset(
    hass: HomeAssistant, latitude, day
):
    hass.config.latitude = latitude
    hass.config.longitude = 10
    hass.config.elevation = 0
    observer = Observer(latitude, 10, 0)
    profile = separate_profile()
    for hour in (0, 6, 12, 18, 23):
        now = datetime.combine(day, datetime.min.time(), UTC) + timedelta(hours=hour)
        sun = native_sun(observer, now, hour < 12)
        cycle = actual_solar_cycle(hass, sun, now)
        assert cycle is not None
        result = natural_values(
            profile, sun.attributes["elevation"], hour < 12, cycle=cycle
        )
        assert 0 <= result["brightness_pct"] <= 100
        assert 1000 <= result["color_temp_kelvin"] <= 40000
        assert all(isfinite(value) for value in result.values())


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"next_noon": "broken"},
        {"next_noon": "2026-10-21T12:00:00", "next_midnight": "2026-10-22T00:00:00"},
    ],
)
async def test_custom_sun_without_aware_event_metadata_uses_only_its_elevation(
    hass: HomeAssistant, observer, metadata
):
    sun = State(
        "sun.demo", "above_horizon", {"elevation": 8, "rising": False, **metadata}
    )
    now = datetime(2026, 10, 21, 4, tzinfo=UTC)
    assert actual_solar_cycle(hass, sun, now) is None
    profile = separate_profile()
    expected = natural_values(profile, 8, False)
    for hour in (0, 8, 16):
        assert actual_solar_cycle(hass, sun, now + timedelta(hours=hour)) is None
        assert natural_values(profile, 8, False) == expected


async def test_engine_targets_cross_actual_noon_and_midnight_without_branch_jumps(
    hass: HomeAssistant, observer, freezer
):
    profile = separate_profile()
    room = deepcopy(ROOM_DEFAULTS)
    room.update(
        id="test",
        lights=["light.test"],
        associations=[
            {"profile_id": "separate", "lights": ["light.test"], "brightness_offset": 0}
        ],
    )
    manager = SimpleNamespace(
        config={
            "rooms": {"test": room},
            "profiles": {"separate": profile},
            "sun_entity_id": "sun.sun",
        },
        runtime_state={},
    )
    engine = HaloRoomEngine(hass, manager, "test")
    hass.states.async_set("light.test", "on", {"supported_color_modes": ["color_temp"]})
    # The real day is not perfectly symmetric around Astral's solar noon.
    for event, expected in ((noon, 69.88), (midnight, 15)):
        turn = event(observer, date(2026, 10, 21))
        results = []
        for seconds in (-0.001, 0.001):
            now = turn + timedelta(seconds=seconds)
            freezer.move_to(now)
            rising = seconds < 0 if event is noon else seconds >= 0
            sun = native_sun(observer, now, rising)
            hass.states.async_set(sun.entity_id, sun.state, dict(sun.attributes))
            results.append(engine._natural_targets()["light.test"])
        assert results[0]["brightness_pct"] == pytest.approx(expected, abs=0.02)
        assert results[1]["brightness_pct"] == pytest.approx(
            results[0]["brightness_pct"], abs=0.001
        )
        assert (
            abs(results[0]["color_temp_kelvin"] - results[1]["color_temp_kelvin"]) <= 1
        )


async def test_daily_astronomy_and_threshold_resolution_are_cached(
    hass: HomeAssistant, observer
):
    now = datetime(2027, 2, 15, 12, tzinfo=UTC)
    sun = native_sun(observer, now, False)
    profile = separate_profile()
    cycle = actual_solar_cycle(hass, sun, now)
    assert cycle is not None
    natural_values(profile, sun.attributes["elevation"], False, cycle=cycle)
    with patch(
        "custom_components.halo.solar.astral_elevation",
        wraps=astral_elevation,
    ) as calculate_elevation:
        for _ in range(3):
            repeated = actual_solar_cycle(hass, sun, now + timedelta(seconds=1))
            assert repeated is not None
            assert repeated.arcs is cycle.arcs
            natural_values(profile, sun.attributes["elevation"], False, cycle=repeated)
        # Only the current height is refreshed. No daily extrema or threshold
        # crossing searches are repeated for rooms sharing the same profiles.
        assert calculate_elevation.call_count <= 1
        assert all(
            call.args[1] == now + timedelta(seconds=1)
            for call in calculate_elevation.call_args_list
        )


@pytest.mark.parametrize("event", [noon, midnight])
@pytest.mark.parametrize("interpolation", ["linear", "ease_in_out"])
async def test_native_quantized_elevation_cannot_break_near_extremum_ramps(
    hass: HomeAssistant, observer, freezer, event, interpolation
):
    """Native rounding/stale height cannot switch 20 -> 50 -> 80 at noon."""
    turn = event(observer, date(2026, 10, 22))
    height = astral_elevation(observer, turn)
    low = floor(height * 100) / 100 if event is noon else -90
    high = ceil(height * 100) / 100 if event is midnight else 90
    profile = separate_profile()
    for period, values in (("morning", (20, 100)), ("evening", (80, 0))):
        profile[period]["brightness"].update(
            low_elevation=low,
            high_elevation=high,
            low=values[0],
            high=values[1],
            interpolation=interpolation,
        )
    room = deepcopy(ROOM_DEFAULTS)
    room.update(
        id="test",
        lights=["light.test"],
        associations=[{"profile_id": "separate", "lights": ["light.test"]}],
    )
    manager = SimpleNamespace(
        config={
            "rooms": {"test": room},
            "profiles": {"separate": profile},
            "sun_entity_id": "sun.sun",
        },
        runtime_state={},
    )
    engine = HaloRoomEngine(hass, manager, "test")
    hass.states.async_set("light.test", "on", {"supported_color_modes": ["brightness"]})
    results = []
    for seconds in (-0.001, 0, 0.001):
        now = turn + timedelta(seconds=seconds)
        freezer.move_to(now)
        rising = seconds < 0 if event is noon else seconds >= 0
        sun = native_sun(observer, now, rising)
        attributes = dict(sun.attributes)
        attributes["elevation"] = round(attributes["elevation"], 2)
        hass.states.async_set(sun.entity_id, sun.state, attributes)
        results.append(engine._natural_targets()["light.test"]["brightness_pct"])
        # A stale but available native state must also use the clock and height
        # of this astronomical cycle, never the older source's rounded height.
        attributes["elevation"] -= 0.5
        hass.states.async_set(sun.entity_id, sun.state, attributes)
        assert engine._natural_targets()["light.test"][
            "brightness_pct"
        ] == pytest.approx(results[-1])
    assert max(results) - min(results) < 0.01
    assert results[1] == pytest.approx(50, abs=0.02)
