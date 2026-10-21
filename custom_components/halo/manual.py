"""Recognize explicit command intent without inferring it from lamp feedback.

The event bus exposes a validated service *request*, not its successful result.
An authenticated request is labelled user/API; it is not proof of a human gesture.
Lamp state contexts are deliberately never used to start or renew a suspension:
some providers keep reusing those contexts for delayed hardware reports.
"""

from collections import OrderedDict, deque
from collections.abc import Callable, Mapping
from time import monotonic
from typing import Any

from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.const import EVENT_CALL_SERVICE, EVENT_STATE_CHANGED
from homeassistant.core import CALLBACK_TYPE, Context, Event, HomeAssistant, callback
from homeassistant.helpers import group as group_helper
from homeassistant.helpers import target as target_helper
from homeassistant.util import dt as dt_util

_CONTEXT_TTL = 600.0
_CONTEXT_LIMIT = 256
_DIAGNOSTIC_LIMIT = 64
_UNAVAILABLE = {"unknown", "unavailable"}
_SERVICES = {
    "light": {"turn_on", "turn_off", "toggle"},
    "homeassistant": {"turn_on", "turn_off", "toggle"},
    "scene": {"turn_on"},
    "input_button": {"press"},
}
_TARGET_FIELDS = ("entity_id", "device_id", "area_id", "floor_id", "label_id")


class CommandOrigins:
    """Keep a bounded, short-lived registry shared by all Halo room engines."""

    def __init__(self) -> None:
        self._contexts: OrderedDict[str, float] = OrderedDict()

    def _prune(self, now: float) -> None:
        for context_id, expires in list(self._contexts.items()):
            if expires <= now:
                self._contexts.pop(context_id, None)
        while len(self._contexts) > _CONTEXT_LIMIT:
            self._contexts.popitem(last=False)

    @callback
    def add(self, context: Context, *, now: float | None = None) -> None:
        """Register Halo's own context before dispatching its service call."""
        instant = monotonic() if now is None else now
        self._contexts.pop(context.id, None)
        self._contexts[context.id] = instant + _CONTEXT_TTL
        self._prune(instant)

    @callback
    def contains(self, context: Context, *, now: float | None = None) -> bool:
        """Recognize exact own lineage before considering a user attribution."""
        self._prune(monotonic() if now is None else now)
        return context.id in self._contexts or context.parent_id in self._contexts

    @callback
    def clear(self) -> None:
        """Release recorded origins when the integration is unloaded."""
        self._contexts.clear()


class IdentifiedCommandListener:
    """Observe explicit intents for one room; the engine decides their effect.

    One context is one intervention per room for ten minutes, including scene
    fan-out and wrapper services. Reusing a context for a genuinely new request
    during that window intentionally does not renew a pause. Normal HA service
    requests create new contexts. The cache is bounded and not persisted.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        room_getter: Callable[[], Mapping[str, Any]],
        origins: CommandOrigins,
        on_command: Callable[[dict[str, Any]], None],
    ) -> None:
        self.hass = hass
        self._room = room_getter
        self._origins = origins
        self._on_command = on_command
        self._unsubscribers: list[CALLBACK_TYPE] = []
        self._seen: OrderedDict[str, float] = OrderedDict()
        self._diagnostics: deque[dict[str, Any]] = deque(maxlen=_DIAGNOSTIC_LIMIT)
        self._generation = 0
        self._last_command_at = 0.0

    @property
    def diagnostics(self) -> list[dict[str, Any]]:
        """Return a detached, bounded explanation of recent classifications."""
        return [dict(item) for item in self._diagnostics]

    @callback
    def start(self) -> None:
        """Subscribe once; all settings are reread for each incoming event."""
        if self._unsubscribers:
            return
        self._generation += 1
        self._unsubscribers = [
            self.hass.bus.async_listen(EVENT_CALL_SERVICE, self._service_event),
            self.hass.bus.async_listen(EVENT_STATE_CHANGED, self._state_event),
        ]

    @callback
    def stop(self) -> None:
        """Remove listeners without retaining the room or pending decisions."""
        self._generation += 1
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
        self._seen.clear()

    @callback
    def invalidate_pending(self) -> None:
        """Discard classifications awaiting auth after a newer engine intent."""
        self._generation += 1

    def _note(self, event: Event, result: str, reason: str, entity_id: str) -> None:
        self._diagnostics.append(
            {
                "result": result,
                "reason": reason,
                "entity_id": entity_id,
                "at": event.time_fired.timestamp(),
            }
        )

    def _eligible_context(self, event: Event, entity_id: str) -> bool:
        if self._origins.contains(event.context):
            self._note(event, "rejected", "halo_context", entity_id)
        elif event.context.parent_id:
            self._note(event, "rejected", "external_automation", entity_id)
        elif not event.context.user_id:
            self._note(event, "unknown", "unattributed_service", entity_id)
        else:
            return True
        return False

    def _emit(
        self,
        event: Event,
        entity_id: str,
        command: str,
        source: str,
        *,
        dedup_key: str | None = None,
    ) -> None:
        if event.time_fired.timestamp() < self._last_command_at:
            self._note(event, "rejected", "older_command", entity_id)
            return
        now = monotonic()
        for context_id, expires in list(self._seen.items()):
            if expires <= now:
                self._seen.pop(context_id, None)
        key = dedup_key or event.context.id
        if key in self._seen or event.context.id in self._seen:
            self._note(event, "rejected", "duplicate_context", entity_id)
            return
        self._seen[key] = now + _CONTEXT_TTL
        while len(self._seen) > _CONTEXT_LIMIT:
            self._seen.popitem(last=False)
        self._last_command_at = event.time_fired.timestamp()
        self._note(event, "accepted", source, entity_id)
        self._on_command(
            {
                "source": source,
                "entity_id": entity_id,
                "command": command,
                "context_id": event.context.id,
                "at": event.time_fired.timestamp(),
            }
        )

    def _members(self, entity_ids: set[str]) -> set[str]:
        """Expand known group/scene membership, retaining aggregate identities.

        Native HA scenes expose entity_id; opaque vendor scenes do not. Never
        guess their effects from their area or from a configured Halo scene.
        """
        result: set[str] = set()
        pending = list(entity_ids)
        registered_groups = group_helper.get_group_entities(self.hass)
        while pending and len(result) < 1024:
            entity_id = pending.pop()
            if entity_id in result or not isinstance(entity_id, str):
                continue
            result.add(entity_id)
            if entity_id in registered_groups:
                pending.extend(registered_groups[entity_id].group.member_entity_ids)
            if entity_id.split(".", 1)[0] not in {"light", "group", "scene"}:
                continue
            state = self.hass.states.get(entity_id)
            members = state.attributes.get("entity_id") if state else None
            if isinstance(members, (list, tuple, set, frozenset)):
                pending.extend(member for member in members if isinstance(member, str))
        return result

    def _service_groups(self, entity_ids: set[str]) -> set[str]:
        """Follow HA service group semantics, with cycle and size protection."""
        registered = group_helper.get_group_entities(self.hass)
        result: set[str] = set()
        seen: set[str] = set()
        pending = list(entity_ids)
        while pending and len(seen) < 1024:
            entity_id = pending.pop()
            if not isinstance(entity_id, str) or entity_id in seen:
                continue
            seen.add(entity_id)
            entity = registered.get(entity_id)
            if entity is not None and isinstance(
                entity.group, group_helper.GenericGroup
            ):
                pending.extend(entity.group.member_entity_ids)
            elif entity_id.startswith("group."):
                pending.extend(group_helper.get_entity_ids(self.hass, entity_id))
            else:
                result.add(entity_id)
        return result

    def _targets(self, data: Mapping[str, Any], domain: str) -> tuple[set[str], bool]:
        selection = {}
        for key in _TARGET_FIELDS:
            value = data.get(key)
            if isinstance(value, str):
                value = [item.strip() for item in value.split(",") if item.strip()]
            if isinstance(value, (list, tuple)) and all(
                isinstance(item, str) for item in value
            ):
                selection[key] = list(value)
        requested = set(selection.get("entity_id", []))
        # The target helper intentionally drops 'all' during group expansion.
        # Keep only services whose domain can actually reach the selected lamps.
        if "all" in requested:
            # HA's wrapper requires concrete targets and does not implement all.
            if domain == "homeassistant":
                return set(), False
            requested = {
                state.entity_id
                for state in self.hass.states.async_all()
                if state.domain == domain
            }
            selection["entity_id"] = list(requested)
        selected = target_helper.async_extract_referenced_entity_ids(
            self.hass, target_helper.TargetSelection(selection), expand_group=False
        )
        entities = selected.referenced | selected.indirectly_referenced
        return self._service_groups(entities), data.get("entity_id") == "all"

    async def _service_event(self, event: Event) -> None:
        generation = self._generation
        room = self._room()
        if room.get("manual_control", {}).get("mode") != "identified":
            return
        domain, service = event.data.get("domain"), event.data.get("service")
        if service not in _SERVICES.get(domain, set()):
            return
        data = event.data.get("service_data")
        if not isinstance(data, Mapping):
            return
        targets, all_requested = self._targets(data, domain)
        allowed = {"light", "scene"} if domain == "homeassistant" else {domain}
        if service != "turn_on":
            allowed.discard("scene")
        affected = self._members(
            {
                entity_id
                for entity_id in targets
                if entity_id.split(".", 1)[0] in allowed
            }
        )
        source = "input" if domain == "input_button" else "user"
        candidates = (
            room.get("manual_control", {}).get("inputs", [])
            if source == "input"
            else room.get("lights", [])
        )
        matched = next(
            (
                entity_id
                for entity_id in candidates
                if self._members({entity_id}) & affected
            ),
            None,
        )
        if matched is None or not self._eligible_context(event, matched):
            return
        user = await self.hass.auth.async_get_user(event.context.user_id)
        if user is None or not user.is_active:
            self._note(event, "rejected", "unknown_or_inactive_user", matched)
            return
        # Entity services check permissions after call_service is fired. Mirror
        # those checks before allowing this separate effect. Suspending a room
        # also requires control of all its configured lamps.
        room = self._room()
        if (
            not self._unsubscribers
            or generation != self._generation
            or room.get("manual_control", {}).get("mode") != "identified"
            or matched
            not in (
                room.get("manual_control", {}).get("inputs", [])
                if source == "input"
                else room.get("lights", [])
            )
            or self._origins.contains(event.context)
        ):
            return
        if all_requested:
            targets = {
                entity_id
                for entity_id in targets
                if user.permissions.check_entity(entity_id, POLICY_CONTROL)
            }
            affected = self._members(targets)
            if not self._members({matched}) & affected:
                self._note(event, "rejected", "control_denied", matched)
                return
        required = targets | set(room.get("lights", []))
        if not all(
            user.permissions.check_entity(entity_id, POLICY_CONTROL)
            for entity_id in required
        ):
            self._note(event, "rejected", "control_denied", matched)
            return
        self._emit(event, matched, f"{domain}.{service}", source)

    async def _state_event(self, event: Event) -> None:
        generation = self._generation
        room = self._room()
        settings = room.get("manual_control", {})
        if settings.get("mode") != "identified":
            return
        entity_id = event.data.get("entity_id")
        if entity_id not in settings.get("inputs", []):
            return
        if entity_id.split(".", 1)[0] not in {"event", "input_button"}:
            return
        old, new = event.data.get("old_state"), event.data.get("new_state")
        if not old or not new or old.state in _UNAVAILABLE or new.state in _UNAVAILABLE:
            self._note(event, "rejected", "input_initial_or_recovery", entity_id)
            return
        previous = dt_util.parse_datetime(old.state)
        current = dt_util.parse_datetime(new.state)
        if (
            previous is None
            or current is None
            or previous.tzinfo is None
            or current.tzinfo is None
            or current <= previous
            or not -5 <= (event.time_fired - current).total_seconds() <= 30
        ):
            self._note(event, "rejected", "input_without_fresh_event", entity_id)
            return
        if self._origins.contains(event.context):
            self._note(event, "rejected", "halo_context", entity_id)
            return
        if event.context.parent_id:
            self._note(event, "rejected", "external_automation", entity_id)
            return
        if event.context.user_id:
            user = await self.hass.auth.async_get_user(event.context.user_id)
            if user is None or not user.is_active:
                self._note(event, "rejected", "unknown_or_inactive_user", entity_id)
                return
            room = self._room()
            if not all(
                user.permissions.check_entity(target, POLICY_CONTROL)
                for target in [entity_id, *room.get("lights", [])]
            ):
                self._note(event, "rejected", "control_denied", entity_id)
                return
        room = self._room()
        if (
            not self._unsubscribers
            or generation != self._generation
            or self._origins.contains(event.context)
            or room.get("manual_control", {}).get("mode") != "identified"
            or entity_id not in room.get("manual_control", {}).get("inputs", [])
        ):
            return
        self._emit(
            event,
            entity_id,
            "input",
            "input",
            dedup_key=f"input:{entity_id}:{new.state}",
        )
