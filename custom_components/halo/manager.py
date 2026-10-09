"""Own Halo configuration, room engines and the authenticated panel data."""

import asyncio
import logging
from collections.abc import Callable
from copy import deepcopy
from typing import Any

from homeassistant.auth.models import User
from homeassistant.auth.permissions.const import POLICY_CONTROL, POLICY_READ
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .engine import HaloRoomEngine
from .models import (
    default_config,
    validate_config,
    validate_lamp_states,
    validate_scene,
)

_LOGGER = logging.getLogger(__name__)


class HaloError(HomeAssistantError):
    """An error code the panel can translate without parsing English messages."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class HaloManager:
    """Keep the engine running independently of any connected browser."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.config = default_config()
        self.runtime_state: dict[str, Any] = {}
        self.engines: dict[str, HaloRoomEngine] = {}
        self.revision = 0
        self._store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}", atomic_writes=True)
        self._last_stored: dict | None = None
        self._loaded = False
        self._listeners: set[Callable[[], None]] = set()
        self._unsubscribers: list[Callable[[], None]] = []
        self._config_lock = asyncio.Lock()
        self._store_lock = asyncio.Lock()
        self._edits: dict[str, tuple[str, str]] = {}
        self._stopped = False

    async def async_load(self) -> None:
        """Load versioned settings and start one engine per saved room."""
        if stored := await self._store.async_load():
            self.config = validate_config(stored["config"])
            self.runtime_state = stored.get("runtime", {})
            self.revision = stored.get("revision", 0)
            self._last_stored = deepcopy(stored)
        self._loaded = True
        for room_id in self.config["rooms"]:
            engine = self.engines[room_id] = HaloRoomEngine(self.hass, self, room_id)
            await engine.async_start()
        for event in (
            ar.EVENT_AREA_REGISTRY_UPDATED,
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            dr.EVENT_DEVICE_REGISTRY_UPDATED,
        ):
            self._unsubscribers.append(
                self.hass.bus.async_listen(event, self._registry_changed)
            )

    @callback
    def _registry_changed(self, event: Any) -> None:
        """Follow room renames without changing device or entity identities."""
        if event.event_type == ar.EVENT_AREA_REGISTRY_UPDATED:
            devices = dr.async_get(self.hass)
            for room_id in self.engines:
                if device := devices.async_get_device_by_identifier(
                    (DOMAIN, room_id), self.entry.entry_id
                ):
                    name = self.room_name(room_id)
                    if device.name != name:
                        devices.async_update_device(device.id, name=name)
        self.async_notify()

    @callback
    def room_name(self, room_id: str) -> str:
        """Resolve the current Home Assistant area name."""
        area = ar.async_get(self.hass).async_get_area(room_id)
        return area.name if area else room_id

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Listen for changes, returning an idempotent unsubscribe callback."""
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    @callback
    def async_notify(self) -> None:
        """Notify entity platforms and panel subscribers."""
        if self._stopped:
            return
        for listener in tuple(self._listeners):
            try:
                listener()
            except Exception:
                _LOGGER.exception("Error in Halo state listener")
        self.hass.bus.async_fire("halo_updated")

    async def async_persist_runtime(self) -> None:
        """Persist configuration and deadlines under a single storage lock."""
        async with self._store_lock:
            data = deepcopy(
                {
                    "config": self.config,
                    "runtime": self.runtime_state,
                    "revision": self.revision,
                }
            )
            if data != self._last_stored:
                await self._store.async_save(data)
                self._last_stored = data

    def _validate_references(self, config: dict) -> None:
        registry = er.async_get(self.hass)
        areas = ar.async_get(self.hass)
        for room_id, room in config["rooms"].items():
            if (
                not areas.async_get_area(room_id)
                and room_id not in self.config["rooms"]
            ):
                raise ValueError("Select an existing Home Assistant area")
            for entity_id in room["lights"]:
                entity = registry.async_get(entity_id)
                if entity and entity.platform == DOMAIN:
                    raise ValueError("Halo lights cannot be selected as members")
                state = self.hass.states.get(entity_id)
                if not entity and not state:
                    old = self.config["rooms"].get(room_id, {}).get("lights", [])
                    if entity_id not in old:
                        raise ValueError("Select an existing light entity")
            for association in room["associations"]:
                for entity_id in association["lights"]:
                    state = self.hass.states.get(entity_id)
                    modes = (
                        state.attributes.get("supported_color_modes", [])
                        if state
                        else []
                    )
                    if modes and not set(modes) - {"onoff"}:
                        raise ValueError("Natural profiles require dimmable lights")

    def _engine(self, room_id: str) -> HaloRoomEngine:
        if room_id not in self.engines:
            raise HaloError("not_found", "Room no longer exists")
        return self.engines[room_id]

    def _check_revision(self, revision: int) -> None:
        if revision != self.revision:
            raise HaloError("conflict", "Configuration changed; refresh before saving")

    def _check_idle(self, room_id: str | None = None) -> None:
        engines = [self._engine(room_id)] if room_id else self.engines.values()
        if any(engine.status.get("editing") for engine in engines):
            raise HaloError(
                "edit_locked", "A scene editor currently controls this room"
            )

    async def _commit_config(self, config: dict) -> None:
        """Publish new settings only after the durable write has succeeded."""
        async with self._store_lock:
            data = deepcopy(
                {
                    "config": config,
                    "runtime": self.runtime_state,
                    "revision": self.revision + 1,
                }
            )
            await self._store.async_save(data)
            self.config = config
            self.revision += 1
            self._last_stored = data

    async def async_save_config(self, config: dict, revision: int) -> None:
        """Validate before updating; reject stale or concurrent editor writes."""
        async with self._config_lock:
            self._check_revision(revision)
            self._check_idle()
            try:
                normalized = validate_config(config)
                self._validate_references(normalized)
            except ValueError as err:
                raise HaloError("invalid_config", str(err)) from err
            removed = {
                room_id: engine
                for room_id, engine in self.engines.items()
                if room_id not in normalized["rooms"]
            }
            for engine in removed.values():
                await engine.async_stop()
            try:
                await self._commit_config(normalized)
            except Exception:
                for engine in removed.values():
                    await engine.async_start()
                raise
            # No await between publishing config and updating the engine map:
            # snapshots and entity listeners must always see a consistent pair.
            for room_id in removed:
                self.engines.pop(room_id)
                self.runtime_state.pop(room_id, None)
                self._edits.pop(room_id, None)
                registry = dr.async_get(self.hass)
                if device := registry.async_get_device_by_identifier(
                    (DOMAIN, room_id), self.entry.entry_id
                ):
                    registry.async_update_device(
                        device.id, remove_config_entry_id=self.entry.entry_id
                    )
            added = set(normalized["rooms"]) - self.engines.keys()
            for room_id in added:
                self.engines[room_id] = HaloRoomEngine(self.hass, self, room_id)
            for room_id in normalized["rooms"]:
                if room_id in added:
                    await self.engines[room_id].async_start()
                else:
                    await self.engines[room_id].async_reconfigure()
            self.async_notify()

    async def _authorize_context(self, room_id: str, context: Context | None) -> None:
        """Apply member permissions to native entity commands as well as WebSocket."""
        if context and context.user_id:
            user = await self.hass.auth.async_get_user(context.user_id)
            if user is None:
                raise Unauthorized(user_id=context.user_id)
            self.check_control(user, room_id)

    async def async_room_command(
        self, room_id: str, command: str, context: Context | None = None
    ) -> None:
        await self._authorize_context(room_id, context)
        self._check_idle(room_id)
        engine = self._engine(room_id)
        if command == "turn_on":
            await engine.async_turn_on(context=context)
        elif command == "turn_off":
            await engine.async_turn_off(context=context)
        else:
            raise HaloError("invalid_config", "Unknown room command")

    async def async_set_mode(
        self, room_id: str, mode: str, enabled: bool, context: Context | None = None
    ) -> None:
        await self._authorize_context(room_id, context)
        async with self._config_lock:
            self._check_idle(room_id)
            self.revision += 1
            await self._engine(room_id).async_set_mode(mode, enabled, context=context)
            await self.async_persist_runtime()
            self.async_notify()

    async def async_resume(self, room_id: str, context: Context | None = None) -> None:
        await self._authorize_context(room_id, context)
        async with self._config_lock:
            self._check_idle(room_id)
            self.revision += 1
            await self._engine(room_id).async_resume(context=context)
            await self.async_persist_runtime()
            self.async_notify()

    async def async_activate_scene(
        self, room_id: str, scene_id: str, context: Context | None = None
    ) -> None:
        await self._authorize_context(room_id, context)
        self._check_idle(room_id)
        await self._engine(room_id).async_activate_scene(scene_id, context=context)

    async def async_begin_edit(self, room_id: str, owner: str) -> str:
        async with self._config_lock:
            self._check_idle(room_id)
            token = await self._engine(room_id).async_begin_edit(owner)
            self._edits[room_id] = (token, owner)
            return token

    def _check_edit(self, room_id: str, token: str, owner: str) -> HaloRoomEngine:
        if self._edits.get(room_id) != (token, owner):
            raise HaloError("invalid_edit", "This connection does not own the editor")
        engine = self._engine(room_id)
        if not engine.status.get("editing"):
            self._edits.pop(room_id, None)
            raise HaloError("invalid_edit", "The editor session expired")
        return engine

    async def async_preview(
        self, room_id: str, token: str, owner: str, lights: dict
    ) -> None:
        engine = self._check_edit(room_id, token, owner)
        try:
            settings = validate_lamp_states(
                lights, self.config["rooms"][room_id]["lights"]
            )
        except ValueError as err:
            raise HaloError("invalid_config", str(err)) from err
        await engine.async_preview(token, settings)

    async def async_touch_edit(self, room_id: str, token: str, owner: str) -> None:
        await self._check_edit(room_id, token, owner).async_touch_edit(token)

    async def async_end_edit(
        self,
        room_id: str,
        token: str,
        owner: str,
        save: bool,
        scene: dict | None = None,
        revision: int | None = None,
    ) -> None:
        async with self._config_lock:
            engine = self._check_edit(room_id, token, owner)
            if save:
                self._check_revision(revision)
                try:
                    normalized = validate_scene(
                        scene, self.config["rooms"][room_id]["lights"]
                    )
                    updated = deepcopy(self.config)
                    scenes = updated["rooms"][room_id]["scenes"]
                    for index, existing in enumerate(scenes):
                        if existing["id"] == normalized["id"]:
                            scenes[index] = normalized
                            break
                    else:
                        scenes.append(normalized)
                    updated = validate_config(updated)
                except ValueError as err:
                    raise HaloError("invalid_config", str(err)) from err

                async def commit() -> None:
                    await self._commit_config(updated)

                await engine.async_commit_edit(token, commit)
            else:
                await engine.async_end_edit(token, save=False)
            self._edits.pop(room_id, None)
            self.async_notify()

    def check_control(self, user: User, room_id: str) -> None:
        """Respect Home Assistant's entity permissions even on aggregate commands."""
        self._engine(room_id)
        if not all(
            user.permissions.check_entity(entity_id, POLICY_CONTROL)
            for entity_id in self.config["rooms"][room_id]["lights"]
        ):
            raise Unauthorized(user_id=user.id)

    @callback
    def snapshot(self, user: User) -> dict:
        """Produce a detached, permission-filtered snapshot for a browser."""
        config = deepcopy(self.config)
        config["rooms"] = {
            key: room
            for key, room in config["rooms"].items()
            if all(
                user.permissions.check_entity(eid, POLICY_READ)
                for eid in room["lights"]
            )
        }
        registry, devices = er.async_get(self.hass), dr.async_get(self.hass)
        areas = [
            {"id": area.id, "name": area.name}
            for area in ar.async_get(self.hass).async_list_areas()
        ]
        known = {area["id"] for area in areas}
        areas.extend(
            {"id": key, "name": key} for key in config["rooms"] if key not in known
        )
        visible_states = [
            state
            for state in self.hass.states.async_all()
            if user.permissions.check_entity(state.entity_id, POLICY_READ)
        ]
        groups: dict[str, list[str]] = {}
        member_of: dict[str, list[str]] = {}
        for state in visible_states:
            registered = registry.async_get(state.entity_id)
            members = state.attributes.get("entity_id")
            if not (
                (registered and registered.platform == "group")
                or isinstance(members, (list, tuple))
            ):
                continue
            # Membership is metadata too: never disclose an unreadable entity
            # through another group's attributes or reverse membership list.
            visible_members = (
                [
                    member
                    for member in members
                    if isinstance(member, str)
                    and user.permissions.check_entity(member, POLICY_READ)
                ]
                if isinstance(members, (list, tuple))
                else []
            )
            groups[state.entity_id] = list(dict.fromkeys(visible_members))
            for member in groups[state.entity_id]:
                member_of.setdefault(member, []).append(state.entity_id)
        lights, entities = [], []
        for state in visible_states:
            entity_id = state.entity_id
            attributes = dict(state.attributes)
            if isinstance(attributes.get("entity_id"), (list, tuple)):
                attributes["entity_id"] = groups[entity_id].copy()
            item = {
                "entity_id": entity_id,
                "name": state.name,
                "state": state.state,
                "attributes": attributes,
            }
            entities.append(item)
            if state.domain != "light":
                continue
            registered = registry.async_get(entity_id)
            if registered and registered.platform == DOMAIN:
                continue
            area_id = registered.area_id if registered else None
            if not area_id and registered and registered.device_id:
                if device := devices.async_get(registered.device_id):
                    area_id = device.area_id
            lights.append(
                item
                | {
                    "is_group": entity_id in groups,
                    "group_members": groups.get(entity_id, []).copy(),
                    "member_of": member_of.get(entity_id, []).copy(),
                    "area_id": area_id,
                    "available": state.state not in ("unavailable", "unknown"),
                    "supported_color_modes": state.attributes.get(
                        "supported_color_modes", []
                    ),
                    "supported_features": state.attributes.get("supported_features", 0),
                    "min_color_temp_kelvin": state.attributes.get(
                        "min_color_temp_kelvin"
                    ),
                    "max_color_temp_kelvin": state.attributes.get(
                        "max_color_temp_kelvin"
                    ),
                }
            )
        return {
            "config": config,
            "revision": self.revision,
            "is_admin": user.is_admin,
            "areas": areas,
            "lights": lights,
            "entities": entities,
            "status": {key: self.engines[key].status for key in config["rooms"]},
        }

    async def async_stop(self) -> None:
        """Stop all rooms, release listeners and flush pending runtime state."""
        self._stopped = True
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
        for engine in self.engines.values():
            await engine.async_stop()
        if self._loaded:
            await self.async_persist_runtime()
        self._listeners.clear()
        self._edits.clear()

    async def async_delete_storage(self) -> None:
        """Remove data only when the integration itself is removed."""
        await self._store.async_remove()
