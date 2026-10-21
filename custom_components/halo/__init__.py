"""Halo: room-based lighting orchestration and its embedded configuration panel."""

import probatio
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .manager import HaloError, HaloManager
from .panel import async_register_panel, async_remove_panel
from .websocket import async_register

PLATFORMS = (
    Platform.LIGHT,
    Platform.SWITCH,
    Platform.SCENE,
    Platform.SENSOR,
)
type HaloConfigEntry = ConfigEntry[HaloManager]


@callback
def _register_manual_services(hass: HomeAssistant) -> None:
    """Expose explicit hold actions; resolve the manager after every reload."""

    async def handle(call: ServiceCall) -> None:
        if not (manager := hass.data.get(DOMAIN, {}).get("manager")):
            raise HaloError("not_loaded", "Halo is not loaded")
        try:
            if call.service == "manual_hold":
                await manager.async_manual_hold(call.data["room_id"], call.context)
            else:
                await manager.async_manual_resume(call.data["room_id"], call.context)
        except ValueError as err:
            if str(err) in ("manual_control_disabled", "automation_disabled"):
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key=str(err)
                ) from err
            raise ServiceValidationError(str(err)) from err

    for name in ("manual_hold", "manual_resume"):
        hass.services.async_register(
            DOMAIN,
            name,
            handle,
            schema=probatio.Schema({probatio.Required("room_id"): str}),
        )


@callback
def _remove_manual_services(hass: HomeAssistant) -> None:
    for name in ("manual_hold", "manual_resume"):
        hass.services.async_remove(DOMAIN, name)


async def async_setup_entry(hass: HomeAssistant, entry: HaloConfigEntry) -> bool:
    """Start persisted rooms and expose the singleton panel."""
    data = hass.data.setdefault(DOMAIN, {})
    manager = entry.runtime_data = HaloManager(hass, entry)
    try:
        await manager.async_load()
        data["manager"] = manager
        _register_manual_services(hass)
        if not data.get("websocket_registered"):
            async_register(hass)
            data["websocket_registered"] = True
        await async_register_panel(hass)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        await manager.async_stop()
        data.pop("manager", None)
        _remove_manual_services(hass)
        async_remove_panel(hass)
        raise
    manager.async_notify()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HaloConfigEntry) -> bool:
    """Release platforms, timers, listeners and the panel."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_stop()
        hass.data[DOMAIN].pop("manager", None)
        _remove_manual_services(hass)
        async_remove_panel(hass)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete configuration only when the user removes Halo."""
    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}").async_remove()
