"""Native Home Assistant status and translations for the nightlight mode."""

from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.translation import async_get_translations
from test_entities import entity_id
from test_entities import platforms as platforms


async def test_nightlight_state_translations_and_reserved_scene_name(hass, platforms):
    area = ar.async_get(hass).async_create("Salon")
    platforms.add_room(area.id)
    await hass.async_block_till_done()
    status_id = entity_id(hass, "sensor", area.id, "status")
    engine = platforms.engines[area.id]
    engine.is_on = True
    engine.lighting_status = {"mode": "nightlight", "scene_id": None}
    platforms.notify()
    assert hass.states.get(status_id).state == "nightlight"
    assert hass.states.get(status_id).attributes["mode"] == "nightlight"
    for language, label in (("en", "Nightlight"), ("fr", "Veilleuse")):
        translations = await async_get_translations(hass, language, "entity", {"halo"})
        assert (
            translations["component.halo.entity.sensor.room_status.state.nightlight"]
            == label
        )
    platforms.config["rooms"][area.id]["scenes"][0]["name"] = "nightlight"
    engine.lighting_status = {"mode": "scene", "scene_id": "cinema"}
    platforms.notify()
    assert hass.states.get(status_id).state == "scene: nightlight"
    assert hass.states.get(status_id).attributes["scene_name"] == "nightlight"
    engine.available = False
    platforms.notify()
    assert hass.states.get(status_id).state == "unavailable"
