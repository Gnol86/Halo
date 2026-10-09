"""Small, deterministic evaluator for Halo's visual condition trees."""

from __future__ import annotations

from datetime import datetime, time
from math import isfinite
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

UNAVAILABLE = {STATE_UNAVAILABLE, STATE_UNKNOWN}


def condition_entities(condition: dict[str, Any] | None) -> set[str]:
    """Find state dependencies to subscribe to without polling all entities."""
    if not condition:
        return set()
    result = {condition["entity_id"]} if condition.get("entity_id") else set()
    for child in condition.get("conditions", []):
        result.update(condition_entities(child))
    result.update(condition_entities(condition.get("condition")))
    return result


def number(value: Any) -> float | None:
    """Unknown, unavailable and non-finite data never become zero."""
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except TypeError, ValueError:
        return None
    return result if isfinite(result) else None


def _between(value: float, condition: dict[str, Any]) -> bool:
    return (condition.get("above") is None or value > float(condition["above"])) and (
        condition.get("below") is None or value < float(condition["below"])
    )


def _evaluate(
    hass: HomeAssistant,
    condition: dict[str, Any] | None,
    sun_entity_id: str | None,
    now: datetime,
) -> bool | None:
    if not condition:
        return False
    kind = condition.get("type")
    if kind in ("and", "or"):
        children = condition.get("conditions", [])
        if not children:
            return False
        values = [_evaluate(hass, item, sun_entity_id, now) for item in children]
        if kind == "and":
            return False if False in values else None if None in values else True
        return True if True in values else None if None in values else False
    if kind == "not":
        value = _evaluate(hass, condition.get("condition"), sun_entity_id, now)
        return None if value is None else not value
    if kind == "time":
        current = now.time().replace(tzinfo=None)
        after = time.fromisoformat(condition.get("after") or "00:00")
        before = time.fromisoformat(condition.get("before") or "23:59:59.999999")
        if after > before:
            return current >= after or current < before
        return after <= current < before
    entity_id = sun_entity_id if kind == "sun" else condition.get("entity_id")
    state = hass.states.get(entity_id) if entity_id else None
    if state is None or state.state in UNAVAILABLE:
        return None
    if kind == "state":
        return state.state == condition.get("state")
    if kind not in ("numeric", "sun"):
        return False
    attribute = "elevation" if kind == "sun" else condition.get("attribute")
    value = number(state.attributes.get(attribute) if attribute else state.state)
    return None if value is None else _between(value, condition)


def evaluate_condition(
    hass: HomeAssistant,
    condition: dict[str, Any] | None,
    sun_entity_id: str | None = None,
    now: datetime | None = None,
) -> bool:
    """Evaluate a validated tree; missing inputs cannot activate a scene via NOT."""
    try:
        return _evaluate(hass, condition, sun_entity_id, now or dt_util.now()) is True
    except TypeError, ValueError, KeyError:
        return False
