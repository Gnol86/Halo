"""Exercise Halo's real manager through authenticated WebSocket connections."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest
from homeassistant.auth.const import GROUP_ID_USER
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
            ("halo/edit/begin", {"room_id": api.room_id}),
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
