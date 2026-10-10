"""Own Halo configuration, room engines and the authenticated panel data."""

import asyncio
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
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
from .external_scenes import composition, feedback_lights, inspect_scene, scene_problem
from .models import (
    default_config,
    validate_config,
    validate_lamp_states,
    validate_nightlight,
    validate_scene,
)
from .nightlight import nightlight_conflicts
from .scene_import import normalize_scene_import

_LOGGER = logging.getLogger(__name__)
_GROUP_MEMBER_TYPES = (list, tuple, set, frozenset)
_EXTERNAL_CALL: ContextVar[str | None] = ContextVar("halo_external_scene", default=None)


def _only_manual_scenes_added(previous: dict, current: dict) -> bool:
    """Names and additional manual drafts do not change lighting decisions."""
    old_scenes, new_scenes = previous["scenes"], current["scenes"]
    return (
        previous | {"scenes": new_scenes} == current
        and len(new_scenes) >= len(old_scenes)
        and all(
            old | {"name": new["name"]} == new
            for old, new in zip(old_scenes, new_scenes, strict=False)
        )
        and all(
            scene["conditions"] is None and not scene["can_turn_on"]
            for scene in new_scenes[len(old_scenes) :]
        )
    )


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
        self._external_contexts: set[str] = set()

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
            if nightlight_conflicts(self.hass, room):
                raise ValueError("A room group would switch off a selected nightlight")
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
            old_sources = {
                item.get("scene_entity_id")
                for item in self.config["rooms"].get(room_id, {}).get("scenes", [])
            }
            for scene in room["scenes"]:
                if scene["type"] != "home_assistant":
                    continue
                source = scene["scene_entity_id"]
                if composition(self.hass, [source]).blocked:
                    raise ValueError("A source scene cannot control Halo entities")
                if (
                    not registry.async_get(source)
                    and not self.hass.states.get(source)
                    and source not in old_sources
                ):
                    raise ValueError("Select an existing Home Assistant scene")

    def scene_problem(self, scene: dict) -> str | None:
        """Resolve native scene availability and recursion without any commands."""
        return scene_problem(self.hass, scene)

    def scene_feedback_lights(self, room_id: str, scene: dict) -> set[str]:
        """Limit contextless feedback tolerance to the initiating room."""
        return feedback_lights(
            self.hass, self.config["rooms"][room_id]["lights"], scene["scene_entity_id"]
        )

    @contextmanager
    def external_scene_context(self, context: Context) -> Iterator[None]:
        """Propagate a recursion guard through awaited service calls and children."""
        token = _EXTERNAL_CALL.set(context.id)
        self._external_contexts.add(context.id)
        try:
            yield
        finally:
            self._external_contexts.discard(context.id)
            _EXTERNAL_CALL.reset(token)

    def _reject_external_scene_reentry(self, context: Context | None) -> None:
        """Reject nested Halo controls before they can wait on the room lock."""
        # Child tasks and timer callbacks inherit their creation context. The
        # inherited guard is meaningful only while that native call is active;
        # a delayed independent action must not retain a permanent prohibition.
        if _EXTERNAL_CALL.get() in self._external_contexts or (
            context
            and (
                context.id in self._external_contexts
                or context.parent_id in self._external_contexts
            )
        ):
            raise HaloError(
                "external_scene_recursive",
                "A source scene cannot control Halo entities",
            )

    async def async_authorize_scene(
        self, room_id: str, scene: dict, context: Context | None
    ) -> None:
        """Check the source and known targets before a manual pause or service call."""
        if scene.get("type", "halo") != "home_assistant":
            return
        if problem := self.scene_problem(scene):
            raise HaloError(problem, "Home Assistant scene cannot be activated")
        if context and context.user_id:
            user = await self.hass.auth.async_get_user(context.user_id)
            if user is None:
                raise Unauthorized(user_id=context.user_id)
            self.check_control(user, room_id)
            targets = composition(self.hass, [scene["scene_entity_id"]]).nodes
            if not all(
                user.permissions.check_entity(entity_id, POLICY_CONTROL)
                for entity_id in targets
            ):
                raise Unauthorized(user_id=user.id)

    @callback
    def inspect_scene(self, room_id: str, entity_id: str) -> dict:
        """Return source metadata without changing configuration or any device."""
        self._engine(room_id)
        return inspect_scene(
            self.hass, self.config["rooms"][room_id]["lights"], entity_id
        )

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

    async def _commit_config(
        self, config: dict, *, resume_room_id: str | None = None
    ) -> None:
        """Publish new settings only after the durable write has succeeded."""
        async with self._store_lock:
            data = deepcopy(
                {
                    "config": config,
                    "runtime": {
                        key: value
                        for key, value in self.runtime_state.items()
                        if key in config["rooms"]
                    },
                    "revision": self.revision + 1,
                }
            )
            if resume_room_id is not None:
                runtime = data["runtime"].setdefault(resume_room_id, {})
                for key in ("pause_until", "manual_scene_id", "nightlight_blocked"):
                    runtime.pop(key, None)
            await self._store.async_save(data)
            self.config = config
            self.revision += 1
            if resume_room_id is not None:
                # Detector callbacks can record an absence while storage waits,
                # even with the room lock held. Publish only the pause reset;
                # never replace newer event data with the stored snapshot.
                runtime = self.runtime_state[resume_room_id]
                for key in ("pause_until", "manual_scene_id", "nightlight_blocked"):
                    runtime.pop(key, None)
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
            globals_changed = any(
                normalized[key] != self.config[key]
                for key in normalized
                if key != "rooms"
            )
            reconfigure = {
                room_id
                for room_id, room in normalized["rooms"].items()
                if room_id in self.engines
                and (
                    globals_changed
                    or not _only_manual_scenes_added(
                        self.config["rooms"][room_id], room
                    )
                )
            }
            removed = {
                room_id: engine
                for room_id, engine in self.engines.items()
                if room_id not in normalized["rooms"]
            }
            try:
                for engine in removed.values():
                    await engine.async_stop()
                await self._commit_config(normalized)
            except BaseException:
                for engine in removed.values():
                    try:
                        await engine.async_start()
                    except Exception:
                        # A full disk can also reject the restart's runtime
                        # flush. async_start has nevertheless restored listeners.
                        _LOGGER.exception("Could not persist restarted Halo room")
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
                    registry.async_remove_device(device.id)
            added = set(normalized["rooms"]) - self.engines.keys()
            for room_id in added:
                self.engines[room_id] = HaloRoomEngine(self.hass, self, room_id)
            for room_id in normalized["rooms"]:
                if room_id in added:
                    await self.engines[room_id].async_start()
                elif room_id in reconfigure:
                    await self.engines[room_id].async_reconfigure()
                else:
                    self.engines[room_id].async_refresh_listeners()
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
        self._reject_external_scene_reentry(context)
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
        self._reject_external_scene_reentry(context)
        await self._authorize_context(room_id, context)
        self._check_idle(room_id)
        if mode not in ("automation", "natural") or not isinstance(enabled, bool):
            raise HaloError("invalid_config", "Invalid room mode")
        engine = self._engine(room_id)
        release = (
            engine.async_suspend_pending_automation()
            if mode == "automation" and enabled is False
            else None
        )
        try:
            async with self._config_lock:
                self._check_idle(room_id)
                updated = deepcopy(self.config)
                updated["rooms"][room_id][f"{mode}_enabled"] = enabled

                async def commit() -> None:
                    await self._commit_config(updated)

                await self._engine(room_id).async_set_mode(
                    mode, enabled, context=context, commit=commit
                )
                await self.async_persist_runtime()
                self.async_notify()
        finally:
            if release:
                release()

    async def async_resume(self, room_id: str, context: Context | None = None) -> None:
        self._reject_external_scene_reentry(context)
        await self._authorize_context(room_id, context)
        async with self._config_lock:
            self._check_idle(room_id)
            updated = deepcopy(self.config)
            updated["rooms"][room_id]["automation_enabled"] = True

            async def commit() -> None:
                await self._commit_config(updated, resume_room_id=room_id)

            await self._engine(room_id).async_resume(context=context, commit=commit)
            await self.async_persist_runtime()
            self.async_notify()

    async def async_activate_scene(
        self, room_id: str, scene_id: str, context: Context | None = None
    ) -> None:
        self._reject_external_scene_reentry(context)
        await self._authorize_context(room_id, context)
        self._check_idle(room_id)
        await self._engine(room_id).async_activate_scene(scene_id, context=context)

    async def async_begin_edit(self, room_id: str, owner: str) -> str:
        async with self._config_lock:
            self._check_idle(room_id)
            token = await self._engine(room_id).async_begin_edit(owner)
            self._edits[room_id] = (token, owner)
            return token

    @callback
    def import_scene(self, room_id: str, config: dict) -> dict:
        """Return an independent import draft, without writes or lamp commands."""
        self._engine(room_id)
        try:
            result = normalize_scene_import(
                config, self.config["rooms"][room_id]["lights"]
            )
        except ValueError as err:
            raise HaloError("invalid_config", str(err)) from err
        if not result["scene"]["lights"]:
            raise HaloError(
                "no_matching_lights", "The scene contains no selected room lights"
            )
        return result

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
        capture: bool = False,
        capture_entities: list[str] | None = None,
        target: str = "scene",
        nightlight: dict | None = None,
    ) -> None:
        async with self._config_lock:
            engine = self._check_edit(room_id, token, owner)
            members = self.config["rooms"][room_id]["lights"]
            if target not in ("scene", "nightlight"):
                raise HaloError("invalid_config", "Unknown editor target")
            if capture_entities is not None:
                if not save or not capture:
                    raise HaloError(
                        "invalid_config", "capture_entities requires save and capture"
                    )
                if (
                    not isinstance(capture_entities, list)
                    or any(not isinstance(item, str) for item in capture_entities)
                    or len(set(capture_entities)) != len(capture_entities)
                    or not set(capture_entities).issubset(members)
                ):
                    raise HaloError(
                        "invalid_config",
                        "capture_entities must contain unique selected room lights",
                    )
            if save:
                self._check_revision(revision)

                async def commit() -> None:
                    try:
                        if target == "nightlight":
                            if scene is not None:
                                raise ValueError(
                                    "A nightlight editor cannot save a scene"
                                )
                            if not isinstance(nightlight, dict):
                                raise ValueError(
                                    "A nightlight editor requires its settings"
                                )
                            # Validate after capture: a new draft may have no
                            # settings yet, but its selected live lights do.
                            normalized = validate_nightlight(
                                nightlight | {"enabled": False}, members
                            )
                        else:
                            if nightlight is not None:
                                raise ValueError(
                                    "A scene editor cannot save a nightlight"
                                )
                            normalized = validate_scene(scene, members)
                        if target == "scene" and normalized["type"] != "halo":
                            raise ValueError("Linked scenes do not use the live editor")
                        if capture:
                            normalized["lights"] = validate_lamp_states(
                                engine.capture_lights(
                                    normalized["lights"], entities=capture_entities
                                ),
                                members,
                            )
                        updated = deepcopy(self.config)
                        if target == "nightlight":
                            normalized["enabled"] = nightlight.get("enabled", False)
                            updated["rooms"][room_id]["nightlight"] = normalized
                        else:
                            scenes = updated["rooms"][room_id]["scenes"]
                            for index, existing in enumerate(scenes):
                                if existing["id"] == normalized["id"]:
                                    scenes[index] = normalized
                                    break
                            else:
                                scenes.append(normalized)
                        updated = validate_config(updated)
                        self._validate_references(updated)
                    except ValueError as err:
                        raise HaloError("invalid_config", str(err)) from err
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

        def visible_members(members: Any) -> list[str]:
            """Filter references in groups, scenes and other entities alike."""
            if not isinstance(members, _GROUP_MEMBER_TYPES):
                return []
            visible = [
                member
                for member in members
                if isinstance(member, str)
                and user.permissions.check_entity(member, POLICY_READ)
            ]
            if isinstance(members, (set, frozenset)):
                visible.sort()
            return list(dict.fromkeys(visible))

        groups: dict[str, list[str]] = {}
        member_of: dict[str, list[str]] = {}
        for state in visible_states:
            if state.domain not in ("light", "group"):
                continue
            registered = registry.async_get(state.entity_id)
            members = state.attributes.get("entity_id")
            # Hue v1 only exposes the flag. Hue v2 additionally returns member
            # IDs as a set and keeps its entity type in the registry when offline.
            is_hue_group = state.domain == "light" and (
                state.attributes.get("is_hue_group") is True
                or (
                    registered
                    and registered.platform == "hue"
                    and registered.translation_key == "hue_grouped_light"
                )
            )
            if not (
                (registered and registered.platform == "group")
                or is_hue_group
                or isinstance(members, _GROUP_MEMBER_TYPES)
            ):
                continue
            # Membership is metadata too: never disclose an unreadable entity
            # through another group's attributes or reverse membership list.
            groups[state.entity_id] = visible_members(members)
            for member in groups[state.entity_id]:
                member_of.setdefault(member, []).append(state.entity_id)
        lights, entities = [], []
        for state in visible_states:
            entity_id = state.entity_id
            attributes = dict(state.attributes)
            if isinstance(attributes.get("entity_id"), _GROUP_MEMBER_TYPES):
                attributes["entity_id"] = visible_members(attributes["entity_id"])
            item = {
                "entity_id": entity_id,
                "name": state.name,
                "state": state.state,
                "attributes": attributes,
                "platform": registered.platform
                if (registered := registry.async_get(entity_id))
                else None,
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
                    "group_members_complete": (
                        (members_info := composition(self.hass, [entity_id])).complete
                        and all(
                            user.permissions.check_entity(member, POLICY_READ)
                            for member in members_info.nodes
                        )
                    ),
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
