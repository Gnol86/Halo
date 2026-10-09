"""Validate priorities' condition inputs, especially missing sensor data."""

from datetime import datetime

import pytest
from homeassistant.core import HomeAssistant

from custom_components.halo.conditions import condition_entities, evaluate_condition


def test_combinations_and_numeric_boundaries(hass: HomeAssistant):
    hass.states.async_set("media_player.tv", "on")
    hass.states.async_set("sensor.lux", "20")
    tree = {
        "type": "and",
        "conditions": [
            {"type": "state", "entity_id": "media_player.tv", "state": "on"},
            {"type": "numeric", "entity_id": "sensor.lux", "above": 10, "below": 30},
        ],
    }
    assert evaluate_condition(hass, tree)
    hass.states.async_set("sensor.lux", "30")
    assert not evaluate_condition(hass, tree)
    assert condition_entities(tree) == {"media_player.tv", "sensor.lux"}


@pytest.mark.parametrize("value", ["unknown", "unavailable", "NaN", "inf", "invalid"])
def test_missing_numeric_is_not_zero_even_under_not(hass, value):
    hass.states.async_set("sensor.lux", value)
    leaf = {"type": "numeric", "entity_id": "sensor.lux", "below": 10}
    assert not evaluate_condition(hass, leaf)
    assert not evaluate_condition(hass, {"type": "not", "condition": leaf})


def test_or_can_use_known_branch_and_empty_conditions_never_auto_activate(hass):
    hass.states.async_set("binary_sensor.present", "on")
    assert evaluate_condition(
        hass,
        {
            "type": "or",
            "conditions": [
                {"type": "state", "entity_id": "sensor.missing", "state": "on"},
                {"type": "state", "entity_id": "binary_sensor.present", "state": "on"},
            ],
        },
    )
    assert not evaluate_condition(hass, None)
    assert not evaluate_condition(hass, {"type": "and", "conditions": []})


@pytest.mark.parametrize(
    "hour,expected",
    [(21, False), (22, True), (23, True), (0, True), (5, True), (6, False)],
)
def test_overnight_time_window(hass, hour, expected):
    condition = {"type": "time", "after": "22:00", "before": "06:00"}
    assert (
        evaluate_condition(hass, condition, now=datetime(2026, 10, 9, hour)) is expected
    )


def test_selected_sun_and_numeric_attributes(hass):
    hass.states.async_set("sun.selected", "above_horizon", {"elevation": 3.25})
    assert evaluate_condition(
        hass, {"type": "sun", "above": 3, "below": 3.5}, "sun.selected"
    )
    assert evaluate_condition(
        hass,
        {
            "type": "numeric",
            "entity_id": "sun.selected",
            "attribute": "elevation",
            "above": 3,
        },
    )
    assert not evaluate_condition(hass, {"type": "sun", "above": 0}, "sun.missing")


def test_optional_null_boundaries(hass):
    hass.states.async_set("sensor.lux", "20")
    assert evaluate_condition(
        hass, {"type": "numeric", "entity_id": "sensor.lux", "above": None, "below": 50}
    )
    assert evaluate_condition(
        hass,
        {"type": "time", "after": None, "before": "20:00"},
        now=datetime(2026, 10, 9, 10),
    )
