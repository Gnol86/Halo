"""Exercise Halo's lifecycle without touching actual lighting hardware."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.halo.const import DOMAIN


async def test_setup_unload_reload(hass: HomeAssistant) -> None:
    """The foundation can be loaded, unloaded and reloaded with lights intact."""
    hass.states.async_set("light.test_living_room", "on", {"brightness": 123})
    initial_light = hass.states.get("light.test_living_room")
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, title="Halo", data={})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED

    assert await hass.config_entries.async_setup(entry.entry_id)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("light.test_living_room") == initial_light

    assert await hass.config_entries.async_remove(entry.entry_id)
    assert not hass.config_entries.async_entries(DOMAIN)
