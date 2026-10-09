"""Current lighting ambience for each Halo room."""

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import HaloRoomEntity, async_setup_room_entities

_RESERVED_STATES = {"off", "manual", "natural", "unknown", "unavailable"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a status sensor to every saved room device, including new rooms."""
    await async_setup_room_entities(
        hass, entry, lambda room_id, room: [HaloRoomStatus(entry.runtime_data, room_id)]
    )


class HaloRoomStatus(HaloRoomEntity, SensorEntity):
    """Expose the room's ambience without generating any lighting commands."""

    _attr_translation_key = "room_status"
    _attr_icon = "mdi:lightbulb-auto-outline"

    def __init__(self, manager: Any, room_id: str) -> None:
        super().__init__(manager, room_id, "status")

    @property
    def available(self) -> bool:
        """Never mistake a room whose lamps are all offline for an off room."""
        engine = self.manager.engines.get(self.room_id)
        return bool(super().available and engine is not None and engine.available)

    @property
    def _lighting_status(self) -> dict[str, str | None] | None:
        engine = self.manager.engines.get(self.room_id)
        return engine.lighting_status if engine is not None else None

    def _scene_name(self, scene_id: str | None) -> str | None:
        return next(
            (
                scene["name"]
                for scene in self.room.get("scenes", [])
                if scene["id"] == scene_id
            ),
            None,
        )

    @property
    def native_value(self) -> str | None:
        """Translate standard modes natively and keep user-authored scene names."""
        if not (status := self._lighting_status):
            return None
        if status["mode"] == "scene":
            name = self._scene_name(status["scene_id"])
            # A custom name must not become HA's unavailable/unknown sentinel
            # or accidentally use one of our built-in state translations.
            return f"scene: {name}" if name in _RESERVED_STATES else name
        return status["mode"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Keep a stable mode and scene ID available for automations."""
        status = self._lighting_status
        return {
            "mode": status["mode"] if status else None,
            "scene_id": status["scene_id"] if status else None,
            "scene_name": self._scene_name(status["scene_id"]) if status else None,
        }
