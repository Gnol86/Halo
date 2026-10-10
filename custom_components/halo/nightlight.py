"""Check known group overlaps without changing the explicit command targets."""

from homeassistant.core import HomeAssistant

from .external_scenes import composition


def nightlight_conflicts(hass: HomeAssistant, room: dict) -> bool:
    """A room group must not turn off a leaf requested on by its nightlight."""
    nightlight = room.get("nightlight", {})
    if not nightlight.get("enabled"):
        return False
    on_targets = [
        entity_id
        for entity_id, settings in nightlight.get("lights", {}).items()
        if settings.get("state") == "on"
        and all(
            settings.get(key, 1) > 0
            for key in ("brightness", "brightness_pct", "white")
        )
    ]
    off_targets = [
        entity_id for entity_id in room["lights"] if entity_id not in on_targets
    ]
    on = composition(hass, on_targets)
    off = composition(hass, off_targets)
    return bool(
        on.lights & off.lights
        or set(on_targets) & off.nodes
        or set(off_targets) & on.nodes
    )
