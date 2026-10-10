"""Exercise Halo's real manager through authenticated WebSocket connections."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from homeassistant.auth.const import GROUP_ID_USER
from homeassistant.components.light import LightEntityFeature
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, MockUser

from custom_components.halo.const import DOMAIN


async def request(client, message_type: str, **fields):
    """Send a request on a connection with no event subscription."""
    await client.send_json_auto_id({"type": message_type, **fields})
    return await client.receive_json()


@pytest.fixture
async def api(hass: HomeAssistant, hass_ws_client):
    """Run the actual integration, using stateful lamp services as the hardware."""
    area = ar.async_get(hass).async_create("Living Room")
    other_area = ar.async_get(hass).async_create("Office")
    lamp = er.async_get(hass).async_get_or_create(
        "light", "test", "lamp", suggested_object_id="living_room_lamp"
    )
    er.async_get(hass).async_update_entity(lamp.entity_id, area_id=area.id)
    hass.states.async_set(
        lamp.entity_id,
        "on",
        {
            "friendly_name": "Physical lamp",
            "brightness": 128,
            "supported_color_modes": ["brightness"],
            "color_mode": "brightness",
        },
    )
    hass.states.async_set("light.unavailable_lamp", "unavailable")
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, title="Halo", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    calls = []

    async def control(call: ServiceCall) -> None:
        calls.append(call)
        targets = call.data["entity_id"]
        if isinstance(targets, str):
            targets = [targets]
        for target in targets:
            current = hass.states.get(target)
            attributes = dict(current.attributes)
            attributes.update(
                {key: value for key, value in call.data.items() if key != "entity_id"}
            )
            if "brightness_pct" in attributes:
                attributes["brightness"] = round(
                    attributes.pop("brightness_pct") * 255 / 100
                )
            hass.states.async_set(
                target,
                "on" if call.service == "turn_on" else "off",
                attributes,
                context=call.context,
            )

    hass.services.async_register("light", "turn_on", control)
    hass.services.async_register("light", "turn_off", control)
    client = await hass_ws_client(hass)
    config = {"rooms": {area.id: {"lights": [lamp.entity_id]}}}
    yield SimpleNamespace(
        client=client,
        entry=entry,
        room_id=area.id,
        other_room_id=other_area.id,
        lamp=lamp.entity_id,
        config=config,
        calls=calls,
    )
    await client.close()
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def configure(api):
    result = await request(api.client, "halo/save", config=api.config, revision=0)
    assert result["success"], result
    return result["result"]


async def test_snapshot_discovers_areas_and_lights_excluding_own_entities(
    hass: HomeAssistant, api
) -> None:
    """The real snapshot includes room metadata, lamp capabilities and availability."""
    initial = await request(api.client, "halo/get")
    assert initial["success"]
    assert initial["result"]["is_admin"]
    assert initial["result"]["config"]["rooms"] == {}
    await configure(api)
    await hass.async_block_till_done()
    response = await request(api.client, "halo/get")
    snapshot = response["result"]
    assert {area["id"] for area in snapshot["areas"]} == {
        api.room_id,
        api.other_room_id,
    }
    lights = {light["entity_id"]: light for light in snapshot["lights"]}
    assert set(lights) == {api.lamp, "light.unavailable_lamp"}
    assert lights[api.lamp]["area_id"] == api.room_id
    assert lights[api.lamp]["supported_color_modes"] == ["brightness"]
    assert not lights["light.unavailable_lamp"]["available"]
    halo_light = er.async_get(hass).async_get_entity_id(
        "light", DOMAIN, f"{api.room_id}_light"
    )
    assert halo_light is not None
    assert halo_light not in lights
    assert snapshot["status"][api.room_id]["is_on"]
    assert not snapshot["config"]["rooms"][api.room_id]["automation_enabled"]


async def test_saving_is_validated_atomic_and_revision_checked(api) -> None:
    """Invalid or stale browser writes cannot partially overwrite saved settings."""
    snapshot = await configure(api)
    duplicate = deepcopy(snapshot["config"])
    duplicate["rooms"][api.other_room_id] = {"lights": [api.lamp]}
    rejected = await request(
        api.client, "halo/save", config=duplicate, revision=snapshot["revision"]
    )
    assert not rejected["success"]
    assert rejected["error"]["code"] == "invalid_config"
    unchanged = (await request(api.client, "halo/get"))["result"]
    assert unchanged["revision"] == snapshot["revision"]
    assert unchanged["config"] == snapshot["config"]
    stale = await request(api.client, "halo/save", config=api.config, revision=0)
    assert not stale["success"]
    assert stale["error"]["code"] == "conflict"


async def test_permissions_separate_control_from_configuration(
    hass: HomeAssistant, api, hass_ws_client, hass_read_only_access_token
) -> None:
    """Regular users control rooms but only administrators can edit configuration."""
    await configure(api)
    group = await hass.auth.async_get_group(GROUP_ID_USER)
    user = MockUser(groups=[group]).add_to_hass(hass)
    refresh = await hass.auth.async_create_refresh_token(
        user, "https://halo.example.test"
    )
    token = hass.auth.async_create_access_token(refresh)
    client = await hass_ws_client(hass, access_token=token)
    read_only = await hass_ws_client(hass, access_token=hass_read_only_access_token)
    try:
        visible = (await request(client, "halo/get"))["result"]
        assert not visible["is_admin"]
        for command, fields in (
            ("halo/save", {"config": api.config, "revision": visible["revision"]}),
            (
                "halo/scene/import",
                {"room_id": api.room_id, "config": {"name": "Native", "entities": {}}},
            ),
            ("halo/edit/begin", {"room_id": api.room_id}),
            (
                "halo/edit/end",
                {
                    "room_id": api.room_id,
                    "token": "not-owned",
                    "save": True,
                    "capture": True,
                },
            ),
        ):
            response = await request(client, command, **fields)
            assert not response["success"]
            assert response["error"]["code"] == "unauthorized"
        response = await request(
            client, "halo/command", room_id=api.room_id, command="turn_off"
        )
        assert response["success"], response
        assert hass.states.get(api.lamp).state == "off"
        assert api.calls[-1].context.user_id == user.id
        response = await request(
            read_only, "halo/command", room_id=api.room_id, command="turn_on"
        )
        assert not response["success"]
        assert hass.states.get(api.lamp).state == "off"
    finally:
        await client.close()
        await read_only.close()


async def test_editor_owner_preview_and_cancel(
    hass: HomeAssistant, api, hass_ws_client
) -> None:
    """A second connection cannot take over editing; cancellation restores lamps."""
    await configure(api)
    editor = await request(api.client, "halo/edit/begin", room_id=api.room_id)
    assert editor["success"], editor
    token = editor["result"]["token"]
    other = await hass_ws_client(hass)
    try:
        locked = await request(other, "halo/edit/begin", room_id=api.room_id)
        assert not locked["success"]
        assert locked["error"]["code"] == "edit_locked"
        stolen = await request(
            other,
            "halo/edit/preview",
            room_id=api.room_id,
            token=token,
            lights={api.lamp: {"state": "off"}},
        )
        assert not stolen["success"]
        assert stolen["error"]["code"] == "invalid_edit"
        captured = await request(
            other,
            "halo/edit/end",
            room_id=api.room_id,
            token=token,
            save=True,
            capture=True,
            scene={"id": "stolen", "name": "Stolen", "lights": {}},
            revision=1,
        )
        assert not captured["success"]
        assert captured["error"]["code"] == "invalid_edit"
        assert hass.states.get(api.lamp).state == "on"
        preview = await request(
            api.client,
            "halo/edit/preview",
            room_id=api.room_id,
            token=token,
            lights={api.lamp: {"state": "on", "brightness_pct": 20}},
        )
        assert preview["success"], preview
        assert hass.states.get(api.lamp).attributes["brightness"] == 51
        assert preview["result"]["status"][api.room_id]["editing"]
        canceled = await request(
            api.client, "halo/edit/end", room_id=api.room_id, token=token, save=False
        )
        assert canceled["success"], canceled
        assert hass.states.get(api.lamp).attributes["brightness"] == 128
        assert not canceled["result"]["status"][api.room_id]["editing"]
        assert not canceled["result"]["config"]["rooms"][api.room_id][
            "automation_enabled"
        ]
    finally:
        await other.close()


async def test_scene_save_and_manual_pause_survive_reload(
    hass: HomeAssistant, api
) -> None:
    """Scene configuration and manual pause deadlines persist in HA storage."""
    initial = await configure(api)
    editor = await request(api.client, "halo/edit/begin", room_id=api.room_id)
    scene = {
        "id": "cinema",
        "name": "Cinéma",
        "lights": {api.lamp: {"state": "on", "brightness_pct": 20}},
    }
    saved = await request(
        api.client,
        "halo/edit/end",
        room_id=api.room_id,
        token=editor["result"]["token"],
        save=True,
        scene=scene,
        revision=initial["revision"],
    )
    assert saved["success"], saved
    applied = await request(
        api.client,
        "halo/command",
        room_id=api.room_id,
        command="scene",
        scene_id="cinema",
    )
    assert applied["success"], applied
    pause = applied["result"]["status"][api.room_id]["pause_until"]
    assert pause is not None
    before = api.entry.runtime_data
    assert await hass.config_entries.async_reload(api.entry.entry_id)
    await hass.async_block_till_done()
    after = (await request(api.client, "halo/get"))["result"]
    assert api.entry.runtime_data is not before
    assert after["status"][api.room_id]["pause_until"] == pause
    assert after["config"]["rooms"][api.room_id]["scenes"][0]["name"] == "Cinéma"
    assert not after["config"]["rooms"][api.room_id]["automation_enabled"]


@pytest.mark.parametrize(
    ("mode", "color"),
    [
        ("rgbw", {"rgbw_color": [13, 27, 82, 54]}),
        ("rgbww", {"rgbww_color": [13, 27, 82, 54, 201]}),
        ("white", {}),
        ("onoff", {}),
    ],
)
async def test_native_scene_capture_persists_real_state_and_replays_effect(
    hass, api, mode, color
):
    initial = await configure(api)
    editor = await request(api.client, "halo/edit/begin", room_id=api.room_id)
    token = editor["result"]["token"]
    # Simulate the state reported after changing the native HA light dialog.
    actual = {
        "brightness": 123,
        "effect": "candle",
        "color_mode": mode,
        **color,
        "supported_color_modes": ["rgb", "white"]
        if mode in ("white", "onoff")
        else [mode],
        "supported_features": LightEntityFeature.EFFECT,
        "effect_list": ["off", "candle"],
        "friendly_name": "Physical lamp",
        "hs_color": [42, 37],
        "rgb_color": [255, 250, 200],
    }
    hass.states.async_set(api.lamp, "on", actual)
    scene = {"id": "native", "name": "Native", "lights": {api.lamp: {"state": "off"}}}
    stale = await request(
        api.client,
        "halo/edit/end",
        room_id=api.room_id,
        token=token,
        save=True,
        scene=scene,
        capture=True,
        revision=initial["revision"] - 1,
    )
    assert not stale["success"] and stale["error"]["code"] == "conflict"
    assert api.entry.runtime_data.engines[api.room_id].status["editing"]
    saved = await request(
        api.client,
        "halo/edit/end",
        room_id=api.room_id,
        token=token,
        save=True,
        scene=scene,
        capture=True,
        revision=initial["revision"],
    )
    assert saved["success"], saved
    expected = {
        "state": "on",
        "brightness": 123,
        "color_mode": mode,
        "effect": "candle",
        **color,
    }
    assert saved["result"]["config"]["rooms"][api.room_id]["scenes"][0]["lights"] == {
        api.lamp: expected
    }
    assert await hass.config_entries.async_reload(api.entry.entry_id)
    await hass.async_block_till_done()
    hass.states.async_set(
        api.lamp, "off", {**actual, "effect": "off", "brightness": 19}
    )
    applied = await request(
        api.client,
        "halo/command",
        room_id=api.room_id,
        command="scene",
        scene_id="native",
    )
    assert applied["success"], applied
    params = {"entity_id": api.lamp, "brightness": 123, "effect": "candle", **color}
    if mode == "white":
        params["white"] = 123
    assert api.calls[-1].data == params


async def test_capture_unavailable_members_retains_known_targets_without_inventing_off(
    hass, api
):
    api.config["rooms"][api.room_id]["lights"] += [
        "light.unavailable_lamp",
        "light.known",
        "light.unknown",
    ]
    hass.states.async_set(
        "light.known",
        "on",
        {"brightness": 123, "supported_color_modes": ["brightness"]},
    )
    hass.states.async_set("light.unknown", "unknown")
    initial = await configure(api)
    editor = await request(api.client, "halo/edit/begin", room_id=api.room_id)
    hass.states.async_set("light.known", "unavailable")
    hass.states.async_set(api.lamp, "off", {"supported_color_modes": ["brightness"]})
    remembered = {"state": "on", "brightness_pct": 21, "effect": "candle"}
    result = await request(
        api.client,
        "halo/edit/end",
        room_id=api.room_id,
        token=editor["result"]["token"],
        save=True,
        capture=True,
        revision=initial["revision"],
        scene={
            "id": "native",
            "name": "Native",
            "lights": {"light.unavailable_lamp": remembered},
        },
    )
    assert result["success"], result
    states = result["result"]["config"]["rooms"][api.room_id]["scenes"][0]["lights"]
    assert states == {
        api.lamp: {"state": "off"},
        "light.unavailable_lamp": remembered,
        "light.known": {"state": "on", "brightness": 123},
    }


async def test_import_returns_detached_partial_draft_without_writes_or_commands(
    hass, api
):
    api.config["rooms"][api.room_id]["lights"] += ["light.unavailable_lamp"]
    initial = await configure(api)
    await hass.async_block_till_done()
    source = {
        "id": "source-scene",
        "name": "Home cinema",
        "entities": {
            api.lamp: {"state": "on", "brightness": 153, "effect": "Candle"},
            "light.unavailable_lamp": False,
            "light.outside": {"state": "invalid"},
            "switch.tv": {"state": "on"},
        },
    }
    manager = api.entry.runtime_data
    with patch.object(manager._store, "async_save") as save:
        imported = await request(
            api.client, "halo/scene/import", room_id=api.room_id, config=source
        )
        save.assert_not_called()
    assert imported["success"], imported
    assert imported["result"]["ignored_entities"] == 2
    draft = imported["result"]["scene"]
    assert draft["name"] == "Home cinema"
    assert draft["id"] != source["id"]
    assert draft["conditions"] is None and not draft["can_turn_on"]
    assert draft["lights"] == {
        api.lamp: {"state": "on", "brightness": 153, "effect": "Candle"},
        "light.unavailable_lamp": {"state": "off"},
    }
    assert not api.calls
    assert manager.config == initial["config"]
    assert manager.revision == initial["revision"]
    assert not manager.engines[api.room_id].status["editing"]


@pytest.mark.parametrize(
    ("entities", "error"),
    [
        ({"light.outside": "on"}, "no_matching_lights"),
        ({}, "no_matching_lights"),
        ({"LAMP": {"state": "on", "brightness": 500}}, "invalid_config"),
        ([], "invalid_config"),
    ],
)
async def test_import_rejects_invalid_or_unrelated_configuration(api, entities, error):
    await configure(api)
    if isinstance(entities, dict) and "LAMP" in entities:
        entities = {api.lamp: entities["LAMP"]}
    response = await request(
        api.client,
        "halo/scene/import",
        room_id=api.room_id,
        config={"name": "Native", "entities": entities},
    )
    assert not response["success"] and response["error"]["code"] == error
    if isinstance(entities, dict) and api.lamp in entities:
        assert api.lamp in response["error"]["message"]
    assert not api.calls
    assert api.entry.runtime_data.revision == 1
    assert not api.entry.runtime_data.config["rooms"][api.room_id]["scenes"]


async def test_import_unknown_room_is_rejected(api):
    await configure(api)
    response = await request(
        api.client,
        "halo/scene/import",
        room_id=api.other_room_id,
        config={"name": "Native", "entities": {api.lamp: "on"}},
    )
    assert not response["success"] and response["error"]["code"] == "not_found"


async def test_saving_import_does_not_reapply_active_room_or_other_rooms(hass, api):
    api.config["rooms"][api.room_id].update(
        automation_enabled=True,
        base={api.lamp: {"state": "on", "brightness": 190}},
    )
    hass.states.async_set(
        "light.other_room", "on", {"supported_color_modes": ["onoff"]}
    )
    api.config["rooms"][api.other_room_id] = {
        "lights": ["light.other_room"],
        "automation_enabled": True,
    }
    initial = await configure(api)
    await hass.async_block_till_done()
    api.calls.clear()
    before = hass.states.get(api.lamp)
    imported = await request(
        api.client,
        "halo/scene/import",
        room_id=api.room_id,
        config={
            "name": "Native",
            "entities": {api.lamp: {"state": "on", "brightness": 90}},
        },
    )
    draft = deepcopy(initial["config"])
    draft["rooms"][api.room_id]["scenes"].append(imported["result"]["scene"])
    saved = await request(
        api.client, "halo/save", config=draft, revision=initial["revision"]
    )
    assert saved["success"], saved
    await hass.async_block_till_done()
    assert not api.calls
    assert hass.states.get(api.lamp) == before
    assert (
        saved["result"]["config"]["rooms"][api.room_id]["scenes"]
        == draft["rooms"][api.room_id]["scenes"]
    )
    # A real behavior change still reconfigures the affected room normally.
    draft["rooms"][api.room_id]["base"][api.lamp]["brightness"] = 230
    changed = await request(
        api.client, "halo/save", config=draft, revision=saved["result"]["revision"]
    )
    assert changed["success"], changed
    assert hass.states.get(api.lamp).attributes["brightness"] == 230
    assert {call.data["entity_id"] for call in api.calls} == {api.lamp}


async def test_partial_capture_excludes_lamps_from_live_and_fallback_states(hass, api):
    hass.states.async_set(
        "light.other", "on", {"brightness": 97, "supported_color_modes": ["brightness"]}
    )
    api.config["rooms"][api.room_id]["lights"] += [
        "light.other",
        "light.unavailable_lamp",
    ]
    initial = await configure(api)
    editor = await request(api.client, "halo/edit/begin", room_id=api.room_id)
    hass.states.async_set(api.lamp, "unavailable")
    remembered = {"state": "on", "brightness": 180, "effect": "Candle"}
    fields = {
        "room_id": api.room_id,
        "token": editor["result"]["token"],
        "save": True,
        "capture": True,
        "capture_entities": [api.lamp],
        "scene": {
            "id": "partial",
            "name": "Partial",
            "lights": {
                api.lamp: remembered,
                "light.unavailable_lamp": {"state": "off"},
            },
        },
    }
    conflict = await request(
        api.client, "halo/edit/end", **fields, revision=initial["revision"] - 1
    )
    assert not conflict["success"] and conflict["error"]["code"] == "conflict"
    assert api.entry.runtime_data.engines[api.room_id].status["editing"]
    saved = await request(
        api.client, "halo/edit/end", **fields, revision=initial["revision"]
    )
    assert saved["success"], saved
    assert saved["result"]["config"]["rooms"][api.room_id]["scenes"][0]["lights"] == {
        api.lamp: remembered
    }
    assert hass.states.get("light.other").attributes["brightness"] == 97
    assert not api.calls


@pytest.mark.parametrize(
    "fields",
    [
        {"capture_entities": ["light.outside"]},
        {"capture_entities": ["LAMP", "LAMP"]},
        {"capture_entities": ["LAMP"], "capture": False},
        {"capture_entities": ["LAMP"], "save": False},
    ],
)
async def test_capture_selection_validation_preserves_editor(api, fields):
    initial = await configure(api)
    editor = await request(api.client, "halo/edit/begin", room_id=api.room_id)
    fields = deepcopy(fields)
    fields["capture_entities"] = [
        api.lamp if entity == "LAMP" else entity
        for entity in fields["capture_entities"]
    ]
    result = await request(
        api.client,
        "halo/edit/end",
        **{
            "room_id": api.room_id,
            "token": editor["result"]["token"],
            "save": True,
            "capture": True,
            "revision": initial["revision"],
            "scene": {"id": "invalid", "name": "Invalid", "lights": {}},
            **fields,
        },
    )
    assert not result["success"] and result["error"]["code"] == "invalid_config"
    assert api.entry.runtime_data.engines[api.room_id].status["editing"]
    assert api.entry.runtime_data.revision == initial["revision"]
    assert not api.calls


async def test_subscription_survives_entry_reload(
    hass: HomeAssistant, api, hass_ws_client
) -> None:
    """Existing dashboards receive snapshots from the replacement manager."""
    await configure(api)
    subscriber = await hass_ws_client(hass)
    try:
        await subscriber.send_json_auto_id({"type": "halo/subscribe"})
        confirmation = await subscriber.receive_json()
        initial = await subscriber.receive_json()
        assert confirmation["success"]
        assert initial["type"] == "event"
        assert initial["event"]["revision"] == 1
        assert await hass.config_entries.async_reload(api.entry.entry_id)
        await hass.async_block_till_done()
        result = await request(
            api.client,
            "halo/command",
            room_id=api.room_id,
            command="natural",
            enabled=False,
        )
        assert result["success"], result
        async with asyncio.timeout(2):
            while True:
                event = await subscriber.receive_json()
                if event["event"]["revision"] == result["result"]["revision"]:
                    break
        assert not event["event"]["config"]["rooms"][api.room_id]["natural_enabled"]
    finally:
        await subscriber.close()


async def test_room_rename_preserves_identity_and_removal_cleans_up(
    hass: HomeAssistant, api
) -> None:
    """Renames retain native identities and removal leaves no device or entities."""
    snapshot = await configure(api)
    await hass.async_block_till_done()
    devices, entities = dr.async_get(hass), er.async_get(hass)
    device = devices.async_get_device_by_identifier(
        (DOMAIN, api.room_id), api.entry.entry_id
    )
    before = {
        entry.entity_id
        for entry in er.async_entries_for_config_entry(entities, api.entry.entry_id)
    }
    ar.async_get(hass).async_update(api.room_id, name="Grand salon")
    await hass.async_block_till_done()
    renamed = devices.async_get_device_by_identifier(
        (DOMAIN, api.room_id), api.entry.entry_id
    )
    assert renamed.id == device.id
    assert renamed.name == "Grand salon"
    assert {
        entry.entity_id
        for entry in er.async_entries_for_config_entry(entities, api.entry.entry_id)
    } == before

    removed = await request(
        api.client, "halo/save", config={"rooms": {}}, revision=snapshot["revision"]
    )
    assert removed["success"], removed
    await hass.async_block_till_done()
    assert devices.async_get(device.id) is None
    assert not er.async_entries_for_config_entry(entities, api.entry.entry_id)
    assert all(hass.states.get(entity_id) is None for entity_id in before)


@pytest.mark.parametrize("duration", [0, 45.5])
async def test_presence_return_setting_roundtrip_and_stale_save(hass, api, duration):
    """Existing config gains the default; explicit settings survive real reloads."""
    await configure(api)
    snapshot = (await request(api.client, "halo/get"))["result"]
    assert snapshot["config"]["presence_return_window"] == 30
    config = deepcopy(snapshot["config"])
    config["presence_return_window"] = duration
    response = await request(
        api.client, "halo/save", config=config, revision=snapshot["revision"]
    )
    assert response["success"], response
    stale = await request(
        api.client,
        "halo/save",
        config=snapshot["config"],
        revision=snapshot["revision"],
    )
    assert not stale["success"] and stale["error"]["code"] == "conflict"
    assert await hass.config_entries.async_reload(api.entry.entry_id)
    await hass.async_block_till_done()
    saved = (await request(api.client, "halo/get"))["result"]
    assert saved["config"]["presence_return_window"] == duration
    assert not api.calls


async def test_presence_return_setting_rejected_atomically(api):
    await configure(api)
    snapshot = (await request(api.client, "halo/get"))["result"]
    invalid = deepcopy(snapshot["config"])
    invalid["presence_return_window"] = -1
    response = await request(
        api.client, "halo/save", config=invalid, revision=snapshot["revision"]
    )
    assert not response["success"] and response["error"]["code"] == "invalid_config"
    current = (await request(api.client, "halo/get"))["result"]
    assert current["revision"] == snapshot["revision"]
    assert current["config"] == snapshot["config"]


async def test_native_scene_inspection_is_admin_only_and_read_only(
    hass, api, hass_ws_client, hass_read_only_access_token
):
    saved = await configure(api)
    hass.states.async_set(
        "scene.native",
        "unknown",
        {"entity_id": [api.lamp, "light.outside", "switch.tv"]},
    )
    inspected = await request(
        api.client, "halo/scene/inspect", room_id=api.room_id, entity_id="scene.native"
    )
    assert inspected["success"]
    assert inspected["result"]["outside_lights"] == ["light.outside"]
    assert inspected["result"]["other_entities"] == ["switch.tv"]
    assert inspected["result"]["complete"]
    assert inspected["result"]["available"]
    current = (await request(api.client, "halo/get"))["result"]
    assert current["config"] == saved["config"]
    assert current["revision"] == saved["revision"]
    assert not api.calls
    reader = await hass_ws_client(hass, access_token=hass_read_only_access_token)
    denied = await request(
        reader, "halo/scene/inspect", room_id=api.room_id, entity_id="scene.native"
    )
    assert not denied["success"] and denied["error"]["code"] == "unauthorized"
    await reader.close()
    invalid = await request(
        api.client, "halo/scene/inspect", room_id=api.room_id, entity_id="light.outside"
    )
    assert not invalid["success"]


async def test_linked_scene_uses_real_native_reproduction_and_preserves_omitted_lamp(
    hass, api
):
    saved = await configure(api)
    for entity_id in ("light.omitted", "light.outside"):
        hass.states.async_set(
            entity_id,
            "on",
            {
                "brightness": 127,
                "color_mode": "brightness",
                "supported_color_modes": ["brightness"],
            },
        )
    await hass.services.async_call(
        "scene",
        "create",
        {
            "scene_id": "native",
            "entities": {
                api.lamp: {"state": "on", "brightness": 200, "effect": "Candle"},
                "light.outside": {"state": "off"},
            },
        },
        blocking=True,
    )
    config = deepcopy(saved["config"])
    config["rooms"][api.room_id]["lights"].append("light.omitted")
    config["rooms"][api.room_id]["scenes"] = [
        {
            "id": "linked",
            "name": "Native link",
            "type": "home_assistant",
            "scene_entity_id": "scene.native",
            "conditions": None,
            "can_turn_on": False,
        }
    ]
    response = await request(
        api.client, "halo/save", config=config, revision=saved["revision"]
    )
    assert response["success"], response
    assert not api.calls
    response = await request(
        api.client,
        "halo/command",
        room_id=api.room_id,
        command="scene",
        scene_id="linked",
    )
    assert response["success"], response
    await hass.async_block_till_done()
    assert {call.data["entity_id"] for call in api.calls} == {
        api.lamp,
        "light.outside",
    }
    assert all(call.context.user_id for call in api.calls)
    assert hass.states.get(api.lamp).attributes["brightness"] == 200
    assert hass.states.get(api.lamp).attributes["effect"] == "Candle"
    assert hass.states.get("light.outside").state == "off"
    assert hass.states.get("light.omitted").attributes["brightness"] == 127
    assert (
        api.entry.runtime_data.engines[api.room_id].lighting_status["scene_id"]
        == "linked"
    )


async def test_renaming_an_active_link_does_not_recall_it(hass, api):
    saved = await configure(api)
    calls = []

    async def recall(call):
        calls.append(call)

    hass.services.async_register("scene", "turn_on", recall)
    hass.states.async_set("scene.native", "unknown")
    config = deepcopy(saved["config"])
    room = config["rooms"][api.room_id]
    room["automation_enabled"] = True
    room["scenes"] = [
        {
            "id": "linked",
            "name": "First",
            "type": "home_assistant",
            "scene_entity_id": "scene.native",
            "can_turn_on": True,
            "conditions": {"type": "state", "entity_id": api.lamp, "state": "on"},
        }
    ]
    response = await request(
        api.client, "halo/save", config=config, revision=saved["revision"]
    )
    assert response["success"], response
    assert len(calls) == 1
    room["scenes"][0]["name"] = "Renamed"
    response = await request(
        api.client, "halo/save", config=config, revision=response["result"]["revision"]
    )
    assert response["success"], response
    assert len(calls) == 1
