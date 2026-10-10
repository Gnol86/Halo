"""Validate and preserve independent natural-curve modes across storage reloads."""

from copy import deepcopy
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.halo.const import DOMAIN
from custom_components.halo.manager import HaloError
from custom_components.halo.models import default_config, validate_config


async def test_initial_profile_is_saved_once_and_stays_editable(hass, hass_storage):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, title="Halo", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    original = deepcopy(entry.runtime_data.config)
    assert set(original["profiles"]) == {"default"}
    assert await hass.config_entries.async_reload(entry.entry_id)
    assert entry.runtime_data.config == original

    manager = entry.runtime_data
    changed = deepcopy(manager.config)
    profile = changed["profiles"]["default"]
    profile["name"] = "Mon rythme"
    profile["linked"] = False
    profile["evening"]["brightness"]["low"] = 15
    assert profile["morning"]["brightness"]["low"] == 40
    await manager.async_save_config(changed, manager.revision)
    assert await hass.config_entries.async_reload(entry.entry_id)
    assert entry.runtime_data.config == changed

    manager = entry.runtime_data
    deleted = deepcopy(manager.config)
    deleted["profiles"].clear()
    await manager.async_save_config(deleted, manager.revision)
    assert await hass.config_entries.async_reload(entry.entry_id)
    assert entry.runtime_data.config == deleted

    # Removing the integration removes its settings; reinstalling seeds afresh.
    storage_key = f"{DOMAIN}.{entry.entry_id}"
    assert await hass.config_entries.async_remove(entry.entry_id)
    assert storage_key not in hass_storage
    replacement = MockConfigEntry(
        domain=DOMAIN, unique_id=DOMAIN, title="Halo", data={}
    )
    replacement.add_to_hass(hass)
    assert await hass.config_entries.async_setup(replacement.entry_id)
    assert replacement.runtime_data.config == original


@pytest.mark.parametrize("include_profiles", [False, True])
async def test_existing_empty_profiles_are_not_seeded(
    hass, hass_storage, include_profiles
):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, title="Halo", data={})
    entry.add_to_hass(hass)
    config = default_config()
    if not include_profiles:
        del config["profiles"]
    saved = {"config": config, "revision": 4, "runtime": {}}
    storage_key = f"{DOMAIN}.{entry.entry_id}"
    hass_storage[storage_key] = {
        "version": 1,
        "minor_version": 1,
        "key": storage_key,
        "data": deepcopy(saved),
    }
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.runtime_data.config["profiles"] == {}
    assert entry.runtime_data.revision == 4
    assert hass_storage[storage_key]["data"] == saved
    assert await hass.config_entries.async_reload(entry.entry_id)
    assert entry.runtime_data.config["profiles"] == {}


async def test_failed_initial_profile_save_does_not_complete_setup(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, title="Halo", data={})
    entry.add_to_hass(hass)
    with patch("custom_components.halo.manager.Store", autospec=True) as store:
        store.return_value.async_load.return_value = None
        store.return_value.async_save.side_effect = OSError
        assert not await hass.config_entries.async_setup(entry.entry_id)
        store.return_value.async_save.assert_awaited_once()
    assert "manager" not in hass.data[DOMAIN]


def profile_config(*, legacy=False, curved_mode="ease_in_out"):
    """Include all four curves with distinct modes, or omit historical modes."""
    config = default_config()
    profile = {"id": "warm", "name": "My light", "linked": False}
    for period in ("morning", "evening"):
        profile[period] = {}
        for quantity in ("brightness", "temperature"):
            curve = {
                "low_elevation": -6.25,
                "high_elevation": 40.5,
                "low": 20 if quantity == "brightness" else 2200,
                "high": 100 if quantity == "brightness" else 5500,
            }
            if not legacy:
                curve["interpolation"] = (
                    curved_mode
                    if (period == "morning") == (quantity == "brightness")
                    else "linear"
                )
            profile[period][quantity] = curve
    config["profiles"]["warm"] = profile
    return config


@pytest.mark.parametrize("mode", [None, "ease_out", [], {}, 0, True])
def test_config_rejects_unknown_curve_mode(mode):
    config = profile_config()
    config["profiles"]["warm"]["evening"]["temperature"]["interpolation"] = mode
    with pytest.raises(ValueError, match="interpolation"):
        validate_config(config)


@pytest.mark.parametrize(
    ("legacy", "curved_mode"),
    [(True, "ease_in_out"), (False, "ease_in_out"), (False, "ease_in")],
)
async def test_profile_modes_survive_load_save_and_reload(
    hass, hass_storage, legacy, curved_mode
):
    config = profile_config(legacy=legacy, curved_mode=curved_mode)
    original = deepcopy(config)
    expected = validate_config(config)
    for period in ("morning", "evening"):
        for quantity in ("brightness", "temperature"):
            actual = expected["profiles"]["warm"][period][quantity]
            old = original["profiles"]["warm"][period][quantity]
            mode = old.get("interpolation", "linear")
            assert actual == old | {
                "interpolation": "ease_in_out" if mode == "ease_in" else mode
            }
    assert config == original
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, title="Halo", data={})
    entry.add_to_hass(hass)
    saved = {"config": config, "revision": 3, "runtime": {}}
    storage_key = f"{DOMAIN}.{entry.entry_id}"
    hass_storage[storage_key] = {
        "version": 1,
        "minor_version": 1,
        "key": storage_key,
        "data": saved,
    }
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass_storage[storage_key]["data"] == saved
    manager = entry.runtime_data
    assert manager.config == expected
    assert saved["config"] == original
    invalid = deepcopy(expected)
    invalid["profiles"]["warm"]["morning"]["brightness"]["interpolation"] = "bad"
    with pytest.raises(HaloError, match="interpolation") as error:
        await manager.async_save_config(invalid, manager.revision)
    assert error.value.code == "invalid_config"
    assert manager.config == expected
    assert manager.revision == 3
    await manager.async_save_config(manager.config, manager.revision)
    assert hass_storage[storage_key]["data"]["config"] == expected
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.config == expected


def test_linked_legacy_profile_does_not_require_evening_curves():
    config = profile_config(legacy=True)
    profile = config["profiles"]["warm"]
    profile["linked"] = True
    del profile["evening"]
    normalized = validate_config(config)["profiles"]["warm"]
    assert normalized["morning"]["brightness"]["interpolation"] == "linear"
    assert normalized["morning"]["temperature"]["interpolation"] == "linear"
    assert "evening" not in normalized


def test_old_acceleration_is_normalized_in_inactive_evening_curves():
    config = profile_config(curved_mode="ease_in")
    config["profiles"]["warm"]["linked"] = True
    normalized = validate_config(config)["profiles"]["warm"]
    assert normalized["morning"]["brightness"]["interpolation"] == "ease_in_out"
    assert normalized["evening"]["temperature"]["interpolation"] == "ease_in_out"
    assert (
        config["profiles"]["warm"]["evening"]["temperature"]["interpolation"]
        == "ease_in"
    )
