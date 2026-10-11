"""Recorder and Activity discovery for commands to other light integrations."""

from copy import deepcopy
from datetime import timedelta

import pytest
from homeassistant.components.logbook.helpers import async_determine_event_types
from homeassistant.components.logbook.processor import EventProcessor
from homeassistant.core import Context
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)
from test_manager import configured as configured_manager

from custom_components.halo.const import DOMAIN, EVENT_LIGHT_COMMAND


@pytest.fixture(autouse=True)
def enable_halo(recorder_mock, enable_custom_integrations):
    """Prepare the recorder database before creating the HA test instance."""


@pytest.mark.parametrize("logbook_first,keep_context", [(True, True), (False, False)])
async def test_recorded_entity_activity_with_real_platform_discovery(
    recorder_mock, hass, logbook_first, keep_context
):
    hass.config.language = "fr"
    if logbook_first:
        assert await async_setup_component(hass, "logbook", {})
    entry, area, manager = await configured_manager(hass)
    if not logbook_first:
        assert await async_setup_component(hass, "logbook", {})
    await hass.async_block_till_done()
    assert hass.data["logbook"].external_events[EVENT_LIGHT_COMMAND][0] == DOMAIN

    async def turn_on(call):
        attrs = {
            "supported_color_modes": ["brightness"],
            "brightness": call.data.get("brightness", 100),
        }
        hass.states.async_set(
            "light.bulb",
            "on",
            attrs,
            context=call.context if keep_context else Context(),
        )

    hass.services.async_register("light", "turn_on", turn_on)
    await manager.engines[area.id].async_turn_on()
    await async_wait_recording_done(hass)
    event_types = async_determine_event_types(hass, ["light.bulb"], None)
    assert EVENT_LIGHT_COMMAND not in event_types
    processor = EventProcessor(hass, event_types, entity_ids=["light.bulb"])
    now = dt_util.utcnow()
    rows = await recorder_mock.async_add_executor_job(
        processor.get_events, now - timedelta(hours=1), now + timedelta(seconds=1)
    )
    notes = [row for row in rows if row.get("message", "").startswith("Halo :")]
    assert len(notes) == 1
    assert "allumage demandé" in notes[0]["message"]
    effects = [row for row in rows if row.get("state") == "on"]
    assert len(effects) == 1
    if keep_context:
        assert effects[0]["context_name"] == "Halo — commande manuelle dans Halo"
        assert effects[0]["context_domain"] == DOMAIN
    else:
        assert "context_name" not in effects[0]
    # Attribute-only changes are absent from ordinary light activity. The
    # request must still be visible through the native entity-filtered query.
    config = deepcopy(manager.config)
    config["rooms"][area.id]["base"] = {
        "light.bulb": {"state": "on", "brightness": 200}
    }
    await manager.async_save_config(config, manager.revision)
    await manager.engines[area.id].async_turn_on()
    await async_wait_recording_done(hass)
    processor = EventProcessor(hass, event_types, entity_ids=["light.bulb"])
    rows = await recorder_mock.async_add_executor_job(
        processor.get_events,
        now - timedelta(hours=1),
        dt_util.utcnow() + timedelta(seconds=1),
    )
    assert any("ajustement demandé" in row.get("message", "") for row in rows)
    assert await hass.config_entries.async_unload(entry.entry_id)
