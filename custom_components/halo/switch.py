"""Switches for Halo's automatic and natural lighting modes."""

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import HaloRoomEntity, async_setup_room_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create both switches for each configured room."""
    await async_setup_room_entities(
        hass,
        entry,
        lambda room_id, room: [
            HaloModeSwitch(entry.runtime_data, room_id, mode)
            for mode in ("automation", "natural")
        ],
    )


class HaloModeSwitch(HaloRoomEntity, SwitchEntity):
    """Persist a room mode without making optimistic state assumptions."""

    def __init__(self, manager: Any, room_id: str, mode: str) -> None:
        super().__init__(manager, room_id, mode)
        self.mode = mode
        self._attr_translation_key = mode

    @property
    def is_on(self) -> bool:
        return bool(self.room.get(f"{self.mode}_enabled", self.mode == "natural"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.manager.async_set_mode(
            self.room_id, self.mode, True, context=self._context
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.manager.async_set_mode(
            self.room_id, self.mode, False, context=self._context
        )
