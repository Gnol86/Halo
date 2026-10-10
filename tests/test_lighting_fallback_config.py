"""Validate and persist no-lux authorization without changing legacy rooms."""

from copy import deepcopy
from unittest.mock import patch

import pytest
from homeassistant.auth.const import GROUP_ID_USER
from pytest_homeassistant_custom_component.common import MockUser
from test_api import api as api
from test_api import configure, request

from custom_components.halo.models import (
    LIGHTING_FALLBACK_DEFAULTS,
    validate_config,
    validate_lighting_fallback,
)


def test_legacy_fallback_is_always_and_never_mutates_supplied_config():
    supplied = {"rooms": {"a": {"absence_delay": 9}, "b": {}}}
    config = validate_config(supplied)
    assert config["rooms"]["a"]["lighting_fallback"] == LIGHTING_FALLBACK_DEFAULTS
    assert config["rooms"]["a"]["absence_delay"] == 9
    config["rooms"]["a"]["lighting_fallback"]["mode"] = "sun"
    assert config["rooms"]["b"]["lighting_fallback"]["mode"] == "always"
    assert "lighting_fallback" not in supplied["rooms"]["a"]
    assert LIGHTING_FALLBACK_DEFAULTS["mode"] == "always"


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        {"mode": "lux"},
        {"mode": True},
        {"extra": 1},
        {"start": "24:00"},
        {"end": "08:60"},
        {"start": "8:00"},
        {"start": "08:00:00"},
        {"start": 800},
        {"start": "08:00"},
        {"linked": 1},
        {"turn_off": "yes"},
        {"morning_below": True},
        {"morning_below": float("nan")},
        {"evening_below": float("inf")},
        {"morning_below": -90.01},
        {"evening_below": 90.01},
    ],
)
def test_invalid_fallback_is_rejected_even_when_inactive(value):
    with pytest.raises(ValueError):
        validate_lighting_fallback(value)


@pytest.mark.parametrize("mode", ["always", "time", "sun"])
def test_all_modes_preserve_inactive_choices_and_signed_fractional_elevations(mode):
    selected = dict(
        mode=mode,
        start="21:15",
        end="07:05",
        linked=True,
        morning_below=-6.5,
        evening_below=4.25,
        turn_off=True,
    )
    config = validate_config(
        {
            "rooms": {
                "a": {
                    "lux_entity_id": "sensor.lux",
                    "lux_threshold": 10,
                    "lighting_fallback": selected,
                }
            }
        }
    )
    assert config["rooms"]["a"]["lighting_fallback"] == selected
    config["rooms"]["a"]["lighting_fallback"]["evening_below"] = 0
    assert selected["evening_below"] == 4.25
    assert validate_lighting_fallback({"morning_below": -90, "evening_below": 90})


async def test_api_roundtrip_keeps_fallback_across_sensor_changes_and_reload(hass, api):
    initial = await configure(api)
    room = initial["config"]["rooms"][api.room_id]
    assert room["lighting_fallback"]["mode"] == "always"
    selected = dict(
        mode="sun",
        start="23:30",
        end="05:45",
        linked=False,
        morning_below=-8.5,
        evening_below=1.5,
        turn_off=True,
    )
    config = deepcopy(initial["config"])
    config["rooms"][api.room_id]["lighting_fallback"] = selected
    revision = initial["revision"]
    for sensor in (None, "sensor.lux", None):
        config["rooms"][api.room_id].update(lux_entity_id=sensor, lux_threshold=20)
        result = await request(
            api.client, "halo/save", config=config, revision=revision
        )
        assert result["success"], result
        revision = result["result"]["revision"]
        assert (
            result["result"]["config"]["rooms"][api.room_id]["lighting_fallback"]
            == selected
        )
    assert await hass.config_entries.async_reload(api.entry.entry_id)
    await hass.async_block_till_done()
    saved = (await request(api.client, "halo/get"))["result"]
    assert saved["config"]["rooms"][api.room_id]["lighting_fallback"] == selected
    assert api.calls == []  # Configuration has not enabled automatic control.


async def test_invalid_conflicting_failed_and_non_admin_saves_leave_policy_unchanged(
    hass, api, hass_ws_client
):
    initial = await configure(api)
    draft = deepcopy(initial["config"])
    draft["rooms"][api.room_id]["lighting_fallback"]["mode"] = "time"
    bad = deepcopy(draft)
    bad["rooms"][api.room_id]["lighting_fallback"]["start"] = "08:00"
    rejected = await request(
        api.client, "halo/save", config=bad, revision=initial["revision"]
    )
    assert rejected["error"]["code"] == "invalid_config"
    stale = await request(api.client, "halo/save", config=draft, revision=0)
    assert stale["error"]["code"] == "conflict"
    manager = api.entry.runtime_data
    with patch.object(
        manager._store, "async_save", side_effect=OSError("disk unavailable")
    ):
        with pytest.raises(OSError):
            await manager.async_save_config(draft, initial["revision"])
    group = await hass.auth.async_get_group(GROUP_ID_USER)
    user = MockUser(groups=[group]).add_to_hass(hass)
    refresh = await hass.auth.async_create_refresh_token(
        user, "https://halo.example.test"
    )
    client = await hass_ws_client(
        hass, access_token=hass.auth.async_create_access_token(refresh)
    )
    try:
        response = await request(
            client, "halo/save", config=draft, revision=initial["revision"]
        )
        assert response["error"]["code"] == "unauthorized"
    finally:
        await client.close()
    current = (await request(api.client, "halo/get"))["result"]
    assert current["config"] == initial["config"]
    assert current["revision"] == initial["revision"]
    assert api.calls == []
