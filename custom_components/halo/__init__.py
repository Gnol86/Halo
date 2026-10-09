"""Halo: the foundation for whole-home lighting orchestration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load Halo. Lighting behavior will be implemented in a later milestone."""
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Halo; this foundation does not allocate runtime resources yet."""
    return True
