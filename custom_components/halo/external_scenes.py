"""Inspect public scene/group metadata without activating or copying a scene."""

from dataclasses import dataclass, field

from homeassistant.core import HomeAssistant, valid_entity_id
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

_MEMBERS = (list, tuple, set, frozenset)


@dataclass
class Composition:
    """Known leaf targets; complete is false when any branch cannot be resolved."""

    lights: set[str] = field(default_factory=set)
    other: set[str] = field(default_factory=set)
    nodes: set[str] = field(default_factory=set)
    complete: bool = True
    blocked: bool = False


def composition(hass: HomeAssistant, entity_ids: list[str]) -> Composition:
    """Expand scene/group memberships, including unavailable registered groups."""
    result = Composition()
    registry = er.async_get(hass)

    active: set[str] = set()
    visited: set[str] = set()
    # An explicit DFS stack bounds work to the metadata graph, even with deep
    # nesting or many branches referring to the same group. Exit markers retain
    # cycle detection without Python recursion or copying every ancestor set.
    pending = [(entity_id, False) for entity_id in reversed(entity_ids)]
    while pending:
        entity_id, leaving = pending.pop()
        if leaving:
            active.discard(entity_id)
            continue
        result.nodes.add(entity_id)
        if entity_id in active:
            result.complete = False
            continue
        if entity_id in visited:
            continue
        visited.add(entity_id)
        entity = registry.async_get(entity_id)
        if entity and entity.platform == DOMAIN:
            result.blocked = True
        state = hass.states.get(entity_id)
        attributes = state.attributes if state else {}
        members = attributes.get("entity_id")
        domain = entity_id.split(".", 1)[0]
        container = domain in ("scene", "group") or (
            domain == "light"
            and (
                isinstance(members, _MEMBERS)
                or attributes.get("is_hue_group") is True
                or entity
                and (
                    entity.platform == "group"
                    or entity.platform == "hue"
                    and entity.translation_key == "hue_grouped_light"
                )
            )
        )
        if container:
            if isinstance(members, _MEMBERS):
                active.add(entity_id)
                pending.append((entity_id, True))
                for member in members:
                    if isinstance(member, str) and valid_entity_id(member):
                        pending.append((member, False))
                    else:
                        result.complete = False
                continue
            result.complete = False
            continue
        if domain == "light":
            result.lights.add(entity_id)
        elif domain not in ("scene", "group"):
            result.other.add(entity_id)

    return result


def inspect_scene(hass: HomeAssistant, room_lights: list[str], entity_id: str) -> dict:
    """Compare known composition only, never claim opaque providers are empty."""
    if not valid_entity_id(entity_id) or not entity_id.startswith("scene."):
        raise ValueError("Select a scene entity")
    source = composition(hass, [entity_id])
    room = composition(hass, room_lights)
    state = hass.states.get(entity_id)
    return {
        "entity_id": entity_id,
        "name": state.name if state else entity_id,
        # An unactivated native scene is legitimately unknown.
        "available": state is not None and state.state != "unavailable",
        "complete": source.complete and room.complete,
        "lights": sorted(source.lights),
        "outside_lights": sorted(source.lights - room.lights) if room.complete else [],
        "missing_lights": sorted(room.lights - source.lights)
        if source.complete and room.complete
        else [],
        "other_entities": sorted(source.other),
        "blocked": source.blocked,
    }


def scene_problem(hass: HomeAssistant, scene: dict) -> str | None:
    """Validate executable references independently of a scene's timestamp."""
    if scene.get("type", "halo") != "home_assistant":
        return None
    entity_id = scene["scene_entity_id"]
    if composition(hass, [entity_id]).blocked:
        return "external_scene_recursive"
    state = hass.states.get(entity_id)
    if state is None or state.state == "unavailable":
        return "external_scene_unavailable"
    return None


def feedback_lights(
    hass: HomeAssistant, room_lights: list[str], entity_id: str
) -> set[str]:
    """Return configured room entities potentially affected by the native call."""
    source = composition(hass, [entity_id])
    if not source.complete:
        return set(room_lights)
    affected = set()
    for light in room_lights:
        target = composition(hass, [light])
        if not target.complete or target.lights & source.lights:
            affected.add(light)
    return affected
