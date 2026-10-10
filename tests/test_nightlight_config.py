"""Nightlight defaults, authenticated editing and explicit group boundaries."""

from copy import deepcopy
from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er
from test_api import api as api
from test_api import configure, request

from custom_components.halo.models import validate_config, validate_nightlight
from custom_components.halo.nightlight import nightlight_conflicts


def test_legacy_defaults_are_detached_and_preserve_other_settings():
    old = {"rooms": {"a": {"lights": ["light.a"], "absence_delay": 7}}}
    normalized = validate_config(old)
    assert normalized["rooms"]["a"]["nightlight"] == {"enabled": False, "lights": {}}
    assert normalized["rooms"]["a"]["absence_delay"] == 7
    normalized["rooms"]["a"]["nightlight"]["lights"]["light.a"] = {"state": "on"}
    assert "nightlight" not in old["rooms"]["a"]
    assert validate_config(old)["rooms"]["a"]["nightlight"]["lights"] == {}


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        {"enabled": "yes"},
        {"enabled": True},
        {"enabled": True, "lights": {"light.a": {"state": "off"}}},
        {"enabled": True, "lights": {"light.a": {"state": "on", "brightness": 0}}},
        {"enabled": True, "lights": {"light.a": {"state": "on", "brightness_pct": 0}}},
        {"lights": {"light.outside": {"state": "on"}}},
        {"lights": {"light.a": {"state": "unknown"}}},
        {"enabled": False, "unexpected": 1},
    ],
)
def test_invalid_nightlights_are_rejected(value):
    with pytest.raises(ValueError):
        validate_nightlight(value, ["light.a"])


def test_presence_required_but_lux_optional():
    room = {
        "lights": ["light.a"],
        "nightlight": {"enabled": True, "lights": {"light.a": {"state": "on"}}},
    }
    with pytest.raises(ValueError, match="presence"):
        validate_config({"rooms": {"a": room}})
    room["presence_entity_id"] = "binary_sensor.presence"
    assert (
        validate_config({"rooms": {"a": room}})["rooms"]["a"]["lux_entity_id"] is None
    )


async def test_known_group_overlap_is_rejected_opaque_is_reported(hass, api):
    hass.states.async_set("light.group", "on", {"entity_id": [api.lamp]})
    api.config["rooms"][api.room_id].update(
        lights=[api.lamp, "light.group"],
        presence_entity_id="binary_sensor.presence",
        nightlight={"enabled": True, "lights": {api.lamp: {"state": "on"}}},
    )
    rejected = await request(api.client, "halo/save", config=api.config, revision=0)
    assert rejected["error"]["code"] == "invalid_config"
    assert api.entry.runtime_data.revision == 0
    assert api.calls == []
    room = api.config["rooms"][api.room_id]
    room["nightlight"]["lights"] = {"light.group": {"state": "on"}}
    assert nightlight_conflicts(hass, room)
    # Nested composition is also checked, without changing command targets.
    hass.states.async_set("light.group", "on", {"entity_id": ["light.inner"]})
    hass.states.async_set("light.inner", "on", {"entity_id": [api.lamp]})
    assert nightlight_conflicts(hass, room)
    hass.states.async_set("light.group", "on", {"is_hue_group": True})
    result = await configure(api)
    group = next(
        light for light in result["lights"] if light["entity_id"] == "light.group"
    )
    assert group["is_group"] and not group["group_members_complete"]


@pytest.mark.parametrize(
    "mode,color",
    [
        ("color_temp", {"color_temp_kelvin": 2200}),
        ("rgbw", {"rgbw_color": [10, 20, 30, 40]}),
        ("rgbww", {"rgbww_color": [10, 20, 30, 40, 50]}),
    ],
)
async def test_nightlight_capture_keeps_effects_selection_and_survives_reload(
    hass, api, mode, color
):
    api.config["rooms"][api.room_id].update(
        lights=[api.lamp, "light.unavailable_lamp"],
        presence_entity_id="binary_sensor.presence",
    )
    initial = await configure(api)
    token = (await request(api.client, "halo/edit/begin", room_id=api.room_id))[
        "result"
    ]["token"]
    hass.states.async_set(
        api.lamp,
        "on",
        {"brightness": 23, "effect": "Candle", "color_mode": mode, **color},
    )
    fields = dict(
        room_id=api.room_id,
        token=token,
        target="nightlight",
        save=True,
        nightlight={"enabled": True, "lights": {}},
        capture=True,
        capture_entities=[api.lamp],
    )
    stale = await request(
        api.client, "halo/edit/end", **fields, revision=initial["revision"] - 1
    )
    assert stale["error"]["code"] == "conflict"
    assert api.entry.runtime_data.engines[api.room_id].status["editing"]
    saved = await request(
        api.client, "halo/edit/end", **fields, revision=initial["revision"]
    )
    assert saved["success"], saved
    expected = {
        "enabled": True,
        "lights": {
            api.lamp: {
                "state": "on",
                "brightness": 23,
                "effect": "Candle",
                "color_mode": mode,
                **color,
            }
        },
    }
    room = saved["result"]["config"]["rooms"][api.room_id]
    assert room["nightlight"] == expected
    assert room["scenes"] == []
    assert api.calls == []  # Configuration alone, automation remains disabled.
    assert await hass.config_entries.async_reload(api.entry.entry_id)
    await hass.async_block_till_done()
    after = (await request(api.client, "halo/get"))["result"]
    assert after["config"]["rooms"][api.room_id]["nightlight"] == expected


async def test_failed_capture_commit_and_cancel_preserve_settings(hass, api):
    initial = await configure(api)
    token = (await request(api.client, "halo/edit/begin", room_id=api.room_id))[
        "result"
    ]["token"]
    preview = await request(
        api.client,
        "halo/edit/preview",
        room_id=api.room_id,
        token=token,
        lights={api.lamp: {"state": "on", "brightness": 9}},
    )
    assert preview["success"]
    engine = api.entry.runtime_data.engines[api.room_id]
    with patch.object(
        api.entry.runtime_data._store,
        "async_save",
        side_effect=OSError("disk unavailable"),
    ):
        with pytest.raises(OSError):
            await api.entry.runtime_data.async_end_edit(
                api.room_id,
                token,
                api.entry.runtime_data._edits[api.room_id][1],
                True,
                revision=initial["revision"],
                target="nightlight",
                nightlight={"enabled": False, "lights": {}},
                capture=True,
                capture_entities=[api.lamp],
            )
    assert engine.status["editing"]
    assert api.entry.runtime_data.config == initial["config"]
    cancel = await request(
        api.client,
        "halo/edit/end",
        room_id=api.room_id,
        token=token,
        target="nightlight",
        save=False,
    )
    assert cancel["success"]
    assert hass.states.get(api.lamp).attributes["brightness"] == 128
    assert not engine.status["editing"]


async def test_unavailable_capture_keeps_saved_value_and_rejects_outside_selection(
    hass, api
):
    api.config["rooms"][api.room_id]["nightlight"] = {
        "enabled": False,
        "lights": {api.lamp: {"state": "on", "brightness": 12}},
    }
    initial = await configure(api)
    token = (await request(api.client, "halo/edit/begin", room_id=api.room_id))[
        "result"
    ]["token"]
    hass.states.async_set(api.lamp, "unavailable")
    fields = dict(
        room_id=api.room_id,
        token=token,
        save=True,
        target="nightlight",
        capture=True,
        nightlight=deepcopy(api.config["rooms"][api.room_id]["nightlight"]),
        revision=initial["revision"],
    )
    bad = await request(
        api.client, "halo/edit/end", **fields, capture_entities=["light.outside"]
    )
    assert bad["error"]["code"] == "invalid_config"
    good = await request(
        api.client, "halo/edit/end", **fields, capture_entities=[api.lamp]
    )
    assert good["success"]
    assert (
        good["result"]["config"]["rooms"][api.room_id]["nightlight"]
        == fields["nightlight"]
    )


async def test_nightlight_editor_requires_owner_and_admin(
    hass, api, hass_ws_client, hass_read_only_access_token
):
    initial = await configure(api)
    token = (await request(api.client, "halo/edit/begin", room_id=api.room_id))[
        "result"
    ]["token"]
    fields = dict(
        room_id=api.room_id,
        token=token,
        save=True,
        target="nightlight",
        nightlight={"enabled": False, "lights": {}},
        revision=initial["revision"],
    )
    other = await hass_ws_client(hass)
    readonly = await hass_ws_client(hass, access_token=hass_read_only_access_token)
    try:
        wrong_owner = await request(other, "halo/edit/end", **fields)
        assert wrong_owner["error"]["code"] == "invalid_edit"
        unauthorized = await request(readonly, "halo/edit/end", **fields)
        assert unauthorized["error"]["code"] == "unauthorized"
    finally:
        await other.close()
        await readonly.close()
    assert api.entry.runtime_data.config == initial["config"]


async def test_hidden_group_members_do_not_claim_complete(
    hass, api, hass_read_only_user
):
    # An unavailable registered Hue group remains explicitly opaque.
    group = er.async_get(hass).async_get_or_create(
        "light",
        "hue",
        "night_group",
        suggested_object_id="night_group",
        translation_key="hue_grouped_light",
    )
    hass.states.async_set(group.entity_id, "unavailable")
    snapshot = api.entry.runtime_data.snapshot(hass_read_only_user)
    item = next(
        light for light in snapshot["lights"] if light["entity_id"] == group.entity_id
    )
    assert item["is_group"] and item["group_members_complete"] is False


@pytest.mark.parametrize(
    "fields",
    [
        {
            "target": "nightlight",
            "scene": {"id": "wrong", "name": "Wrong", "lights": {}},
            "nightlight": {},
        },
        {"target": "scene", "nightlight": {}},
        {"target": "nightlight"},
    ],
)
async def test_editor_targets_cannot_be_confused(api, fields):
    initial = await configure(api)
    token = (await request(api.client, "halo/edit/begin", room_id=api.room_id))[
        "result"
    ]["token"]
    result = await request(
        api.client,
        "halo/edit/end",
        room_id=api.room_id,
        token=token,
        save=True,
        revision=initial["revision"],
        **fields,
    )
    assert result["error"]["code"] == "invalid_config"
    assert api.entry.runtime_data.engines[api.room_id].status["editing"]
    assert api.entry.runtime_data.config == initial["config"]


async def test_capture_validates_known_group_conflict_before_commit(hass, api):
    hass.states.async_set("light.group", "on", {"entity_id": [api.lamp]})
    api.config["rooms"][api.room_id].update(
        lights=[api.lamp, "light.group"], presence_entity_id="binary_sensor.presence"
    )
    initial = await configure(api)
    token = (await request(api.client, "halo/edit/begin", room_id=api.room_id))[
        "result"
    ]["token"]
    result = await request(
        api.client,
        "halo/edit/end",
        room_id=api.room_id,
        token=token,
        save=True,
        target="nightlight",
        revision=initial["revision"],
        nightlight={"enabled": True, "lights": {}},
        capture=True,
        capture_entities=[api.lamp],
    )
    assert result["error"]["code"] == "invalid_config"
    assert api.entry.runtime_data.config == initial["config"]
    assert api.entry.runtime_data.engines[api.room_id].status["editing"]
    assert not api.calls
