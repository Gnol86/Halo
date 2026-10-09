"""Shared room entities and dynamic platform lifecycle for Halo."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import async_get_current_platform

from .const import DOMAIN, NAME


class HaloRoomEntity(Entity):
    """An entity belonging to a stable Home Assistant area."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: Any, room_id: str, key: str) -> None:
        """Keep references to the manager; configuration remains live."""
        self.manager = manager
        self.room_id = room_id
        self._attr_unique_id = f"{room_id}_{key}"

    @property
    def room(self) -> dict[str, Any]:
        """Return current configuration, including mode changes."""
        return self.manager.config["rooms"].get(self.room_id, {})

    @property
    def available(self) -> bool:
        """Controls remain available even when the physical lamps are offline."""
        return self.room_id in self.manager.config["rooms"]

    @property
    def device_info(self) -> DeviceInfo:
        """Use the area identifier rather than its mutable display name."""
        name = self.manager.room_name(self.room_id)
        area = ar.async_get(self.manager.hass).async_get_area(self.room_id)
        return DeviceInfo(
            identifiers={(DOMAIN, self.room_id)},
            name=name,
            manufacturer=NAME,
            model=NAME,
            entry_type=dr.DeviceEntryType.SERVICE,
            suggested_area=name if area else None,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to changes and attach the logical device to its area."""
        await super().async_added_to_hass()
        registry = dr.async_get(self.hass)
        if (
            device := registry.async_get_device_by_identifier(
                (DOMAIN, self.room_id), self.manager.entry.entry_id
            )
        ) and (ar.async_get(self.hass).async_get_area(self.room_id) is not None):
            registry.async_update_device(device.id, area_id=self.room_id)
        self.async_on_remove(
            self.manager.async_add_listener(self._async_manager_updated)
        )

    @callback
    def _async_manager_updated(self) -> None:
        """Publish actual states rather than optimistically changing lamps."""
        self.async_write_ha_state()


async def async_setup_room_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    factory: Callable[[str, dict[str, Any]], Iterable[HaloRoomEntity]],
) -> None:
    """Reconcile a platform when rooms or scenes change without a reload.

    Additions and removals are serialized, including a rapid delete/recreate.
    Remove registry entries as well as states so deleted rooms leave no orphan
    entities, including entities disabled by the user.
    """
    manager = entry.runtime_data
    platform = async_get_current_platform()
    registry = er.async_get(hass)
    entities: dict[str, HaloRoomEntity] = {}
    pending: dict[str, HaloRoomEntity] | None = None
    requested: frozenset[str] | None = None
    task: asyncio.Task[None] | None = None
    stopped = False

    async def async_reconcile() -> None:
        nonlocal pending, task
        try:
            while pending is not None and not stopped:
                desired, pending = pending, None
                for registered in list(
                    er.async_entries_for_config_entry(registry, entry.entry_id)
                ):
                    if (
                        registered.domain == platform.domain
                        and registered.platform == DOMAIN
                        and registered.unique_id not in desired
                    ):
                        if registered.entity_id in platform.entities:
                            await platform.async_remove_entity(registered.entity_id)
                        registry.async_remove(registered.entity_id)
                for unique_id in entities.keys() - desired.keys():
                    del entities[unique_id]
                additions = [
                    entity
                    for unique_id, entity in desired.items()
                    if unique_id not in entities
                ]
                if additions:
                    await platform.async_add_entities(additions)
                entities.update({entity.unique_id: entity for entity in additions})
        finally:
            task = None

    @callback
    def async_changed() -> None:
        nonlocal pending, requested, task
        if stopped:
            return
        desired = {
            entity.unique_id: entity
            for room_id, room in manager.config["rooms"].items()
            for entity in factory(room_id, room)
        }
        signature = frozenset(desired)
        if signature == requested:
            return
        requested = signature
        pending = desired
        if task is None:
            task = entry.async_create_task(
                hass,
                async_reconcile(),
                f"Halo {platform.domain} entities",
                eager_start=False,
            )

    unsubscribe = manager.async_add_listener(async_changed)

    @callback
    def async_stop() -> None:
        nonlocal stopped, pending
        stopped = True
        pending = None
        unsubscribe()
        if task is not None:
            task.cancel()

    entry.async_on_unload(async_stop)
    async_changed()
    if task is not None:
        await task
