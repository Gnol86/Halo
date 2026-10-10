"""Validate persisted and incoming Halo configuration before it controls lights."""

import math
import re
from copy import deepcopy
from typing import Any

TRANSITIONS = ("turn_on", "lux_on", "natural", "scene", "turn_off")
DEFAULT_PRESENCE_RETURN_WINDOW = 30
TRANSITION_DEFAULTS = {
    "turn_on": 0,
    "lux_on": 10,
    "natural": 60,
    "scene": 10,
    "turn_off": 2,
}
LIGHTING_FALLBACK_DEFAULTS = {
    "mode": "always",
    "start": "18:00",
    "end": "08:00",
    "linked": True,
    "morning_below": 0,
    "evening_below": 0,
    "turn_off": False,
}
ROOM_DEFAULTS = {
    "lights": [],
    "presence_entity_id": None,
    "presence_states": ["on"],
    "lux_entity_id": None,
    "lux_threshold": None,
    "lux_hysteresis": 0,
    "lux_off": False,
    "lighting_fallback": LIGHTING_FALLBACK_DEFAULTS.copy(),
    "absence_delay": 0,
    "manual_pause": 7200,
    "lux_off_delay": 30,
    "allow_off_during_pause": True,
    "automation_enabled": False,
    "natural_enabled": True,
    "transitions": dict.fromkeys(TRANSITIONS, "inherit"),
    "base": {},
    "nightlight": {"enabled": False, "lights": {}},
    "associations": [],
    "scenes": [],
}


def default_config() -> dict[str, Any]:
    """Return a fresh configuration, never sharing mutable defaults."""
    return {
        "sun_entity_id": "sun.sun",
        "presence_return_window": DEFAULT_PRESENCE_RETURN_WINDOW,
        "transitions": TRANSITION_DEFAULTS.copy(),
        "profiles": {},
        "rooms": {},
    }


def _mapping(value: Any, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label}: expected an object")
    return value


def _number(value: Any, label: str, low: float, high: float) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not low <= value <= high
        or not math.isfinite(value)
    ):
        raise ValueError(f"{label}: expected a finite number between {low} and {high}")
    return value


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label}: expected a boolean")
    return value


def validate_lighting_fallback(value: Any) -> dict[str, Any]:
    """Keep inactive choices while validating a room's no-sensor policy."""
    supplied = _mapping(value, "lighting_fallback")
    if supplied.keys() - LIGHTING_FALLBACK_DEFAULTS.keys():
        raise ValueError("Unknown lighting_fallback setting")
    fallback = LIGHTING_FALLBACK_DEFAULTS.copy() | deepcopy(supplied)
    if fallback["mode"] not in ("always", "time", "sun"):
        raise ValueError("Invalid lighting_fallback mode")
    for key in ("start", "end"):
        if not isinstance(fallback[key], str) or not re.fullmatch(
            r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", fallback[key]
        ):
            raise ValueError(f"lighting_fallback {key}: expected HH:MM")
    if fallback["start"] == fallback["end"]:
        raise ValueError("lighting_fallback start and end must differ")
    for key in ("linked", "turn_off"):
        _boolean(fallback[key], f"lighting_fallback {key}")
    for key in ("morning_below", "evening_below"):
        _number(fallback[key], f"lighting_fallback {key}", -90, 90)
    return fallback


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 255:
        raise ValueError(f"{label}: expected non-empty text (maximum 255 characters)")
    return value


def _entity(value: Any, domain: str | None = None) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9_]+\.[a-z0-9_]+", value):
        raise ValueError("Invalid entity ID")
    if domain and not value.startswith(f"{domain}."):
        raise ValueError(f"Expected a {domain} entity")
    return value


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", value):
        raise ValueError("Invalid stable identifier")
    return value


def _lights(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("Lights must be a list")
    result = [_entity(item, "light") for item in value]
    if len(set(result)) != len(result):
        raise ValueError("Duplicate lights")
    return result


def validate_lamp_states(value: Any, members: list[str]) -> dict:
    """Accept only light parameters, never arbitrary Home Assistant service data."""
    output = deepcopy(_mapping(value, "lamp states"))
    allowed = {
        "state",
        "brightness",
        "brightness_pct",
        "effect",
        "color_mode",
        "color_temp_kelvin",
        "rgb_color",
        "rgbw_color",
        "rgbww_color",
        "hs_color",
        "xy_color",
        "white",
    }
    for entity_id, settings in output.items():
        if entity_id not in members:
            raise ValueError("Scene or ambience refers to a light outside its room")
        _mapping(settings, entity_id)
        if set(settings) - allowed or settings.get("state") not in ("on", "off"):
            raise ValueError("Invalid lamp state")
        if "brightness_pct" in settings:
            _number(settings["brightness_pct"], "brightness_pct", 0, 100)
        if "brightness" in settings:
            _number(settings["brightness"], "brightness", 0, 255)
            if int(settings["brightness"]) != settings["brightness"]:
                raise ValueError("brightness must be an integer")
            if "brightness_pct" in settings:
                raise ValueError("Use only one brightness representation per light")
        if "effect" in settings:
            _text(settings["effect"], "effect")
        if "color_mode" in settings and settings["color_mode"] not in (
            "onoff",
            "brightness",
            "color_temp",
            "hs",
            "rgb",
            "rgbw",
            "rgbww",
            "xy",
            "white",
        ):
            raise ValueError("Invalid color mode")
        if "white" in settings:
            _number(settings["white"], "white", 0, 255)
        if "color_temp_kelvin" in settings:
            _number(settings["color_temp_kelvin"], "color_temp_kelvin", 1000, 40000)
        color_keys = set(settings) & {
            "color_temp_kelvin",
            "rgb_color",
            "rgbw_color",
            "rgbww_color",
            "hs_color",
            "xy_color",
            "white",
        }
        if len(color_keys) > 1:
            raise ValueError("Use only one color representation per light")
        if color_keys and "color_mode" in settings:
            mode = settings["color_mode"]
            expected = (
                "color_temp_kelvin"
                if mode == "color_temp"
                else "white"
                if mode == "white"
                else f"{mode}_color"
            )
            if expected not in color_keys:
                raise ValueError("Color attributes must match the active color mode")
        for key, bounds in (
            ("rgb_color", (255, 255, 255)),
            ("rgbw_color", (255, 255, 255, 255)),
            ("rgbww_color", (255, 255, 255, 255, 255)),
            ("hs_color", (360, 100)),
            ("xy_color", (1, 1)),
        ):
            if key not in settings:
                continue
            color = settings[key]
            if not isinstance(color, list) or len(color) != len(bounds):
                raise ValueError(f"Invalid {key}")
            for component, upper in zip(color, bounds, strict=True):
                _number(component, key, 0, upper)
    return output


def validate_nightlight(value: Any, members: list[str]) -> dict:
    """Normalize an absence ambience without silently selecting room lights."""
    nightlight = {"enabled": False, "lights": {}} | deepcopy(
        _mapping(value, "nightlight")
    )
    if set(nightlight) - {"enabled", "lights"}:
        raise ValueError("Unknown nightlight setting")
    _boolean(nightlight["enabled"], "nightlight.enabled")
    nightlight["lights"] = validate_lamp_states(nightlight["lights"], members)
    if nightlight["enabled"] and not any(
        settings["state"] == "on"
        and all(
            settings.get(key, 1) > 0
            for key in ("brightness", "brightness_pct", "white")
        )
        for settings in nightlight["lights"].values()
    ):
        raise ValueError("An enabled nightlight requires at least one light on")
    return nightlight


def validate_condition(value: Any, depth: int = 0) -> None:
    """Validate the visual condition tree; no templates or arbitrary code."""
    if value is None:
        return
    if depth > 8:
        raise ValueError("Conditions are nested too deeply")
    node = _mapping(value, "condition")
    kind = node.get("type")
    if kind in ("and", "or"):
        children = node.get("conditions")
        if not isinstance(children, list) or not 1 <= len(children) <= 32:
            raise ValueError("A condition group needs 1 to 32 conditions")
        for child in children:
            if child is None:
                raise ValueError("A condition group cannot contain an empty condition")
            validate_condition(child, depth + 1)
    elif kind == "not":
        if node.get("condition") is None:
            raise ValueError("NOT requires a condition")
        validate_condition(node["condition"], depth + 1)
    elif kind == "state":
        _entity(node.get("entity_id"))
        _text(node.get("state"), "condition state")
    elif kind in ("numeric", "sun"):
        if kind == "numeric":
            _entity(node.get("entity_id"))
            if node.get("attribute"):
                _text(node["attribute"], "attribute")
        if node.get("above") is None and node.get("below") is None:
            raise ValueError("A numeric condition requires a bound")
        for key in ("above", "below"):
            if node.get(key) is not None:
                _number(node[key], key, -1e12, 1e12)
        if (
            node.get("above") is not None
            and node.get("below") is not None
            and node["above"] >= node["below"]
        ):
            raise ValueError("Numeric lower bound must be below upper bound")
    elif kind == "time":
        for key in ("after", "before"):
            if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", str(node.get(key, ""))):
                raise ValueError("Time conditions require HH:MM bounds")
    else:
        raise ValueError("Unknown condition type")


def validate_scene(value: Any, members: list[str]) -> dict:
    """Normalize a scene and its lamp settings."""
    scene = deepcopy(_mapping(value, "scene"))
    _identifier(scene.get("id"))
    _text(scene.get("name"), "scene name")
    scene.setdefault("can_turn_on", False)
    _boolean(scene["can_turn_on"], "can_turn_on")
    scene.setdefault("conditions", None)
    validate_condition(scene["conditions"])
    kind = scene.setdefault("type", "halo")
    if kind == "home_assistant":
        _entity(scene.get("scene_entity_id"), "scene")
        if "lights" in scene:
            raise ValueError("A linked scene cannot contain copied lamp settings")
    elif kind == "halo":
        if "scene_entity_id" in scene:
            raise ValueError("A Halo scene cannot also reference a native scene")
        scene["lights"] = validate_lamp_states(scene.get("lights", {}), members)
    else:
        raise ValueError("Unknown scene type")
    return scene


def _transitions(value: Any, *, room: bool) -> dict:
    settings = _mapping(value, "transitions")
    if set(settings) - set(TRANSITIONS):
        raise ValueError("Unknown transition category")
    result = (
        dict.fromkeys(TRANSITIONS, "inherit") if room else TRANSITION_DEFAULTS.copy()
    )
    for key, duration in settings.items():
        if duration is None or (room and duration == "inherit"):
            result[key] = duration
        else:
            result[key] = _number(duration, key, 0, 86400)
    return result


def validate_config(value: Any) -> dict[str, Any]:
    """Normalize and cross-check all settings, without requiring devices online."""
    config = default_config() | deepcopy(_mapping(value, "configuration"))
    if set(config) - set(default_config()):
        raise ValueError("Unknown configuration section")
    _number(config["presence_return_window"], "presence_return_window", 0, 604800)
    if config["sun_entity_id"] is not None:
        _entity(config["sun_entity_id"], "sun")
    config["transitions"] = _transitions(config["transitions"], room=False)
    profiles = _mapping(config["profiles"], "profiles")
    for profile_id, profile in profiles.items():
        _identifier(profile_id)
        _mapping(profile, "profile")
        if profile.get("id") != profile_id:
            raise ValueError("Profile ID differs from its key")
        _text(profile.get("name"), "profile name")
        profile.setdefault("linked", True)
        _boolean(profile["linked"], "linked")
        # Migrate the original one-sided acceleration, including stored evening
        # curves of a linked profile, without requiring inactive curves to exist.
        for period in ("morning", "evening"):
            if isinstance(branch := profile.get(period), dict):
                for curve in branch.values():
                    if (
                        isinstance(curve, dict)
                        and curve.get("interpolation") == "ease_in"
                    ):
                        curve["interpolation"] = "ease_in_out"
        periods = ["morning"] if profile["linked"] else ["morning", "evening"]
        for period in periods:
            branch = _mapping(profile.get(period), period)
            for quantity, lower, upper in (
                ("brightness", 0, 100),
                ("temperature", 1000, 40000),
            ):
                curve = _mapping(branch.get(quantity), quantity)
                curve.setdefault("interpolation", "linear")
                if curve["interpolation"] not in ("linear", "ease_in_out"):
                    raise ValueError("Unknown curve interpolation")
                for bound in ("low_elevation", "high_elevation"):
                    _number(curve.get(bound), bound, -90, 90)
                if curve["low_elevation"] >= curve["high_elevation"]:
                    raise ValueError("Solar elevations must be distinct and ordered")
                for bound in ("low", "high"):
                    _number(curve.get(bound), quantity, lower, upper)
    assigned: set[str] = set()
    rooms = _mapping(config["rooms"], "rooms")
    scene_ids: set[str] = set()
    for room_id, supplied in list(rooms.items()):
        _identifier(room_id)
        room = deepcopy(ROOM_DEFAULTS) | _mapping(supplied, "room")
        if room.get("id", room_id) != room_id:
            raise ValueError("Room ID differs from its key")
        room["id"] = room_id
        rooms[room_id] = room
        room["lights"] = _lights(room["lights"])
        if assigned.intersection(room["lights"]):
            raise ValueError("A light can only belong to one Halo room")
        assigned.update(room["lights"])
        for key in ("presence_entity_id", "lux_entity_id"):
            if room[key] is not None:
                _entity(room[key])
        states = room["presence_states"]
        if not isinstance(states, list) or not states:
            raise ValueError("Presence requires at least one present state")
        for state in states:
            _text(state, "presence state")
            if state in ("unknown", "unavailable"):
                raise ValueError("Unavailable states cannot mean present")
        if room["lux_entity_id"] is not None or room["lux_threshold"] is not None:
            _number(room["lux_threshold"], "lux_threshold", 0, 1e9)
        _number(room["lux_hysteresis"], "lux_hysteresis", 0, 1e9)
        room["lighting_fallback"] = validate_lighting_fallback(
            room["lighting_fallback"]
        )
        for key in ("absence_delay", "manual_pause", "lux_off_delay"):
            _number(room[key], key, 0, 604800)
        for key in (
            "lux_off",
            "allow_off_during_pause",
            "automation_enabled",
            "natural_enabled",
        ):
            _boolean(room[key], key)
        room["transitions"] = _transitions(room["transitions"], room=True)
        room["base"] = validate_lamp_states(room["base"], room["lights"])
        room["nightlight"] = validate_nightlight(room["nightlight"], room["lights"])
        if room["nightlight"]["enabled"] and not room["presence_entity_id"]:
            raise ValueError("An enabled nightlight requires a presence entity")
        if not isinstance(room["associations"], list):
            raise ValueError("Associations must be a list")
        natural_members: set[str] = set()
        for association in room["associations"]:
            _mapping(association, "association")
            _identifier(association.get("profile_id"))
            if association.get("profile_id") not in profiles:
                raise ValueError("Unknown natural profile")
            association["lights"] = _lights(association.get("lights", []))
            if not set(association["lights"]).issubset(room["lights"]):
                raise ValueError(
                    "Natural association contains a light outside its room"
                )
            if natural_members.intersection(association["lights"]):
                raise ValueError("A light can only have one natural profile")
            natural_members.update(association["lights"])
            association.setdefault("brightness_offset", 0)
            _number(association["brightness_offset"], "brightness_offset", -100, 1000)
        if not isinstance(room["scenes"], list):
            raise ValueError("Scenes must be an ordered list")
        room["scenes"] = [
            validate_scene(scene, room["lights"]) for scene in room["scenes"]
        ]
        for scene in room["scenes"]:
            if scene["id"] in scene_ids:
                raise ValueError("Duplicate scene ID")
            scene_ids.add(scene["id"])
    return config
