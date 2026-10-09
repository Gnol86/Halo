"""Resume Halo's automation after a manual pause or disabled mode."""

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import HaloRoomEntity, async_setup_room_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Expose one resume action per configured room."""
    await async_setup_room_entities(
        hass,
        entry,
        lambda room_id, room: [HaloResumeButton(entry.runtime_data, room_id)],
    )


class HaloResumeButton(HaloRoomEntity, ButtonEntity):
    """Enable automatic mode, clear the pause and reevaluate the room."""

    _attr_translation_key = "resume"

    def __init__(self, manager: Any, room_id: str) -> None:
        super().__init__(manager, room_id, "resume")

    async def async_press(self) -> None:
        await self.manager.async_resume(self.room_id, context=self._context)
