"""Natural-light interpolation and capability-aware lamp commands."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from math import fsum, isfinite
from typing import Any

from homeassistant.components.light import LightEntityFeature
from homeassistant.core import State
from homeassistant.util import color

from .solar import SolarCycle, schematic_cycle, solar_anchor


def interpolate(curve: dict[str, Any], elevation: float) -> float:
    """Interpolate a two-point curve, retaining fractional solar elevations."""
    low_elevation = float(curve["low_elevation"])
    high_elevation = float(curve["high_elevation"])
    low, high = float(curve["low"]), float(curve["high"])
    if not all(isfinite(v) for v in (low_elevation, high_elevation, low, high)):
        raise ValueError("Curve values must be finite")
    if low_elevation >= high_elevation or not isfinite(elevation):
        raise ValueError("Curve elevations must be increasing and finite")
    fraction = max(
        0.0, min(1.0, (elevation - low_elevation) / (high_elevation - low_elevation))
    )
    interpolation = curve.get("interpolation", "linear")
    if interpolation in ("ease_in", "ease_in_out"):
        # Keep old profiles compatible while correcting both ends of the curve.
        fraction = fraction * fraction * (3 - 2 * fraction)
    elif interpolation != "linear":
        raise ValueError("Unknown curve interpolation")
    return low + (high - low) * fraction


def natural_values(
    profile: dict[str, Any],
    elevation: float,
    rising: bool,
    brightness_offset: float = 0,
    *,
    cycle: SolarCycle | None = None,
) -> dict[str, float]:
    """Calculate independent curves with continuous day and night connectors."""
    if profile.get("linked", True):
        brightness = interpolate(profile["morning"]["brightness"], elevation)
        temperature = interpolate(profile["morning"]["temperature"], elevation)
    else:
        if cycle is None:
            cycle = schematic_cycle(elevation, rising)
        brightness = continuous_curve(
            profile["morning"]["brightness"],
            profile["evening"]["brightness"],
            elevation,
            cycle,
        )
        temperature = continuous_curve(
            profile["morning"]["temperature"],
            profile["evening"]["temperature"],
            elevation,
            cycle,
        )
    return {
        "brightness_pct": max(
            0.0, min(100.0, brightness * (1 + brightness_offset / 100))
        ),
        "color_temp_kelvin": round(temperature),
    }


@dataclass(frozen=True, slots=True)
class _CurveNode:
    position: float
    elevation: float
    value: float
    outgoing: str


def continuous_curve(
    morning: dict[str, Any],
    evening: dict[str, Any],
    elevation: float,
    cycle: SolarCycle,
) -> float:
    """Join four solar anchors, preserving elevation-based reachable ramps.

    Unreachable thresholds meet at the real solar extremum. Co-located anchors
    share their mean attainable value; the adjacent ramp adapts to that endpoint.
    Only exactly equal positions merge, never nearby fractional thresholds.
    """
    # Native sun states round elevation to 0.01 degrees and may be minutes old.
    # Use the same precise instant as the astronomical anchors, especially when
    # an attainable threshold is very close to the solar turning elevation.
    if cycle.elevation is not None:
        elevation = cycle.elevation
    if not isfinite(elevation):
        raise ValueError("Solar elevation must be finite")
    nodes = []
    for arc in cycle.arcs:
        curve = morning if arc.rising else evening
        period = "morning" if arc.rising else "evening"
        bounds = ("low", "high") if arc.rising else ("high", "low")
        for index, bound in enumerate(bounds):
            position, attained = solar_anchor(arc, float(curve[f"{bound}_elevation"]))
            nodes.append(
                _CurveNode(
                    position,
                    attained,
                    interpolate(curve, attained),
                    period if index == 0 else "bridge",
                )
            )
    merged = []
    start = 0
    while start < len(nodes):
        end = start + 1
        while end < len(nodes) and nodes[end].position == nodes[start].position:
            end += 1
        last = nodes[end - 1]
        merged.append(
            _CurveNode(
                last.position,
                last.elevation,
                fsum(node.value for node in nodes[start:end]) / (end - start),
                last.outgoing,
            )
        )
        start = end
    index = bisect_right([node.position for node in merged], cycle.position) - 1
    if index < 0:
        return merged[0].value
    if index >= len(merged) - 1:
        return merged[-1].value
    before, after = merged[index : index + 2]
    if cycle.position == before.position:
        return before.value
    if before.outgoing == "bridge" or before.elevation == after.elevation:
        progress = (cycle.position - before.position) / (
            after.position - before.position
        )
    else:
        progress = (elevation - before.elevation) / (after.elevation - before.elevation)
    progress = max(0.0, min(1.0, progress))
    curve = morning if before.outgoing == "morning" else evening
    if before.outgoing == "bridge" or curve.get("interpolation", "linear") in (
        "ease_in",
        "ease_in_out",
    ):
        progress = progress * progress * (3 - 2 * progress)
    return before.value + (after.value - before.value) * progress


def supports_brightness(state: State) -> bool:
    """Use the advertised modes, never infer capabilities from current values."""
    return bool(
        set(state.attributes.get("supported_color_modes", ()))
        & {"brightness", "color_temp", "hs", "xy", "rgb", "rgbw", "rgbww", "white"}
    )


def _rgb_command(rgb: tuple[int, int, int], modes: set[str]) -> dict[str, Any]:
    """Express RGB in a color mode actually supported by a lamp."""
    if "rgb" in modes:
        return {"rgb_color": list(rgb)}
    if "rgbw" in modes:
        return {"rgbw_color": [*rgb, 0]}
    if "rgbww" in modes:
        return {"rgbww_color": [*rgb, 0, 0]}
    if "hs" in modes:
        return {"hs_color": list(color.color_RGB_to_hs(*rgb))}
    if "xy" in modes:
        return {"xy_color": list(color.color_RGB_to_xy(*rgb))}
    return {}


def lamp_parameters(state: State, desired: dict[str, Any]) -> dict[str, Any]:
    """Filter and adapt requested attributes before calling light.turn_on."""
    modes = set(state.attributes.get("supported_color_modes", ()))
    result: dict[str, Any] = {}
    if supports_brightness(state):
        if "brightness" in desired:
            result["brightness"] = max(0, min(255, int(desired["brightness"])))
        elif "brightness_pct" in desired:
            result["brightness_pct"] = max(
                0.0, min(100.0, float(desired["brightness_pct"]))
            )
    if "effect" in desired and (
        state.attributes.get("supported_features", 0) & LightEntityFeature.EFFECT
    ):
        result["effect"] = desired["effect"]
    if "white" in modes and (
        "white" in desired or desired.get("color_mode") == "white"
    ):
        if "white" in desired or "brightness" in desired:
            result["white"] = desired.get("white", desired.get("brightness"))
        elif "brightness_pct" in desired:
            result["white"] = round(desired["brightness_pct"] * 255 / 100)
    elif "color_temp_kelvin" in desired:
        kelvin = float(desired["color_temp_kelvin"])
        if "color_temp" in modes:
            minimum = state.attributes.get("min_color_temp_kelvin")
            maximum = state.attributes.get("max_color_temp_kelvin")
            if minimum is not None:
                kelvin = max(kelvin, minimum)
            if maximum is not None:
                kelvin = min(kelvin, maximum)
            result["color_temp_kelvin"] = round(kelvin)
        else:
            rgb = tuple(
                round(value) for value in color.color_temperature_to_rgb(kelvin)
            )
            result.update(_rgb_command(rgb, modes))
    elif "rgbw_color" in desired and "rgbw" in modes:
        result["rgbw_color"] = list(desired["rgbw_color"])
    elif "rgbww_color" in desired and "rgbww" in modes:
        result["rgbww_color"] = list(desired["rgbww_color"])
    elif "rgb_color" in desired:
        result.update(_rgb_command(tuple(desired["rgb_color"]), modes))
    elif "hs_color" in desired:
        if "hs" in modes:
            result["hs_color"] = list(desired["hs_color"])
        else:
            rgb = color.color_hs_to_RGB(*desired["hs_color"])
            result.update(_rgb_command(rgb, modes))
    elif "xy_color" in desired:
        if "xy" in modes:
            result["xy_color"] = list(desired["xy_color"])
        else:
            result.update(
                _rgb_command(color.color_xy_to_RGB(*desired["xy_color"]), modes)
            )
    return result


def capture_lamp_state(state: State) -> dict[str, Any]:
    """Retain reproducible light attributes, including the active native color."""
    result: dict[str, Any] = {"state": state.state}
    for key in ("brightness", "effect"):
        if (value := state.attributes.get(key)) is not None:
            result[key] = value
    mode = state.attributes.get("color_mode")
    color_attributes = {
        "color_temp": "color_temp_kelvin",
        "hs": "hs_color",
        "rgb": "rgb_color",
        "rgbw": "rgbw_color",
        "rgbww": "rgbww_color",
        "xy": "xy_color",
    }
    if mode in (*color_attributes, "white", "brightness", "onoff"):
        result["color_mode"] = mode
        key = color_attributes.get(mode)
        if key and (value := state.attributes.get(key)) is not None:
            result[key] = list(value) if isinstance(value, (list, tuple)) else value
    else:
        # Older integrations may omit color_mode. Prefer native white channels
        # over their approximate RGB/HS/XY attributes when choosing a fallback.
        for key in (
            "color_temp_kelvin",
            "rgbww_color",
            "rgbw_color",
            "rgb_color",
            "hs_color",
            "xy_color",
        ):
            if (value := state.attributes.get(key)) is not None:
                result[key] = list(value) if isinstance(value, (list, tuple)) else value
                break
    return result
