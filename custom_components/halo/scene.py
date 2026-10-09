"""Expose scenes authored in Halo as native Home Assistant scenes."""

from typing import Any

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import HaloRoomEntity, async_setup_room_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Keep scene entities synchronized with the room's saved scenes."""
    await async_setup_room_entities(
        hass,
        entry,
        lambda room_id, room: [
            HaloScene(entry.runtime_data, room_id, scene["id"])
            for scene in room.get("scenes", [])
        ],
    )


class HaloScene(HaloRoomEntity, Scene):
    """Launch a named ambience and activate the room's manual pause."""

    def __init__(self, manager: Any, room_id: str, scene_id: str) -> None:
        super().__init__(manager, room_id, f"scene_{scene_id}")
        self.scene_id = scene_id

    @property
    def name(self) -> str:
        """Custom scene names remain unchanged across locale changes."""
        return next(
            (
                scene["name"]
                for scene in self.room.get("scenes", [])
                if scene["id"] == self.scene_id
            ),
            self.scene_id,
        )

    @property
    def available(self) -> bool:
        return super().available and any(
            scene["id"] == self.scene_id for scene in self.room.get("scenes", [])
        )

    async def async_activate(self, **kwargs: Any) -> None:
        """Let the room engine arbitrate a deliberate scene command."""
        await self.manager.async_activate_scene(
            self.room_id, self.scene_id, context=self._context
        )
