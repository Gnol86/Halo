"""Exercise Halo through Home Assistant's actual config entry manager."""

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.halo.const import DOMAIN


async def test_user_setup(hass: HomeAssistant, hass_storage) -> None:
    """Setup requires confirmation and creates a loaded, unique entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not hass.config_entries.async_entries(DOMAIN)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.title == "Halo"
    assert entry.unique_id == DOMAIN
    assert entry.state is ConfigEntryState.LOADED
    config = entry.runtime_data.config
    assert config["rooms"] == {}
    assert config["sun_entity_id"] == "sun.sun"
    assert set(config["profiles"]) == {"default"}
    profile = config["profiles"]["default"]
    assert profile["id"] == "default"
    assert profile["name"] == "Natural light"
    assert profile["linked"] is True
    assert profile["morning"] == {
        "brightness": {
            "low_elevation": -20,
            "high_elevation": 20,
            "low": 40,
            "high": 100,
            "interpolation": "linear",
        },
        "temperature": {
            "low_elevation": 0,
            "high_elevation": 20,
            "low": 2000,
            "high": 5500,
            "interpolation": "linear",
        },
    }
    assert profile["evening"] == profile["morning"]
    # The preset is durable before any browser opens or a room is configured.
    assert hass_storage[f"{DOMAIN}.{entry.entry_id}"]["data"] == {
        "config": config,
        "revision": 0,
        "runtime": {},
    }


async def test_existing_instance(hass: HomeAssistant) -> None:
    """A configured home cannot acquire a second Halo instance."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={})
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_simultaneous_setup(hass: HomeAssistant) -> None:
    """Two open setup dialogs must not produce duplicate entries."""
    first = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    second = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert first["type"] is FlowResultType.FORM
    assert second["type"] is FlowResultType.ABORT
    assert second["reason"] == "already_in_progress"

    await hass.config_entries.flow.async_configure(first["flow_id"], {})
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
