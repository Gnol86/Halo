"""Authenticated WebSocket interface shared by the panel and the Python engine."""

from typing import Any

import probatio
from homeassistant.components import websocket_api
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, Unauthorized

from .const import DOMAIN
from .manager import HaloError, HaloManager

SIGNAL_UPDATED = "halo_updated"


def _manager(hass: HomeAssistant) -> HaloManager:
    if not (manager := hass.data.get(DOMAIN, {}).get("manager")):
        raise HaloError("not_loaded", "Halo is not loaded")
    return manager


async def _handle(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Dispatch already authenticated and schema-validated commands."""
    try:
        manager = _manager(hass)
        kind = msg["type"]
        owner = f"{connection.user.id}:{id(connection)}"
        context = Context(user_id=connection.user.id)
        if kind == "halo/get":
            connection.send_result(msg["id"], manager.snapshot(connection.user))
            return
        if kind == "halo/subscribe":
            pending = None

            @callback
            def publish() -> None:
                nonlocal pending
                pending = None
                try:
                    current = _manager(hass)
                except HaloError:
                    return
                connection.send_event(msg["id"], current.snapshot(connection.user))

            @callback
            def changed(event: Any) -> None:
                nonlocal pending
                if pending is None:
                    pending = hass.loop.call_later(0.1, publish)

            remove_listener = hass.bus.async_listen(SIGNAL_UPDATED, changed)

            @callback
            def unsubscribe() -> None:
                remove_listener()
                if pending is not None:
                    pending.cancel()

            connection.subscriptions[msg["id"]] = unsubscribe
            connection.send_result(msg["id"])
            publish()
            return
        if kind == "halo/save":
            await manager.async_save_config(msg["config"], msg["revision"])
        elif kind == "halo/scene/import":
            connection.send_result(
                msg["id"], manager.import_scene(msg["room_id"], msg["config"])
            )
            return
        elif kind == "halo/command":
            room_id, command = msg["room_id"], msg["command"]
            manager.check_control(connection.user, room_id)
            if command in ("turn_on", "turn_off"):
                await manager.async_room_command(room_id, command, context)
            elif command == "resume":
                await manager.async_resume(room_id, context)
            elif command in ("automation", "natural"):
                if "enabled" not in msg:
                    raise HaloError("invalid_config", "Mode commands require enabled")
                await manager.async_set_mode(room_id, command, msg["enabled"], context)
            elif command == "scene":
                if "scene_id" not in msg:
                    raise HaloError("invalid_config", "Scene commands require scene_id")
                await manager.async_activate_scene(room_id, msg["scene_id"], context)
        elif kind == "halo/edit/begin":
            token = await manager.async_begin_edit(msg["room_id"], owner)
            connection.send_result(msg["id"], {"token": token})
            return
        elif kind == "halo/edit/preview":
            await manager.async_preview(
                msg["room_id"], msg["token"], owner, msg["lights"]
            )
        elif kind == "halo/edit/touch":
            await manager.async_touch_edit(msg["room_id"], msg["token"], owner)
        elif kind == "halo/edit/end":
            await manager.async_end_edit(
                msg["room_id"],
                msg["token"],
                owner,
                msg["save"],
                msg.get("scene"),
                msg.get("revision"),
                capture=msg.get("capture", False),
                capture_entities=msg.get("capture_entities"),
            )
        connection.send_result(msg["id"], manager.snapshot(connection.user))
    except HaloError as err:
        connection.send_error(msg["id"], err.code, str(err))
    except ValueError as err:
        code = {
            "room_being_edited": "edit_locked",
            "edit_session_expired": "invalid_edit",
            "scene_not_found": "not_found",
        }.get(str(err), "invalid_config")
        connection.send_error(msg["id"], code, str(err))
    except Unauthorized:
        raise
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "command_failed", str(err))


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register commands once; resolve the active manager on every request."""
    room = {probatio.Required("room_id"): str}
    edit = room | {probatio.Required("token"): str}
    commands = {
        "halo/get": ({}, False),
        "halo/subscribe": ({}, False),
        "halo/save": (
            {
                probatio.Required("config"): dict,
                probatio.Required("revision"): int,
            },
            True,
        ),
        "halo/command": (
            room
            | {
                probatio.Required("command"): probatio.In(
                    ["turn_on", "turn_off", "resume", "automation", "natural", "scene"]
                ),
                probatio.Optional("enabled"): bool,
                probatio.Optional("scene_id"): str,
            },
            False,
        ),
        "halo/edit/begin": (room, True),
        "halo/scene/import": (room | {probatio.Required("config"): dict}, True),
        "halo/edit/preview": (edit | {probatio.Required("lights"): dict}, True),
        "halo/edit/touch": (edit, True),
        "halo/edit/end": (
            edit
            | {
                probatio.Required("save"): bool,
                probatio.Optional("scene"): dict,
                probatio.Optional("revision"): int,
                probatio.Optional("capture", default=False): bool,
                probatio.Optional("capture_entities"): [str],
            },
            True,
        ),
    }
    for name, (fields, admin) in commands.items():
        handler = websocket_api.async_response(_handle)
        if admin:
            handler = websocket_api.require_admin(handler)
        handler = websocket_api.websocket_command(
            {probatio.Required("type"): name} | fields
        )(handler)
        websocket_api.async_register_command(hass, handler)
