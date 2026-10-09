"""Halo: room-based lighting orchestration and its embedded configuration panel."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .manager import HaloManager
from .panel import async_register_panel, async_remove_panel
from .websocket import async_register

PLATFORMS = (Platform.LIGHT, Platform.SWITCH, Platform.BUTTON, Platform.SCENE)
type HaloConfigEntry = ConfigEntry[HaloManager]


async def async_setup_entry(hass: HomeAssistant, entry: HaloConfigEntry) -> bool:
    """Start persisted rooms and expose the singleton panel."""
    data = hass.data.setdefault(DOMAIN, {})
    manager = entry.runtime_data = HaloManager(hass, entry)
    try:
        await manager.async_load()
        data["manager"] = manager
        if not data.get("websocket_registered"):
            async_register(hass)
            data["websocket_registered"] = True
        await async_register_panel(hass)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        await manager.async_stop()
        data.pop("manager", None)
        async_remove_panel(hass)
        raise
    manager.async_notify()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HaloConfigEntry) -> bool:
    """Release platforms, timers, listeners and the panel."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_stop()
        hass.data[DOMAIN].pop("manager", None)
        async_remove_panel(hass)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete configuration only when the user removes Halo."""
    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}").async_remove()
