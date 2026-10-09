"""Convert native Home Assistant scene configuration into a detached Halo scene."""

from copy import deepcopy
from typing import Any
from uuid import uuid4

from .models import validate_lamp_states, validate_scene

# Match Home Assistant 2026.10 light/reproduce_state.py's legacy color priority.
# Keep this explicit: the reproduction module is not a public parsing API.
_COLOR_ATTRIBUTES = {
    "hs": "hs_color",
    "color_temp": "color_temp_kelvin",
    "rgb": "rgb_color",
    "rgbw": "rgbw_color",
    "rgbww": "rgbww_color",
    "xy": "xy_color",
}


def _lamp_settings(value: Any) -> dict:
    """Retain only reproducible light attributes from one native scene member."""
    source = value if isinstance(value, dict) else {"state": value}
    state = source.get("state")
    if isinstance(state, bool):
        state = "on" if state else "off"
    target = {"state": state}
    if state == "off":
        # HA reproduces an off scene member with turn_off only. Stored color
        # attributes may be null or stale and must never prevent an extinction.
        return target
    for key in ("brightness", "effect"):
        if source.get(key) is not None:
            target[key] = deepcopy(source[key])

    mode = source.get("color_mode")
    if mode in (None, "unknown"):
        for attribute in _COLOR_ATTRIBUTES.values():
            if source.get(attribute) is not None:
                target[attribute] = deepcopy(source[attribute])
                break
    elif mode in _COLOR_ATTRIBUTES:
        attribute = _COLOR_ATTRIBUTES[mode]
        if source.get(attribute) is None:
            raise ValueError(f"Color mode {mode} requires {attribute}")
        target["color_mode"] = mode
        target[attribute] = deepcopy(source[attribute])
    elif mode == "white":
        if source.get("brightness") is None:
            raise ValueError("Color mode white requires brightness")
        target["color_mode"] = mode
        target["white"] = deepcopy(source["brightness"])
    elif mode in ("brightness", "onoff"):
        target["color_mode"] = mode
    else:
        raise ValueError("Invalid color mode")
    return target


def normalize_scene_import(config: Any, members: list[str]) -> dict:
    """Filter before validating, without reading states or activating the source.

    Entities not explicitly selected in this room, including group members, are
    ignored. The caller rejects an empty intersection before returning a draft.
    """
    if not isinstance(config, dict) or not isinstance(config.get("entities"), dict):
        raise ValueError("Scene configuration requires an entities object")
    entities = config["entities"]
    lights = {}
    for entity_id in members:
        if entity_id not in entities:
            continue
        try:
            target = _lamp_settings(entities[entity_id])
            lights.update(validate_lamp_states({entity_id: target}, members))
        except (ValueError, TypeError) as err:
            raise ValueError(f"{entity_id}: {err}") from err
    scene = validate_scene(
        {
            "id": uuid4().hex,
            "name": config.get("name"),
            "conditions": None,
            "can_turn_on": False,
            "lights": lights,
        },
        members,
    )
    return {"scene": scene, "ignored_entities": len(entities) - len(lights)}
