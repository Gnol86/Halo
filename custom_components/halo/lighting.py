"""Evaluate the fallback lighting permission without inventing lux readings."""

from datetime import time
from typing import Any

from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

from .conditions import UNAVAILABLE, number


def solar_elevation(sun: State | None) -> float | None:
    """Accept a real finite solar angle; unavailable data never becomes zero."""
    if sun is None or sun.state in UNAVAILABLE:
        return None
    elevation = number(sun.attributes.get("elevation"))
    return elevation if elevation is not None and -90 <= elevation <= 90 else None


def fallback_permission(
    hass: HomeAssistant, fallback: dict[str, Any], sun_entity_id: str | None
) -> bool | None:
    """Return permission from validated settings, or unknown solar data."""
    mode = fallback.get("mode", "always")
    if mode == "always":
        return True
    if mode == "time":
        current = dt_util.now().time().replace(tzinfo=None)
        start = time.fromisoformat(fallback.get("start", "18:00"))
        end = time.fromisoformat(fallback.get("end", "08:00"))
        if start > end:
            return current >= start or current < end
        return start <= current < end
    sun = hass.states.get(sun_entity_id) if sun_entity_id else None
    elevation = solar_elevation(sun)
    if elevation is None:
        return None
    threshold = fallback.get("morning_below", 0)
    if not fallback.get("linked", True):
        rising = sun.attributes.get("rising")
        if not isinstance(rising, bool):
            return None
        if not rising:
            threshold = fallback.get("evening_below", 0)
    return elevation < threshold
