"""Aggregate light command for each Halo room."""

from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import HaloRoomEntity, async_setup_room_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add room lights now and as rooms are configured."""
    await async_setup_room_entities(
        hass, entry, lambda room_id, room: [HaloRoomLight(entry.runtime_data, room_id)]
    )


class HaloRoomLight(HaloRoomEntity, LightEntity):
    """A room command whose state reflects the underlying lamps."""

    _attr_translation_key = "room"
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF

    def __init__(self, manager: Any, room_id: str) -> None:
        super().__init__(manager, room_id, "light")

    @property
    def available(self) -> bool:
        """The light is unavailable only when no managed lamp is available."""
        engine = self.manager.engines.get(self.room_id)
        return bool(super().available and engine is not None and engine.available)

    @property
    def is_on(self) -> bool:
        """At least one real lamp must be on; sending a command is insufficient."""
        engine = self.manager.engines.get(self.room_id)
        return bool(engine is not None and engine.is_on)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Apply the current scene or normal room ambience."""
        await self.manager.async_room_command(
            self.room_id, "turn_on", context=self._context
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the room and enter the common manual pause."""
        await self.manager.async_room_command(
            self.room_id, "turn_off", context=self._context
        )
