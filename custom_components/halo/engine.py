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
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .conditions import UNAVAILABLE, condition_entities, evaluate_condition, number
from .lighting import fallback_permission, solar_elevation
from .models import DEFAULT_PRESENCE_RETURN_WINDOW, ROOM_DEFAULTS
from .natural import (
    capture_lamp_state,
    lamp_parameters,
    natural_values,
    supports_brightness,
)
from .nightlight import nightlight_conflicts

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
_SCENE_TRANSITION_LIMIT = 6553


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
        self._interrupted_generation: int | None = None
        self._stopped = True
        self._presence: bool | None = None
        self._dark: bool | None = None
        self._dark_memory: bool | None = None
        self._lighting_allowed: bool | None = None
        self._lighting_source = "always"
        self._fallback_observed: bool | None = None
        self._pending_lighting_open: int | None = None
        self._lux: float | None = None
        self._absence_deadline: float | None = None
        self._lux_off_deadline: float | None = None
        self._lighting_off_deadline: float | None = None
        self._scene_id: str | None = None
        self._applied_scene: str | None = None
        self._reason = "idle"
        self._last_error: str | None = None
        self._lamp_errors: dict[str, str] = {}
        self._own_contexts: dict[str, float] = {}
        self._expected: dict[str, dict[str, Any]] = {}
        self._scene_feedback: dict[str, float] = {}
        self._failed_scenes: set[str] = set()
        self._scene_errors: dict[str, str] = {}
        self._automation_suspensions: set[object] = set()
        self._last_commands: dict[str, dict[str, Any]] = {}
        self._edit: dict[str, Any] | None = None
        # Ephemeral: a restart must never recreate a recent return of presence.
        self._absence_off_started_at: float | None = None
        self._absence_off_handled = False
        self._pending_presence_return: int | None = None
        self._presence_returned_at: float | None = None
        # Keep the absence ambience separate from normal lighting, including
        # while waiting for sufficient darkness after presence returns.
        self._nightlight_mode = False

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

    @property
    def lighting_status(self) -> dict[str, str | None] | None:
        """Describe the current ambience, distinct from a pending decision.

        Real lamp availability and power take precedence. A condition matching
        a scene alone is not enough to report that scene as the active ambience.
        This is the engine's operating mode, not a measurement of lamp colors.
        """
        if not self.available:
            return None
        if not self.is_on:
            return {"mode": "off", "scene_id": None}
        manual = {"mode": "manual", "scene_id": None}
        if self._edit:
            return manual
        if self._nightlight_mode and self.room.get("automation_enabled"):
            return {"mode": "nightlight", "scene_id": None}
        paused = self._runtime.get("pause_until", 0) > dt_util.utcnow().timestamp()
        scene_id = (
            self._runtime.get("manual_scene_id")
            if paused
            else self._applied_scene
            if self.room.get("automation_enabled") and self._reason == "scene"
            else None
        )
        if scene_id and any(
            scene["id"] == scene_id for scene in self.room.get("scenes", [])
        ):
            return {"mode": "scene", "scene_id": scene_id}
        if paused or not self.room.get("automation_enabled"):
            return manual
        if self._natural_targets(only_on=True):
            return {"mode": "natural", "scene_id": None}
        return manual

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
            "lighting_allowed": self._lighting_allowed,
            "lighting_source": self._lighting_source,
            "lux": self._lux,
            "absence_deadline": self._iso(self._absence_deadline),
            "lux_off_deadline": self._iso(self._lux_off_deadline),
            "lighting_off_deadline": self._iso(self._lighting_off_deadline),
            "is_on": self.is_on,
            "available": self.available,
            "error": self._last_error
            or next(iter(self._lamp_errors.values()), None)
            or next(iter(self._scene_errors.values()), None),
            "scene_errors": dict(self._scene_errors),
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
            if scene.get("type") == "home_assistant":
                entities.add(scene["scene_entity_id"])
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
        if (
            not self.room.get("lux_entity_id")
            and self.room.get("lighting_fallback", {}).get("mode") == "time"
        ):
            # The rule has minute precision. HA handles local time and DST;
            # only a permission change queues a reevaluation at the boundary.
            self._unsubscribers.append(
                async_track_time_change(self.hass, self._async_lighting_tick, second=0)
            )

    @callback
    def async_refresh_listeners(self) -> None:
        """Refresh dependencies for configuration-only changes without commands."""
        if self._stopped:
            return
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
        self._subscribe()

    @callback
    def async_suspend_pending_automation(self) -> Callable[[], None]:
        """Invalidate automation while a disable request waits for configuration.

        The room configuration stays inside the manager's transaction. A token
        also blocks queued input reevaluations until that transaction completes;
        generation invalidation alone would only stop the current service call.
        """
        token = object()
        self._automation_suspensions.add(token)
        self._generation += 1
        self._scene_feedback.clear()
        self._cancel_presence_return()

        @callback
        def release() -> None:
            if token not in self._automation_suspensions:
                return
            self._automation_suspensions.discard(token)
            if (
                not self._automation_suspensions
                and not self._stopped
                and self.room.get("automation_enabled", False)
            ):
                # An interrupted request must not leave an enabled room inert.
                self.hass.async_create_task(self._async_wakeup("mode"))

        return release

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
        self._scene_feedback.clear()
        self._cancel_presence_return()
        self._presence_returned_at = None
        self._pending_lighting_open = None
        self._lighting_off_deadline = None
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
        self._scene_feedback.clear()
        self._failed_scenes.clear()
        self._scene_errors.clear()
        self._cancel_presence_return()
        self._presence_returned_at = None
        self._pending_lighting_open = None
        self._lighting_off_deadline = None
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
        self._subscribe()
        self._last_commands.clear()
        self._lamp_errors = {
            entity_id: error
            for entity_id, error in self._lamp_errors.items()
            if entity_id in self.room["lights"]
        }
        await self._async_wakeup("reconfigure")

    async def _async_tick(self, _now: datetime) -> None:
        self._observe_fallback()
        await self._async_wakeup("tick")

    async def _async_lighting_tick(self, _now: datetime) -> None:
        if self._observe_fallback():
            await self._async_wakeup("lighting")

    def _observe_fallback(self) -> bool:
        """Invalidate obsolete automatic sequences before waiting for the lock."""
        if self._stopped or self.room.get("lux_entity_id"):
            return False
        allowed = fallback_permission(
            self.hass,
            self.room.get("lighting_fallback", {}),
            self.manager.config.get("sun_entity_id"),
        )
        if allowed is self._fallback_observed:
            return False
        self._fallback_observed = allowed
        autonomous = any(
            scene["id"] == self._scene_id and scene.get("can_turn_on", False)
            for scene in self.room.get("scenes", [])
        )
        paused = self._runtime.get("pause_until", 0) > dt_util.utcnow().timestamp()
        if (
            not self._edit
            and not autonomous
            and not self._automation_suspensions
            and self.room.get("automation_enabled", False)
            and (not paused or self._nightlight_mode)
        ):
            self._generation += 1
            self._pending_lighting_open = self._generation if allowed is True else None
        if allowed is not True:
            self._cancel_presence_return()
        return True

    @callback
    def _async_state_event(self, event: Event) -> None:
        """Reject own feedback before queuing a serialized reevaluation."""
        entity_id = event.data["entity_id"]
        old, new = event.data["old_state"], event.data["new_state"]
        if entity_id in {
            self.room.get("presence_entity_id"),
            self.manager.config.get("sun_entity_id"),
        }:
            self._observe_fallback()
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
                self._last_commands.pop(entity_id, None)
            elif old.state != new.state or any(
                old.attributes.get(key) != new.attributes.get(key)
                for key in _LIGHT_ATTRIBUTES
            ):
                trigger = "manual"
            else:
                return
        elif entity_id == self.room.get("presence_entity_id"):
            trigger = "presence"
            before, after = self._presence_value(old), self._presence_value(new)
            if after is not True:
                self._presence_returned_at = None
            elif before is False and new is not None:
                self._presence_returned_at = new.last_changed.timestamp()
            if after is None:
                # An unavailable detector cannot prove continuous absence,
                # even if its recovery is queued behind a slow light service.
                self._runtime.pop("absent_since", None)
            if before != after:
                if self.room.get("nightlight", {}).get("enabled"):
                    # An absence sequence may still be fading or waiting on a
                    # service. Stop its remaining commands before taking the lock.
                    self._generation += 1
                if after is False:
                    # Track every new absence at the event boundary, including
                    # repeated dropouts while a light command holds the lock.
                    self._runtime["absent_since"] = new.last_changed.timestamp()
                    self._cancel_presence_return()
                    self._absence_off_handled = False
                elif before is False and after is True and self._can_return():
                    # Cancel the rest of an off sequence before waiting for its
                    # service call/lock. Other queued evaluations can consume
                    # this same one-shot intent, always using turn_on.
                    self._generation += 1
                    self._pending_presence_return = self._generation
                    self._absence_off_started_at = None
                else:
                    self._cancel_presence_return()
        elif entity_id == self.room.get("lux_entity_id"):
            trigger = "lux"
        elif linked := [
            scene
            for scene in self.room.get("scenes", [])
            if scene.get("type") == "home_assistant"
            and scene.get("scene_entity_id") == entity_id
        ]:
            # A scene's state is its last activation time (or unknown before the
            # first call), not an on/off condition. Never replay on timestamps.
            before = old is not None and old.state != "unavailable"
            after = new is not None and new.state != "unavailable"
            if before == after:
                if not any(
                    entity_id in condition_entities(scene.get("conditions"))
                    for scene in self.room.get("scenes", [])
                ):
                    return
                trigger = "condition"
            else:
                for scene in linked:
                    self._failed_scenes.discard(scene["id"])
                    self._scene_errors.pop(scene["id"], None)
                trigger = "scene_availability"
        else:
            trigger = "condition"
        if trigger == "manual" and not self._edit:
            self._generation += 1
            self._scene_feedback.clear()
            self._cancel_presence_return()
        self.hass.async_create_task(self._async_wakeup(trigger))

    def _presence_value(self, state: State | None) -> bool | None:
        if state is None or state.state in UNAVAILABLE:
            return None
        return state.state in self.room.get("presence_states", ["on"])

    def _cancel_presence_return(self) -> None:
        """Discard eligibility without reopening it in the same absence cycle."""
        self._absence_off_started_at = None
        self._pending_presence_return = None
        self._absence_off_handled = True

    def _can_return(self) -> bool:
        """A real return can bypass stale lux only after our recent absence-off."""
        duration = self.manager.config.get(
            "presence_return_window", DEFAULT_PRESENCE_RETURN_WINDOW
        )
        return bool(
            not self._stopped
            and not self._edit
            and not self._automation_suspensions
            and self.room.get("automation_enabled", False)
            and not self._lux_off_enabled()
            and (
                self.room.get("lux_entity_id")
                or fallback_permission(
                    self.hass,
                    self.room.get("lighting_fallback", {}),
                    self.manager.config.get("sun_entity_id"),
                )
                is True
            )
            and self._absence_off_started_at is not None
            and 0
            <= dt_util.utcnow().timestamp() - self._absence_off_started_at
            < duration
        )

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
        # Provider feedback may discard the context (notably Hue). The bounded
        # grace period belongs only to this room; known foreign contexts win.
        if not new.context.parent_id and self._scene_feedback.get(entity_id, 0) > now:
            return True
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
                self._pause(block_nightlight=not self.is_on)
                self._last_commands.clear()
            await self._evaluate(trigger)

    def _pause(self, *, block_nightlight: bool = False) -> None:
        self._scene_feedback.clear()
        self._cancel_presence_return()
        self._nightlight_mode = False
        if block_nightlight:
            self._runtime["nightlight_blocked"] = True
        else:
            self._runtime.pop("nightlight_blocked", None)
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
        # Older runtimes stored a boolean based only on the off delay. Recheck
        # the actual duration instead, including the shared presence protection.
        self._runtime.pop("absence_confirmed", None)
        if self._presence is False:
            since = self._runtime.setdefault("absent_since", now)
            self._absence_deadline = since + self.room.get(
                "absence_delay", ROOM_DEFAULTS["absence_delay"]
            )
        else:
            self._absence_deadline = None
            since = self._runtime.pop("absent_since", None)
            if self._presence and since is not None and state is not None:
                confirmation_delay = max(
                    self.room.get("absence_delay", ROOM_DEFAULTS["absence_delay"]),
                    self.manager.config.get(
                        "presence_return_window", DEFAULT_PRESENCE_RETURN_WINDOW
                    ),
                )
                # Use the return event's time: waiting for an in-flight service
                # must not turn a brief sensor dropout into a confirmed absence.
                returned_at = (
                    self._presence_returned_at
                    if self._presence_returned_at is not None
                    else state.last_changed.timestamp()
                )
                if returned_at >= since + confirmation_delay:
                    self._runtime.pop("pause_until", None)
        lux_id = self.room.get("lux_entity_id")
        lux_state = self._available_state(lux_id)
        self._lux = number(lux_state.state) if lux_state else None
        threshold = number(self.room.get("lux_threshold"))
        if not lux_id:
            self._dark = None
        elif self._lux is None or threshold is None:
            self._dark = None
        else:
            if self._lux < threshold:
                self._dark_memory = True
            elif self._lux >= threshold + self.room.get("lux_hysteresis", 0):
                self._dark_memory = False
            self._dark = self._dark_memory
        self._lighting_source = (
            "lux"
            if lux_id
            else self.room.get("lighting_fallback", {}).get("mode", "always")
        )
        self._lighting_allowed = (
            self._dark
            if lux_id
            else fallback_permission(
                self.hass,
                self.room.get("lighting_fallback", {}),
                self.manager.config.get("sun_entity_id"),
            )
        )
        self._fallback_observed = self._lighting_allowed if not lux_id else None
        nightlight_lux = self.room.get("nightlight", {}).get("enabled") and (
            self._nightlight_mode or self._presence is False
        )
        if (self.room.get("lux_off", False) or nightlight_lux) and self._dark is False:
            if self._lux_off_deadline is None:
                self._lux_off_deadline = now + self.room.get("lux_off_delay", 30)
        else:
            self._lux_off_deadline = None
        if (
            not lux_id
            and (self._normal_off_enabled() or nightlight_lux)
            and self._lighting_allowed is False
        ):
            if self._lighting_off_deadline is None:
                self._lighting_off_deadline = now + (
                    self.room.get("lux_off_delay", 30)
                    if self._lighting_source == "sun"
                    else 0
                )
        else:
            self._lighting_off_deadline = None
        if self._runtime.get("pause_until", 0) <= now:
            self._runtime.pop("pause_until", None)
            self._runtime.pop("manual_scene_id", None)
            self._runtime.pop("nightlight_blocked", None)

    def _normal_off_enabled(self) -> bool:
        if self.room.get("lux_entity_id"):
            return self._lux_off_enabled()
        return self.room.get("lighting_fallback", {}).get("turn_off", False)

    def _lux_off_enabled(self) -> bool:
        """A retained sensor setting has no effect after the sensor is removed."""
        return bool(self.room.get("lux_entity_id") and self.room.get("lux_off", False))

    def _lighting_off_due(self, now: float) -> bool:
        deadline = (
            self._lux_off_deadline
            if self.room.get("lux_entity_id")
            else self._lighting_off_deadline
        )
        return deadline is not None and now >= deadline

    def _lighting_block_reason(self) -> str:
        return {
            "time": "outside_schedule",
            "sun": "sun_above_threshold",
        }.get(self._lighting_source, "bright")

    def _selected_scene(self) -> dict[str, Any] | None:
        selected = None
        for scene in self.room.get("scenes", []):
            scene_id = scene["id"]
            if not evaluate_condition(
                self.hass,
                scene.get("conditions"),
                self.manager.config.get("sun_entity_id"),
            ):
                self._failed_scenes.discard(scene_id)
                self._scene_errors.pop(scene_id, None)
                continue
            if scene.get("type") == "home_assistant":
                if problem := self.manager.scene_problem(scene):
                    self._scene_errors[scene_id] = problem
                    continue
                if scene_id in self._failed_scenes:
                    continue
                self._scene_errors.pop(scene_id, None)
            if selected is None:
                selected = scene
        return selected

    async def _evaluate(self, trigger: str) -> None:
        if self._stopped:
            return
        now = dt_util.utcnow().timestamp()
        previous_pause = bool(self._runtime.get("pause_until"))
        previous_allowed = self._lighting_allowed
        self._inputs(now)
        if (
            self._lighting_source != "lux"
            and self._lighting_allowed is True
            and (
                previous_allowed is not True
                or self._pending_lighting_open == self._generation
            )
            and trigger
            not in {
                "start",
                "reconfigure",
                "resume",
                "mode",
                "presence",
                "manual",
                "explicit",
                "edit",
            }
        ):
            trigger = "lighting"
        if previous_pause and not self._runtime.get("pause_until"):
            trigger = "resume"
        if self._edit and self._edit["until"] <= now:
            await self._restore_edit()
            self._edit = None
            trigger = "resume"
        if trigger in {"start", "reconfigure", "resume", "mode"}:
            self._failed_scenes.clear()
            self._scene_errors.clear()
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
        # Providers may fail independently; iterate instead of nesting calls
        # so even a long priority list is bounded by its number of candidates.
        while await self._decide_once(now, scene, trigger):
            scene = self._selected_scene()
            self._scene_id = scene["id"] if scene else None

    async def _decide_once(
        self, now: float, scene: dict[str, Any] | None, trigger: str
    ) -> bool | None:
        generation = self._generation
        presence_return = (
            self._pending_presence_return is not None
            and self._pending_presence_return == self._generation
            and self._presence is True
            and not self._lux_off_enabled()
            and (self._lighting_source == "lux" or self._lighting_allowed is True)
        )
        self._pending_presence_return = None
        lighting_open = trigger == "lighting" and self._lighting_allowed is True
        self._pending_lighting_open = None
        if self._edit:
            self._reason = "editing"
            return
        if self._automation_suspensions or not self.room.get(
            "automation_enabled", False
        ):
            self._reason = "disabled"
            return
        absence_due = (
            self._absence_deadline is not None and now >= self._absence_deadline
        )
        lux_due = self._lighting_off_due(now)
        paused = bool(self._runtime.get("pause_until"))
        if paused:
            self._reason = "manual_pause"
            if self.room.get("allow_off_during_pause", True) and not self._runtime.get(
                "nightlight_blocked"
            ):
                if await self._decide_nightlight(
                    now, trigger, absence_due, paused=True
                ):
                    return
            if self.room.get("allow_off_during_pause", True) and (
                absence_due or (lux_due and self._normal_off_enabled())
            ):
                await self._all_off(absence=absence_due)
            return
        if not self.available and not (scene and scene.get("type") == "home_assistant"):
            self._reason = "unavailable"
            return
        autonomous_scene = scene is not None and scene.get("can_turn_on", False)
        if not autonomous_scene and await self._decide_nightlight(
            now, trigger, absence_due
        ):
            return
        leaving_nightlight = self._nightlight_mode
        if not autonomous_scene and (
            absence_due or (lux_due and self._normal_off_enabled())
        ):
            self._reason = "absence" if absence_due else self._lighting_block_reason()
            await self._all_off(absence=absence_due)
            self._applied_scene = None
            self._nightlight_mode = False
            return
        changed_scene = self._scene_id != self._applied_scene
        force = (
            presence_return
            or (lighting_open and not autonomous_scene)
            or leaving_nightlight
            or trigger
            in {
                "start",
                "reconfigure",
                "resume",
                "mode",
                "availability",
            }
        )
        can_start = presence_return or (
            self._presence is True
            and self._lighting_allowed is True
            and trigger
            in {
                "start",
                "presence",
                "lux",
                "lighting",
                "resume",
                "reconfigure",
                "mode",
                "availability",
            }
        )
        was_on = self.is_on
        if scene and (autonomous_scene or was_on or can_start):
            self._reason = "scene"
            if changed_scene or force:
                transition = (
                    "lux_on"
                    if (lighting_open and not autonomous_scene)
                    or (leaving_nightlight and trigger in {"lux", "lighting"})
                    else "turn_on"
                    if presence_return or leaving_nightlight
                    else "scene"
                )
                if (
                    not presence_return
                    and not was_on
                    and can_start
                    and trigger in {"presence", "lux", "lighting"}
                ):
                    transition = (
                        "lux_on" if trigger in {"lux", "lighting"} else "turn_on"
                    )
                try:
                    applied = await self._apply_scene(scene, transition)
                except HomeAssistantError as error:
                    self._failed_scenes.add(scene["id"])
                    self._scene_errors[scene["id"]] = "external_scene_failed"
                    _LOGGER.warning(
                        "Halo could not activate %s: %s", scene["id"], error
                    )
                    if generation != self._generation or self._stopped:
                        return None
                    if presence_return:
                        self._pending_presence_return = self._generation
                    return True
                if not applied:
                    return
            self._applied_scene = scene["id"]
            self._nightlight_mode = False
            return
        self._applied_scene = None
        self._scene_feedback.clear()
        if not scene and (was_on or can_start):
            self._reason = "base"
            if changed_scene or force or (not was_on and can_start):
                transition = (
                    "turn_on"
                    if presence_return
                    or (leaving_nightlight and trigger not in {"lux", "lighting"})
                    else "lux_on"
                    if leaving_nightlight or lighting_open
                    else "scene"
                    if changed_scene
                    else "lux_on"
                    if trigger in {"lux", "lighting"}
                    else "turn_on"
                )
                targets = self._ambience()
                if (
                    was_on
                    and not changed_scene
                    and trigger != "resume"
                    and not presence_return
                    and not lighting_open
                    and not leaving_nightlight
                ):
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
                if generation != self._generation or self._stopped:
                    return
            else:
                await self._apply(self._natural_targets(only_on=True), "natural")
            self._nightlight_mode = False
            if self.room.get("natural_enabled", True) and self.room.get("associations"):
                self._reason = "natural" if self._solar() is not None else "unavailable"
            if self._lighting_allowed is None or (
                self.room.get("presence_entity_id") and self._presence is None
            ):
                self._reason = "unavailable"
            return
        if self._presence is False:
            self._reason = "absence"
        elif self._lighting_allowed is False:
            self._reason = self._lighting_block_reason()
        elif (
            self.room.get("presence_entity_id") and self._presence is None
        ) or self._lighting_allowed is None:
            self._reason = "unavailable"

    async def _decide_nightlight(
        self, now: float, trigger: str, absence_due: bool, *, paused: bool = False
    ) -> bool:
        """Handle absence lighting without mistaking it for the normal ambience."""
        nightlight = self.room.get("nightlight", {})
        if not nightlight.get("enabled") or not self.room.get("presence_entity_id"):
            return False
        if self._presence is None or self._lighting_allowed is None:
            # Neither an unavailable detector nor a missing lux reading can
            # justify turning the configured nightlights on or off.
            if absence_due or self._nightlight_mode:
                self._reason = "unavailable"
                return True
            return False
        if self._presence is True and self._lighting_allowed is True and not paused:
            # The caller must restore every normal target, even if a nightlight
            # is still physically on or its preceding fade has not completed.
            return False
        if not absence_due and not self._nightlight_mode:
            return False
        if self._presence is False and not absence_due:
            return self._nightlight_mode
        self._cancel_presence_return()
        self._applied_scene = None
        self._runtime.pop("manual_scene_id", None)
        if nightlight_conflicts(self.hass, self.room):
            self._last_error = "nightlight_group_conflict"
            self._reason = "unavailable"
            return True
        if self._last_error == "nightlight_group_conflict":
            self._last_error = None
        lux_due = self._lighting_off_due(now)
        if self._lighting_allowed is False:
            if self._nightlight_mode and not lux_due:
                self._reason = "nightlight"
                return True
            self._nightlight_mode = True
            self._reason = self._lighting_block_reason()
            await self._all_off()
            return True
        if paused and self._presence is True:
            self._reason = "nightlight"
            return True
        self._nightlight_mode = True
        self._reason = "nightlight"
        targets = {
            entity_id: dict(
                nightlight.get("lights", {}).get(entity_id, {"state": "off"})
            )
            for entity_id in self.room["lights"]
        }
        await self._apply(
            targets, "lux_on" if trigger in {"lux", "lighting"} else "turn_off"
        )
        return True

    def _solar(self) -> tuple[float, bool] | None:
        sun = self._available_state(self.manager.config.get("sun_entity_id"))
        elevation = solar_elevation(sun)
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

    async def _all_off(
        self, context: Context | None = None, *, absence: bool = False
    ) -> None:
        self._scene_feedback.clear()
        await self._apply(
            {entity_id: {"state": "off"} for entity_id in self.room["lights"]},
            "turn_off",
            context=context,
            absence=absence,
        )

    async def _apply_scene(
        self,
        scene: dict[str, Any],
        category: str,
        *,
        context: Context | None = None,
    ) -> bool:
        """Apply a local snapshot or recall the complete native scene once."""
        generation = self._generation
        self._scene_feedback.clear()
        if scene.get("type") != "home_assistant":
            await self._apply(
                scene.get("lights", {}), category, force=True, context=context
            )
            return generation == self._generation and not self._stopped
        if problem := self.manager.scene_problem(scene):
            raise HomeAssistantError(problem)
        transition = self._transition(category)
        data: dict[str, Any] = {"entity_id": scene["scene_entity_id"]}
        if transition is not None:
            data["transition"] = min(transition, _SCENE_TRANSITION_LIMIT)
        own_context = Context(
            parent_id=context.id if context else None,
            user_id=context.user_id if context else None,
        )
        now = dt_util.utcnow().timestamp()
        until = now + (data.get("transition") or 0) + 5
        self._own_contexts[own_context.id] = max(until, now + 60)
        self._scene_feedback = {
            entity_id: until
            for entity_id in self.manager.scene_feedback_lights(self.room_id, scene)
        }
        for entity_id in self._scene_feedback:
            self._expected.pop(entity_id, None)
            self._last_commands.pop(entity_id, None)
        try:
            with self.manager.external_scene_context(own_context):
                await self.hass.services.async_call(
                    "scene", "turn_on", data, blocking=True, context=own_context
                )
        except HomeAssistantError:
            self._scene_feedback.clear()
            raise
        except asyncio.CancelledError:
            self._scene_feedback.clear()
            raise
        except Exception as error:
            # Providers are outside Halo's implementation. Normalize their
            # failures so arbitration and the explicit API behave consistently.
            self._scene_feedback.clear()
            raise HomeAssistantError(str(error)) from error
        self._last_error = None
        for entity_id in self._scene_feedback:
            self._lamp_errors.pop(entity_id, None)
        self._scene_errors.pop(scene["id"], None)
        self._failed_scenes.discard(scene["id"])
        return generation == self._generation and not self._stopped

    async def _apply(
        self,
        targets: dict[str, dict[str, Any]],
        category: str | None,
        *,
        force: bool = False,
        context: Context | None = None,
        absence: bool = False,
    ) -> None:
        generation = self._generation
        transition = self._transition(category) if category else None
        for entity_id, desired in targets.items():
            if self._stopped or generation != self._generation:
                if not self._stopped and context is None:
                    self._interrupted_generation = self._generation
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
                self._lamp_errors.pop(entity_id, None)
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
            if (
                absence
                and not turn_on
                and state.state == "on"
                and not self._absence_off_handled
                and not self._lux_off_enabled()
                and self.manager.config.get(
                    "presence_return_window", DEFAULT_PRESENCE_RETURN_WINDOW
                )
                > 0
            ):
                # Arm at dispatch, including while a slow service is in flight.
                # Only the first actual command of this absence opens a window.
                self._absence_off_started_at = dt_util.utcnow().timestamp()
                self._absence_off_handled = True
            try:
                await self.hass.services.async_call(
                    "light",
                    "turn_on" if turn_on else "turn_off",
                    data,
                    blocking=True,
                    context=own_context,
                )
            except HomeAssistantError as error:
                self._lamp_errors[entity_id] = str(error)
                self._last_commands.pop(entity_id, None)
                _LOGGER.warning("Halo could not command %s: %s", entity_id, error)
            else:
                self._last_commands[entity_id] = target
                self._lamp_errors.pop(entity_id, None)
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
            self._lighting_off_deadline,
            self._runtime.get("pause_until"),
            self._edit["until"] if self._edit else None,
        ]
        future = [value for value in deadlines if value is not None and value > now]
        if future:
            self._timer = async_call_later(
                self.hass,
                max(0, min(future) - dt_util.utcnow().timestamp()),
                self._async_tick,
            )

    async def async_turn_on(self, context: Context | None = None) -> None:
        self._generation += 1
        self._scene_feedback.clear()
        self._cancel_presence_return()
        async with self._lock:
            self._require_no_editor()
            scene = self._selected_scene()
            if scene and scene.get("type") == "home_assistant":
                await self.manager.async_authorize_scene(self.room_id, scene, context)
            self._pause()
            try:
                if scene:
                    if await self._apply_scene(scene, "turn_on", context=context):
                        self._runtime["manual_scene_id"] = scene["id"]
                else:
                    await self._apply(
                        self._ambience(), "turn_on", force=True, context=context
                    )
            except HomeAssistantError as error:
                self._last_error = str(error)
                raise
            finally:
                await self._evaluate("explicit")

    async def async_turn_off(self, context: Context | None = None) -> None:
        self._generation += 1
        self._scene_feedback.clear()
        self._cancel_presence_return()
        async with self._lock:
            self._require_no_editor()
            self._pause(block_nightlight=True)
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
        self._scene_feedback.clear()
        self._cancel_presence_return()
        async with self._lock:
            self._require_no_editor()
            if scene.get("type") == "home_assistant":
                await self.manager.async_authorize_scene(self.room_id, scene, context)
            self._pause()
            try:
                if await self._apply_scene(scene, "scene", context=context):
                    self._runtime["manual_scene_id"] = scene_id
            except HomeAssistantError as error:
                self._last_error = str(error)
                raise
            finally:
                await self._evaluate("explicit")

    async def _commit_mode_change(
        self, commit: Callable[[], Awaitable[None]], generation: int
    ) -> None:
        """Recover only the automatic sequence interrupted by a rejected mode."""
        try:
            await commit()
        except Exception:
            if (
                not self._stopped
                and self._interrupted_generation == generation == self._generation
            ):
                self._interrupted_generation = None
                try:
                    # This reevaluates the saved policy without ending a pause.
                    # A newer manual intent changes the generation and wins.
                    await self._evaluate("resume")
                except Exception:
                    _LOGGER.exception("Could not recover Halo after failed mode save")
            raise

    async def async_set_mode(
        self,
        mode: str,
        enabled: bool,
        context: Context | None = None,
        *,
        commit: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        if mode not in ("automation", "natural"):
            raise ValueError("invalid_mode")
        self._generation += 1
        generation = self._generation
        self._scene_feedback.clear()
        self._cancel_presence_return()
        async with self._lock:
            self._require_no_editor()
            if commit is not None:
                await self._commit_mode_change(commit, generation)
            self.room[f"{mode}_enabled"] = enabled
            await self._evaluate("mode" if mode == "automation" else "natural_mode")

    async def async_resume(
        self,
        context: Context | None = None,
        *,
        commit: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._generation += 1
        generation = self._generation
        self._scene_feedback.clear()
        self._cancel_presence_return()
        async with self._lock:
            self._require_no_editor()
            if commit is not None:
                await self._commit_mode_change(commit, generation)
            self.room["automation_enabled"] = True
            self._runtime.pop("pause_until", None)
            await self._evaluate("resume")

    def _require_no_editor(self) -> None:
        if self._edit:
            raise ValueError("room_being_edited")

    async def async_begin_edit(self, owner: str) -> str:
        self._generation += 1
        self._scene_feedback.clear()
        self._cancel_presence_return()
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
