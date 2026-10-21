"""Solar cycles for continuous natural profiles, without network access."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from math import acos, floor, isfinite, pi

from astral import Observer
from astral.sun import elevation as astral_elevation
from astral.sun import midnight, noon
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.sun import get_astral_observer
from homeassistant.util import dt as dt_util

type ObserverKey = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class SolarArc:
    """One rising or setting branch, including its actual turning elevations."""

    start: float
    end: float
    start_elevation: float
    end_elevation: float
    rising: bool
    observer: ObserverKey | None = None


@dataclass(frozen=True, slots=True)
class SolarCycle:
    """Current position and surrounding branches, in days or UTC seconds."""

    position: float
    arcs: tuple[SolarArc, ...]
    elevation: float | None = None


def schematic_cycle(elevation: float, rising: bool) -> SolarCycle:
    """Use the editor's periodic cycle when a source has no solar event metadata."""
    if not isfinite(elevation):
        raise ValueError("Solar elevation must be finite")
    position = acos(-max(-90.0, min(90.0, elevation)) / 90) / (2 * pi)
    if not rising:
        position = 1 - position
    return SolarCycle(
        position,
        tuple(
            arc
            for offset in (-1, 0, 1)
            for arc in (
                SolarArc(offset, offset + 0.5, -90, 90, True),
                SolarArc(offset + 0.5, offset + 1, 90, -90, False),
            )
        ),
    )


@lru_cache(maxsize=8192)
def _second_elevation(observer_key: ObserverKey, second: int) -> float:
    """Share current and searched astronomical heights across rooms."""
    return astral_elevation(
        Observer(*observer_key), datetime.fromtimestamp(second, UTC)
    )


def _precise_elevation(observer_key: ObserverKey, position: float) -> float:
    """Interpolate Astral's whole-second calculation to avoid subsecond steps."""
    second = floor(position)
    height = _second_elevation(observer_key, second)
    fraction = position - second
    if not fraction:
        return height
    return height + (_second_elevation(observer_key, second + 1) - height) * fraction


@lru_cache(maxsize=32)
def _astral_arcs(observer_key: ObserverKey, day: date) -> tuple[SolarArc, ...]:
    """Cache neighbouring days; locations and dates invalidate the cache key."""
    observer = Observer(*observer_key)
    midnights = [
        midnight(observer, day + timedelta(days=offset)).timestamp()
        for offset in range(-3, 4)
    ]
    result = []
    for offset in range(-2, 3):
        peak = noon(observer, day + timedelta(days=offset)).timestamp()
        start = max(value for value in midnights if value < peak)
        end = min(value for value in midnights if value > peak)
        heights = [
            _precise_elevation(observer_key, value) for value in (start, peak, end)
        ]
        result.extend(
            (
                SolarArc(start, peak, heights[0], heights[1], True, observer_key),
                SolarArc(peak, end, heights[1], heights[2], False, observer_key),
            )
        )
    return tuple(result)


def actual_solar_cycle(
    hass: HomeAssistant, sun: State, now: datetime
) -> SolarCycle | None:
    """Use astronomy only for sources exposing the native solar-event contract.

    Synthetic/custom elevation-only sources keep the schematic cycle rather than
    mixing their state with an unrelated geographical clock. Event values are a
    capability check, not the interpolation clock: a stale next event at the
    exact turning instant must not switch the calculation to a different model.
    """
    for key in ("next_noon", "next_midnight"):
        value = sun.attributes.get(key)
        if not isinstance(value, str):
            return None
        event = dt_util.parse_datetime(value)
        if event is None or event.tzinfo is None:
            return None
    observer = get_astral_observer(hass)
    observer_key = (
        float(observer.latitude),
        float(observer.longitude),
        float(observer.elevation),
    )
    return SolarCycle(
        now.timestamp(),
        _astral_arcs(observer_key, now.astimezone(UTC).date()),
        _precise_elevation(observer_key, now.timestamp()),
    )


@lru_cache(maxsize=4096)
def solar_anchor(arc: SolarArc, elevation: float) -> tuple[float, float]:
    """Resolve a threshold to its time and attainable elevation on one branch."""
    if arc.rising:
        if elevation <= arc.start_elevation:
            return arc.start, arc.start_elevation
        if elevation >= arc.end_elevation:
            return arc.end, arc.end_elevation
    else:
        if elevation >= arc.start_elevation:
            return arc.start, arc.start_elevation
        if elevation <= arc.end_elevation:
            return arc.end, arc.end_elevation
    if arc.observer is None:
        progress = acos(-elevation / 90) / pi
        if not arc.rising:
            progress = 1 - progress
        return arc.start + (arc.end - arc.start) * progress, elevation
    lower, upper = arc.start, arc.end
    # Bisection is bounded and cached per daily branch/threshold, never per lamp.
    for _ in range(40):
        middle = (lower + upper) / 2
        if middle in (lower, upper):
            break
        height = _precise_elevation(arc.observer, middle)
        if (height < elevation) == arc.rising:
            lower = middle
        else:
            upper = middle
    return (lower + upper) / 2, elevation
