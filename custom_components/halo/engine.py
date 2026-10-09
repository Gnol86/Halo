"""Independent, event-driven room controller for Halo."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from copy import deepcopy
from datetime import datetime, timedelta
from secrets import token_urlsafe
from typing import Any

from homeassistant.components.light import LightEntityFeature
from homeassistant.core import Context, Event, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .conditions import UNAVAILABLE, condition_entities, evaluate_condition, number
from .models import ROOM_DEFAULTS
from .natural import (
    capture_lamp_state,
    lamp_parameters,
    natural_values,
    supports_brightness,
)

_LOGGER = logging.getLogger(__name__)
_LIGHT_ATTRIBUTES = (
    "brightness",
    "color_temp_kelvin",
    "rgb_color",
    "rgbw_color",
    "rgbww_color",
    "hs_color",
    "xy_color",
    "color_mode",
    "effect",
)
_EDIT_TTL = 120


class HaloRoomEngine:
    """Coordinate one room without a frontend or independent polling tasks."""

    def __init__(self, hass: HomeAssistant, manager: Any, room_id: str) -> None:
        self.hass = hass
        self.manager = manager
        self.room_id = room_id
        self._last_room = manager.config["rooms"][room_id]
        self._runtime = manager.runtime_state.setdefault(room_id, {})
        self._lock = asyncio.Lock()
        self._unsubscribers: list[Callable[[], None]] = []
        self._timer: Callable[[], None] | None = None
        self._generation = 0
        self._stopped = True
        self._presence: bool | None = None
        self._dark: bool | None = None
        self._dark_memory: bool | None = None
        self._lux: float | None = None
        self._absence_deadline: float | None = None
        self._lux_off_deadline: float | None = None
        self._scene_id: str | None = None
        self._applied_scene: str | None = None
        self._reason = "idle"
        self._last_error: str | None = None
        self._own_contexts: dict[str, float] = {}
        self._expected: dict[str, dict[str, Any]] = {}
        self._last_commands: dict[str, dict[str, Any]] = {}
        self._edit: dict[str, Any] | None = None

    @property
    def room(self) -> dict[str, Any]:
        """Read the current saved configuration after atomic manager updates."""
        self._last_room = self.manager.config["rooms"].get(
            self.room_id, self._last_room
        )
        return self._last_room

    @property
    def available(self) -> bool:
        return any(
            self._available_state(entity_id) for entity_id in self.room["lights"]
        )

    @property
    def is_on(self) -> bool:
        return any(
            (state := self._available_state(entity_id)) and state.state == "on"
            for entity_id in self.room["lights"]
        )

    @staticmethod
    def _iso(timestamp: float | None) -> str | None:
        return dt_util.utc_from_timestamp(timestamp).isoformat() if timestamp else None

    @property
    def status(self) -> dict[str, Any]:
        """Return serializable facts, including actual lamp availability/state."""
        return {
            "reason": self._reason,
            "scene_id": self._scene_id,
            "pause_until": self._iso(self._runtime.get("pause_until")),
            "editing": self._edit is not None,
            "presence": self._presence,
            "dark": self._dark,
            "lux": self._lux,
            "absence_deadline": self._iso(self._absence_deadline),
            "lux_off_deadline": self._iso(self._lux_off_deadline),
            "is_on": self.is_on,
            "available": self.available,
            "error": self._last_error,
        }

    def _available_state(self, entity_id: str | None) -> State | None:
        state = self.hass.states.get(entity_id) if entity_id else None
        return state if state and state.state not in UNAVAILABLE else None

    def _subscribe(self) -> None:
        entities = set(self.room["lights"])
        for field in ("presence_entity_id", "lux_entity_id"):
            if self.room.get(field):
                entities.add(self.room[field])
        if sun := self.manager.config.get("sun_entity_id"):
            entities.add(sun)
        for scene in self.room.get("scenes", []):
            entities.update(condition_entities(scene.get("conditions")))
        if entities:
            self._unsubscribers.append(
                async_track_state_change_event(
                    self.hass, entities, self._async_state_event
                )
            )
        self._unsubscribers.append(
            async_track_time_interval(
                self.hass, self._async_tick, timedelta(seconds=30)
            )
        )

    async def async_start(self) -> None:
        """Subscribe and restore deadlines without resetting a manual hold."""
        if not self._stopped:
            return
        self._stopped = False
        self._subscribe()
        await self._async_wakeup("start")

    async def async_stop(self) -> None:
        """Cancel every listener and deadline; no light commands during unload."""
        self._stopped = True
        self._generation += 1
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
        if self._timer:
            self._timer()
            self._timer = None
        self._edit = None
        await self.manager.async_persist_runtime()

    async def async_reconfigure(self) -> None:
        """Refresh dependencies after changes to a room or global profile."""
        if self._stopped:
            return
        self._generation += 1
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
        self._subscribe()
        self._last_commands.clear()
        await self._async_wakeup("reconfigure")

    async def _async_tick(self, _now: datetime) -> None:
        await self._async_wakeup("tick")

    @callback
    def _async_state_event(self, event: Event) -> None:
        """Reject own feedback before queuing a serialized reevaluation."""
        entity_id = event.data["entity_id"]
        old, new = event.data["old_state"], event.data["new_state"]
        if entity_id in self.room["lights"]:
            self.manager.async_notify()
            if self._own_change(entity_id, old, new):
                return
            if (
                not old
                or not new
                or old.state in UNAVAILABLE
                or new.state in UNAVAILABLE
            ):
                trigger = "availability"
            elif old.state != new.state or any(
                old.attributes.get(key) != new.attributes.get(key)
                for key in _LIGHT_ATTRIBUTES
            ):
                trigger = "manual"
            else:
                return
        elif entity_id == self.room.get("presence_entity_id"):
            trigger = "presence"
        elif entity_id == self.room.get("lux_entity_id"):
            trigger = "lux"
        else:
            trigger = "condition"
        if trigger == "manual" and not self._edit:
            self._generation += 1
        self.hass.async_create_task(self._async_wakeup(trigger))

    def _own_change(self, entity_id: str, old: State | None, new: State | None) -> bool:
        if not new:
            return False
        now = dt_util.utcnow().timestamp()
        self._own_contexts = {k: v for k, v in self._own_contexts.items() if v >= now}
        if (
            new.context.id in self._own_contexts
            or new.context.parent_id in self._own_contexts
        ):
            return True
        # A user context always wins over the fallback for devices dropping context.
        if new.context.user_id:
            return False
        expected = self._expected.get(entity_id)
        if not expected or expected["until"] < now or not old:
            return False
        target = expected["target"]
        fading_off = target["state"] == "off" and old.state == new.state == "on"
        if new.state != target["state"] and not fading_off:
            return False
        if fading_off:
            target = {**target, "brightness_pct": 0}
        if "white" in target:
            target = {**target, "brightness": target["white"]}
        color_fields = set(_LIGHT_ATTRIBUTES) - {"brightness", "color_mode", "effect"}
        primary_color = (
            "white"
            if "white" in target
            else next((key for key in color_fields if key in target), None)
        )
        changed = [
            key
            for key in _LIGHT_ATTRIBUTES
            if old.attributes.get(key) != new.attributes.get(key)
        ]
        for key in changed:
            if key == "color_mode":
                continue
            if (
                key in color_fields
                and "effect" in target
                and new.attributes.get("effect") == target["effect"]
                and new.attributes.get("color_mode") in ("onoff", "brightness")
            ):
                # An effect can replace native color control with on/off or
                # brightness only, clearing the formerly exposed colors.
                continue
            if primary_color and key in color_fields and key != primary_color:
                # HA exposes derived HS/XY/RGB values alongside native white or
                # color. Validate the commanded representation only.
                continue
            if key == "brightness" and "brightness_pct" in target:
                value = number(new.attributes.get(key))
                previous = number(old.attributes.get(key))
                goal = target["brightness_pct"] * 255 / 100
                if (
                    value is None
                    or previous is None
                    or not min(previous, goal) - 2 <= value <= max(previous, goal) + 2
                ):
                    return False
            elif key in target:
                value, goal = new.attributes.get(key), target[key]
                if isinstance(goal, str):
                    if value != goal:
                        return False
                elif isinstance(goal, (int, float)):
                    previous = number(old.attributes.get(key))
                    value = number(value)
                    if (
                        previous is None
                        or value is None
                        or not min(previous, goal) - 1
                        <= value
                        <= max(previous, goal) + 1
                    ):
                        return False
                else:
                    previous = old.attributes.get(key)
                    if not value or not previous or len(value) != len(goal):
                        return False
                    if any(
                        not min(start, end) - 1 <= current <= max(start, end) + 1
                        for start, end, current in zip(
                            previous, goal, value, strict=True
                        )
                    ):
                        return False
            elif old.state == new.state:
                return False
        return True

    async def _async_wakeup(self, trigger: str) -> None:
        if self._stopped:
            return
        async with self._lock:
            if self._stopped:
                return
            if trigger == "manual" and not self._edit:
                self._pause()
                self._last_commands.clear()
            await self._evaluate(trigger)

    def _pause(self) -> None:
        self._runtime.pop("manual_scene_id", None)
        self._runtime["pause_until"] = dt_util.utcnow().timestamp() + self.room.get(
            "manual_pause", ROOM_DEFAULTS["manual_pause"]
        )

    def _inputs(self, now: float) -> None:
        presence_id = self.room.get("presence_entity_id")
        state = self._available_state(presence_id)
        self._presence = (
            state.state in self.room.get("presence_states", ["on"]) if state else None
        )
        if self._presence is False:
            since = self._runtime.setdefault("absent_since", now)
            self._absence_deadline = since + self.room.get(
                "absence_delay", ROOM_DEFAULTS["absence_delay"]
            )
            if now >= self._absence_deadline:
                self._runtime["absence_confirmed"] = True
        else:
            self._absence_deadline = None
            self._runtime.pop("absent_since", None)
            if self._presence:
                if self._runtime.pop("absence_confirmed", False):
                    self._runtime.pop("pause_until", None)
        lux_id = self.room.get("lux_entity_id")
        lux_state = self._available_state(lux_id)
        self._lux = number(lux_state.state) if lux_state else None
        threshold = number(self.room.get("lux_threshold"))
        if not lux_id:
            self._dark = True
        elif self._lux is None or threshold is None:
            self._dark = None
        else:
            if self._lux < threshold:
                self._dark_memory = True
            elif self._lux >= threshold + self.room.get("lux_hysteresis", 0):
                self._dark_memory = False
            self._dark = self._dark_memory
        if self.room.get("lux_off", False) and self._dark is False:
            if self._lux_off_deadline is None:
                self._lux_off_deadline = now + self.room.get("lux_off_delay", 30)
        else:
            self._lux_off_deadline = None
        if self._runtime.get("pause_until", 0) <= now:
            self._runtime.pop("pause_until", None)
            self._runtime.pop("manual_scene_id", None)

    def _selected_scene(self) -> dict[str, Any] | None:
        return next(
            (
                scene
                for scene in self.room.get("scenes", [])
                if evaluate_condition(
                    self.hass,
                    scene.get("conditions"),
                    self.manager.config.get("sun_entity_id"),
                )
            ),
            None,
        )

    async def _evaluate(self, trigger: str) -> None:
        if self._stopped:
            return
        now = dt_util.utcnow().timestamp()
        previous_pause = bool(self._runtime.get("pause_until"))
        self._inputs(now)
        if previous_pause and not self._runtime.get("pause_until"):
            trigger = "resume"
        if self._edit and self._edit["until"] <= now:
            await self._restore_edit()
            self._edit = None
            trigger = "resume"
        scene = self._selected_scene()
        self._scene_id = scene["id"] if scene else None
        if self._runtime.get("pause_until") and self._runtime.get("manual_scene_id"):
            self._scene_id = self._runtime["manual_scene_id"]
        self._reason = "idle"
        try:
            await self._decide(now, scene, trigger)
        finally:
            self._schedule(now)
            await self.manager.async_persist_runtime()
            self.manager.async_notify()

    async def _decide(
        self, now: float, scene: dict[str, Any] | None, trigger: str
    ) -> None:
        if self._edit:
            self._reason = "editing"
            return
        if not self.room.get("automation_enabled", False):
            self._reason = "disabled"
            return
        absence_due = (
            self._absence_deadline is not None and now >= self._absence_deadline
        )
        lux_due = self._lux_off_deadline is not None and now >= self._lux_off_deadline
        paused = bool(self._runtime.get("pause_until"))
        if paused:
            self._reason = "manual_pause"
            if self.room.get("allow_off_during_pause", True) and (
                absence_due or lux_due
            ):
                await self._all_off()
            return
        if not self.available:
            self._reason = "unavailable"
            return
        autonomous_scene = scene is not None and scene.get("can_turn_on", False)
        if not autonomous_scene and (absence_due or lux_due):
            self._reason = "absence" if absence_due else "bright"
            await self._all_off()
            self._applied_scene = None
            return
        changed_scene = self._scene_id != self._applied_scene
        force = trigger in {"start", "reconfigure", "resume", "mode", "availability"}
        can_start = (
            self._presence is True
            and self._dark is True
            and trigger
            in {
                "start",
                "presence",
                "lux",
                "resume",
                "reconfigure",
                "mode",
                "availability",
            }
        )
        was_on = self.is_on
        if scene and (autonomous_scene or was_on or can_start):
            self._reason = "scene"
            if changed_scene or force or (not was_on and can_start):
                transition = "scene"
                if not was_on and can_start and trigger in {"presence", "lux"}:
                    transition = "lux_on" if trigger == "lux" else "turn_on"
                await self._apply(scene.get("lights", {}), transition, force=True)
            self._applied_scene = scene["id"]
            return
        self._applied_scene = None
        if not scene and (was_on or can_start):
            self._reason = "base"
            if changed_scene or force or (not was_on and can_start):
                transition = (
                    "scene"
                    if changed_scene
                    else "lux_on"
                    if trigger == "lux"
                    else "turn_on"
                )
                targets = self._ambience()
                if was_on and not changed_scene and trigger != "resume":
                    # Editing a shared profile or recovering a sensor is an
                    # adjustment, not a request to relight every room member.
                    targets = {
                        entity_id: desired
                        for entity_id, desired in targets.items()
                        if (state := self._available_state(entity_id))
                        and state.state == "on"
                    }
                    transition = "natural"
                await self._apply(targets, transition, force=True)
            else:
                await self._apply(self._natural_targets(only_on=True), "natural")
            if self.room.get("natural_enabled", True) and self.room.get("associations"):
                self._reason = "natural" if self._solar() is not None else "unavailable"
            if self._dark is None or (
                self.room.get("presence_entity_id") and self._presence is None
            ):
                self._reason = "unavailable"
            return
        if self._presence is False:
            self._reason = "absence"
        elif self._dark is False:
            self._reason = "bright"
        elif (
            self.room.get("presence_entity_id") and self._presence is None
        ) or self._dark is None:
            self._reason = "unavailable"

    def _solar(self) -> tuple[float, bool] | None:
        sun = self._available_state(self.manager.config.get("sun_entity_id"))
        elevation = number(sun.attributes.get("elevation")) if sun else None
        if elevation is None:
            return None
        return elevation, bool(sun.attributes.get("rising", True))

    def _natural_targets(self, only_on: bool = False) -> dict[str, dict[str, Any]]:
        if not self.room.get("natural_enabled", True) or not (solar := self._solar()):
            return {}
        result = {}
        for association in self.room.get("associations", []):
            profile = self.manager.config.get("profiles", {}).get(
                association["profile_id"]
            )
            if profile is None:
                continue
            values = natural_values(
                profile, *solar, association.get("brightness_offset", 0)
            )
            for entity_id in association["lights"]:
                state = self._available_state(entity_id)
                if (
                    state
                    and supports_brightness(state)
                    and (not only_on or state.state == "on")
                ):
                    result[entity_id] = {"state": "on", **values}
        return result

    def _ambience(self) -> dict[str, dict[str, Any]]:
        targets = {
            entity_id: dict(self.room.get("base", {}).get(entity_id, {"state": "on"}))
            for entity_id in self.room["lights"]
        }
        for entity_id, values in self._natural_targets().items():
            if targets[entity_id].get("state", "on") == "on":
                # A natural white value takes precedence over stored scene colors.
                targets[entity_id] = {
                    key: value
                    for key, value in targets[entity_id].items()
                    if key
                    not in (
                        "rgb_color",
                        "hs_color",
                        "xy_color",
                        "rgbw_color",
                        "rgbww_color",
                        "color_mode",
                        "brightness",
                        "white",
                        "effect",
                    )
                }
                targets[entity_id].update(values)
        return targets

    def _transition(self, category: str) -> float | None:
        value = self.room.get("transitions", {}).get(category, "inherit")
        return (
            self.manager.config.get("transitions", {}).get(category)
            if value == "inherit"
            else value
        )

    async def _all_off(self, context: Context | None = None) -> None:
        await self._apply(
            {entity_id: {"state": "off"} for entity_id in self.room["lights"]},
            "turn_off",
            context=context,
        )

    async def _apply(
        self,
        targets: dict[str, dict[str, Any]],
        category: str | None,
        *,
        force: bool = False,
        context: Context | None = None,
    ) -> None:
        generation = self._generation
        transition = self._transition(category) if category else None
        for entity_id, desired in targets.items():
            if self._stopped or generation != self._generation:
                return
            state = self._available_state(entity_id)
            if not state or entity_id not in self.room["lights"]:
                continue
            turn_on = desired.get("state", "on") == "on"
            params = lamp_parameters(state, desired) if turn_on else {}
            target = {"state": "on" if turn_on else "off", **params}
            if not force and self._last_commands.get(entity_id) == target:
                continue
            if not force and not turn_on and state.state == "off":
                continue
            data = {"entity_id": entity_id, **params}
            supported = state.attributes.get("supported_features", 0)
            if transition is not None and supported & LightEntityFeature.TRANSITION:
                data["transition"] = transition
            own_context = Context(
                parent_id=context.id if context else None,
                user_id=context.user_id if context else None,
            )
            until = dt_util.utcnow().timestamp() + (data.get("transition") or 0) + 5
            self._own_contexts[own_context.id] = max(
                until, dt_util.utcnow().timestamp() + 60
            )
            self._expected[entity_id] = {"target": target, "until": until}
            try:
                await self.hass.services.async_call(
                    "light",
                    "turn_on" if turn_on else "turn_off",
                    data,
                    blocking=True,
                    context=own_context,
                )
            except HomeAssistantError as error:
                self._last_error = str(error)
                self._last_commands.pop(entity_id, None)
                _LOGGER.warning("Halo could not command %s: %s", entity_id, error)
            else:
                self._last_commands[entity_id] = target
                self._last_error = None

    def _schedule(self, now: float) -> None:
        if self._timer:
            self._timer()
            self._timer = None
        if self._stopped:
            return
        deadlines = [
            self._absence_deadline,
            self._lux_off_deadline,
            self._runtime.get("pause_until"),
            self._edit["until"] if self._edit else None,
        ]
        future = [value for value in deadlines if value is not None and value > now]
        if future:
            self._timer = async_call_later(
                self.hass, max(0, min(future) - now), self._async_tick
            )

    async def async_turn_on(self, context: Context | None = None) -> None:
        self._generation += 1
        async with self._lock:
            self._require_no_editor()
            scene = self._selected_scene()
            self._pause()
            if scene:
                self._runtime["manual_scene_id"] = scene["id"]
            await self._apply(
                scene.get("lights", {}) if scene else self._ambience(),
                "turn_on",
                force=True,
                context=context,
            )
            await self._evaluate("explicit")

    async def async_turn_off(self, context: Context | None = None) -> None:
        self._generation += 1
        async with self._lock:
            self._require_no_editor()
            self._pause()
            await self._all_off(context)
            await self._evaluate("explicit")

    async def async_activate_scene(
        self, scene_id: str, context: Context | None = None
    ) -> None:
        scene = next(
            (item for item in self.room.get("scenes", []) if item["id"] == scene_id),
            None,
        )
        if scene is None:
            raise ValueError("scene_not_found")
        self._generation += 1
        async with self._lock:
            self._require_no_editor()
            self._pause()
            self._runtime["manual_scene_id"] = scene_id
            await self._apply(scene["lights"], "scene", force=True, context=context)
            await self._evaluate("explicit")

    async def async_set_mode(
        self, mode: str, enabled: bool, context: Context | None = None
    ) -> None:
        if mode not in ("automation", "natural"):
            raise ValueError("invalid_mode")
        self._generation += 1
        async with self._lock:
            self.room[f"{mode}_enabled"] = enabled
            await self._evaluate("mode" if mode == "automation" else "natural_mode")

    async def async_resume(self, context: Context | None = None) -> None:
        self._generation += 1
        async with self._lock:
            self._require_no_editor()
            self.room["automation_enabled"] = True
            self._runtime.pop("pause_until", None)
            await self._evaluate("resume")

    def _require_no_editor(self) -> None:
        if self._edit:
            raise ValueError("room_being_edited")

    async def async_begin_edit(self, owner: str) -> str:
        self._generation += 1
        async with self._lock:
            if self._edit and self._edit["until"] <= dt_util.utcnow().timestamp():
                await self._restore_edit()
                self._edit = None
            self._require_no_editor()
            snapshot = self.capture_lights()
            token = token_urlsafe(32)
            self._edit = {
                "token": token,
                "owner": owner,
                "snapshot": snapshot,
                "until": dt_util.utcnow().timestamp() + _EDIT_TTL,
            }
            await self._evaluate("edit")
            return token

    def capture_lights(
        self, fallback: dict | None = None, *, entities: list[str] | None = None
    ) -> dict[str, dict[str, Any]]:
        """Capture real room lights while retaining known unavailable targets only.

        The manager invokes this synchronously inside the editor's commit lock.
        No availability failure is converted into an invented off state.
        """
        previous = self._edit["snapshot"] if self._edit else {}
        previous = previous | (fallback or {})
        result = {}
        for entity_id in self.room["lights"]:
            if entities is not None and entity_id not in entities:
                continue
            if state := self._available_state(entity_id):
                if state.state in ("on", "off"):
                    result[entity_id] = capture_lamp_state(state)
            elif entity_id in previous:
                result[entity_id] = deepcopy(previous[entity_id])
        return result

    def _check_editor(self, token: str) -> None:
        if (
            not self._edit
            or self._edit["token"] != token
            or self._edit["until"] <= dt_util.utcnow().timestamp()
        ):
            raise ValueError("edit_session_expired")

    async def async_touch_edit(self, token: str) -> None:
        async with self._lock:
            self._check_editor(token)
            self._edit["until"] = dt_util.utcnow().timestamp() + _EDIT_TTL
            self._schedule(dt_util.utcnow().timestamp())

    async def async_preview(
        self, token: str, lights: dict[str, dict[str, Any]]
    ) -> None:
        self._generation += 1
        async with self._lock:
            self._check_editor(token)
            if set(lights) - set(self.room["lights"]):
                raise ValueError("light_not_in_room")
            self._edit["until"] = dt_util.utcnow().timestamp() + _EDIT_TTL
            await self._apply(lights, None, force=True)
            self._schedule(dt_util.utcnow().timestamp())
            self.manager.async_notify()

    async def _restore_edit(self) -> None:
        if self._edit:
            await self._apply(self._edit["snapshot"], None, force=True)
            self._last_commands.clear()

    async def async_commit_edit(
        self, token: str, commit: Callable[[], Awaitable[None]]
    ) -> None:
        """Persist a scene and release its editor as one serialized operation."""
        self._generation += 1
        async with self._lock:
            self._check_editor(token)
            try:
                await commit()
            except Exception:
                # Keep the preview recoverable after a storage failure. An expiry
                # task that was queued during commit now observes the renewed lease.
                self._edit["until"] = dt_util.utcnow().timestamp() + _EDIT_TTL
                self._schedule(dt_util.utcnow().timestamp())
                self.manager.async_notify()
                raise
            for unsubscribe in self._unsubscribers:
                unsubscribe()
            self._unsubscribers.clear()
            self._subscribe()
            self._edit = None
            await self._evaluate("resume")

    async def async_end_edit(self, token: str, save: bool) -> None:
        self._generation += 1
        async with self._lock:
            self._check_editor(token)
            if not save:
                await self._restore_edit()
            self._edit = None
            if save:
                await self._evaluate("resume")
            else:
                # Preserve the restored snapshot at cancel; subsequent input events
                # resume the normal policy without immediately erasing the restore.
                self._reason = (
                    "manual_pause"
                    if self._runtime.get("pause_until")
                    else "idle"
                    if self.room.get("automation_enabled")
                    else "disabled"
                )
                self._schedule(dt_util.utcnow().timestamp())
                self.manager.async_notify()
