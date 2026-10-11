"""Expose Halo as the cause of its light and native-scene commands."""

from collections.abc import Callable
from typing import Any

from homeassistant.components.logbook import LazyEventPartialState
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, EVENT_LIGHT_COMMAND


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[
        [str, str, Callable[[LazyEventPartialState], dict[str, Any]]], None
    ],
) -> None:
    """Register the public logbook platform without requiring Activity setup."""

    @callback
    def describe(event: LazyEventPartialState) -> dict[str, Any]:
        # The origin is Halo, not the target lamp. Standard activity entries
        # carry the lamp entity; this description supplies the integration's
        # name/reason to the native cause node without impersonating a light.
        return {
            "name": event.data["name"],
            "message": event.data["message"],
            "context_id": event.context_id,
        }

    async_describe_event(DOMAIN, EVENT_LIGHT_COMMAND, describe)
