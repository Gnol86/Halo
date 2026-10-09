"""Validate and preserve independent natural-curve modes across storage reloads."""

from copy import deepcopy

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.halo.const import DOMAIN
from custom_components.halo.manager import HaloError
from custom_components.halo.models import default_config, validate_config


def profile_config(*, legacy=False):
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
                    "ease_in"
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


@pytest.mark.parametrize("legacy", [True, False])
async def test_profile_modes_survive_load_save_and_reload(hass, hass_storage, legacy):
    config = profile_config(legacy=legacy)
    original = deepcopy(config)
    expected = validate_config(config)
    for period in ("morning", "evening"):
        for quantity in ("brightness", "temperature"):
            actual = expected["profiles"]["warm"][period][quantity]
            old = original["profiles"]["warm"][period][quantity]
            assert actual == {"interpolation": "linear"} | old
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
