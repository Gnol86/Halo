"""Natural-light interpolation and capability-aware lamp commands."""

from __future__ import annotations

from math import isfinite
from typing import Any

from homeassistant.core import State
from homeassistant.util import color


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
    return low + (high - low) * fraction


def natural_values(
    profile: dict[str, Any],
    elevation: float,
    rising: bool,
    brightness_offset: float = 0,
) -> dict[str, float]:
    """Calculate independent brightness and white-temperature curves."""
    branch = "morning" if profile.get("linked", True) or rising else "evening"
    curves = profile[branch]
    brightness = interpolate(curves["brightness"], elevation)
    return {
        "brightness_pct": max(
            0.0, min(100.0, brightness * (1 + brightness_offset / 100))
        ),
        "color_temp_kelvin": round(interpolate(curves["temperature"], elevation)),
    }


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
    if supports_brightness(state) and "brightness_pct" in desired:
        result["brightness_pct"] = max(
            0.0, min(100.0, float(desired["brightness_pct"]))
        )
    if "color_temp_kelvin" in desired:
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
