"""Verify native platforms, real states and dynamic room/scene lifecycle."""

from collections.abc import Callable
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import Platform
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import async_get_translations
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.halo.const import DOMAIN

PLATFORMS = [
    Platform.LIGHT,
    Platform.SWITCH,
    Platform.BUTTON,
    Platform.SCENE,
    Platform.SENSOR,
]


class RoomManagerStub:
    """Isolate platform integration from the lighting decision engine."""

    def __init__(self, hass: HomeAssistant, entry: MockConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.config = {"rooms": {}}
        self.engines = {}
        self.listeners: set[Callable[[], None]] = set()
        self.async_room_command = AsyncMock()
        self.async_set_mode = AsyncMock()
        self.async_resume = AsyncMock()
        self.async_activate_scene = AsyncMock()

    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self.listeners.add(listener)
        return lambda: self.listeners.discard(listener)

    def room_name(self, room_id: str) -> str:
        area = ar.async_get(self.hass).async_get_area(room_id)
        return area.name if area else room_id

    def notify(self) -> None:
        for listener in tuple(self.listeners):
            listener()

    def add_room(self, room_id: str) -> None:
        self.config["rooms"][room_id] = {
            "id": room_id,
            "lights": ["light.real_lamp"],
            "automation_enabled": False,
            "natural_enabled": True,
            "scenes": [{"id": "cinema", "name": "Cinéma personnel"}],
        }
        self.engines[room_id] = SimpleNamespace(
            available=True,
            is_on=False,
            status={},
            lighting_status={"mode": "off", "scene_id": None},
        )
        self.notify()


@pytest.fixture
async def platforms(hass: HomeAssistant):
    """Run all five real HA entity platforms with a controlled manager."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, title="Halo", data={})
    entry.add_to_hass(hass)
    manager = RoomManagerStub(hass, entry)

    async def async_setup(hass, entry):
        entry.runtime_data = manager
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        return True

    async def async_unload(hass, entry):
        return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    with (
        patch("custom_components.halo.async_setup_entry", async_setup),
        patch("custom_components.halo.async_unload_entry", async_unload),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield manager
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert not manager.listeners


def entity_id(hass: HomeAssistant, domain: str, room_id: str, key: str) -> str:
    """Look up stable identities independently of generated translated IDs."""
    result = er.async_get(hass).async_get_entity_id(domain, DOMAIN, f"{room_id}_{key}")
    assert result is not None
    return result


async def test_native_entities_device_and_real_state(
    hass: HomeAssistant, platforms: RoomManagerStub
) -> None:
    """A configured room creates one device; light state follows real feedback."""
    registry = er.async_get(hass)
    assert not er.async_entries_for_config_entry(registry, platforms.entry.entry_id)
    area = ar.async_get(hass).async_create("Living Room")
    platforms.add_room(area.id)
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(registry, platforms.entry.entry_id)
    assert len(entries) == 6
    assert len({entry.device_id for entry in entries}) == 1
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, area.id), platforms.entry.entry_id
    )
    assert device is not None
    assert device.area_id == area.id
    assert device.name == "Living Room"

    light = entity_id(hass, "light", area.id, "light")
    automation = entity_id(hass, "switch", area.id, "automation")
    natural = entity_id(hass, "switch", area.id, "natural")
    assert hass.states.get(light).state == "off"
    assert hass.states.get(light).attributes["supported_color_modes"] == ["onoff"]
    assert hass.states.get(automation).state == "off"
    assert hass.states.get(natural).state == "on"

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": light}, blocking=True
    )
    assert hass.states.get(light).state == "off"
    platforms.engines[area.id].is_on = True
    platforms.notify()
    assert hass.states.get(light).state == "on"
    platforms.engines[area.id].available = False
    platforms.notify()
    assert hass.states.get(light).state == "unavailable"
    assert hass.states.get(automation).state == "off"
    assert hass.states.get(natural).state == "on"


async def test_services_preserve_context_and_modes(
    hass: HomeAssistant, platforms: RoomManagerStub, hass_admin_user
) -> None:
    """Room commands, switches, resume and scenes reach the engine with context."""
    area = ar.async_get(hass).async_create("Bedroom")
    platforms.add_room(area.id)
    await hass.async_block_till_done()
    context = Context(user_id=hass_admin_user.id)
    calls = [
        (
            "light",
            "turn_on",
            "light",
            platforms.async_room_command,
            (area.id, "turn_on"),
        ),
        (
            "light",
            "turn_off",
            "light",
            platforms.async_room_command,
            (area.id, "turn_off"),
        ),
        (
            "switch",
            "turn_on",
            "automation",
            platforms.async_set_mode,
            (area.id, "automation", True),
        ),
        (
            "switch",
            "turn_off",
            "natural",
            platforms.async_set_mode,
            (area.id, "natural", False),
        ),
        ("button", "press", "resume", platforms.async_resume, (area.id,)),
        (
            "scene",
            "turn_on",
            "scene_cinema",
            platforms.async_activate_scene,
            (area.id, "cinema"),
        ),
    ]
    for domain, service, key, command, args in calls:
        await hass.services.async_call(
            domain,
            service,
            {"entity_id": entity_id(hass, domain, area.id, key)},
            blocking=True,
            context=context,
        )
        command.assert_awaited_with(*args, context=context)

    platforms.config["rooms"][area.id]["automation_enabled"] = True
    platforms.config["rooms"][area.id]["natural_enabled"] = False
    platforms.notify()
    assert (
        hass.states.get(entity_id(hass, "switch", area.id, "automation")).state == "on"
    )
    assert hass.states.get(entity_id(hass, "switch", area.id, "natural")).state == "off"


@pytest.mark.parametrize("disable_before_deletion", [False, True])
async def test_scenes_rename_delete_and_room_recreate(
    hass: HomeAssistant, platforms: RoomManagerStub, disable_before_deletion: bool
) -> None:
    """Editing scenes preserves identity; deletion removes states and registry rows."""
    area = ar.async_get(hass).async_create("Salon")
    platforms.add_room(area.id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    scene = entity_id(hass, "scene", area.id, "scene_cinema")
    assert (
        hass.states.get(scene).attributes["friendly_name"] == "Salon Cinéma personnel"
    )
    platforms.config["rooms"][area.id]["scenes"][0]["name"] = "Soirée cinéma"
    platforms.notify()
    await hass.async_block_till_done()
    assert entity_id(hass, "scene", area.id, "scene_cinema") == scene
    assert hass.states.get(scene).attributes["friendly_name"] == "Salon Soirée cinéma"

    if disable_before_deletion:
        registry.async_update_entity(scene, disabled_by=er.RegistryEntryDisabler.USER)
        await hass.async_block_till_done()

    platforms.config["rooms"][area.id]["scenes"] = []
    platforms.notify()
    await hass.async_block_till_done()
    assert registry.async_get(scene) is None
    assert hass.states.get(scene) is None

    platforms.config["rooms"].pop(area.id)
    platforms.engines.pop(area.id)
    platforms.notify()
    await hass.async_block_till_done()
    assert not er.async_entries_for_config_entry(registry, platforms.entry.entry_id)

    platforms.add_room(area.id)
    await hass.async_block_till_done()
    assert (
        len(er.async_entries_for_config_entry(registry, platforms.entry.entry_id)) == 6
    )
    assert hass.states.get(entity_id(hass, "light", area.id, "light")).state == "off"


async def test_rapid_room_configuration_changes(
    hass: HomeAssistant, platforms: RoomManagerStub
) -> None:
    """Coalesce concurrent edits without duplicate entities or stale scenes."""
    area = ar.async_get(hass).async_create("Office")
    platforms.add_room(area.id)
    platforms.config["rooms"].pop(area.id)
    platforms.notify()
    platforms.add_room(area.id)
    platforms.config["rooms"][area.id]["scenes"] = [
        {"id": "working", "name": "Travail"}
    ]
    platforms.notify()
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, platforms.entry.entry_id)
    assert len(entries) == 6
    assert (
        registry.async_get_entity_id("scene", DOMAIN, f"{area.id}_scene_cinema") is None
    )
    assert (
        hass.states.get(entity_id(hass, "scene", area.id, "scene_working")) is not None
    )


@pytest.mark.parametrize("language", ["en", "fr"])
async def test_entity_labels_translated_and_custom_names_preserved(
    hass: HomeAssistant, platforms: RoomManagerStub, language: str
) -> None:
    """HA localization supplies entity labels without translating user names."""
    # Reload the platforms after changing HA's language, as HA loads entity
    # translation resources when the platform is initialized.
    await hass.config_entries.async_unload(platforms.entry.entry_id)
    hass.config.language = language
    area = ar.async_get(hass).async_create("Ma pièce")
    platforms.add_room(area.id)
    assert await hass.config_entries.async_setup(platforms.entry.entry_id)
    await hass.async_block_till_done()
    light = hass.states.get(entity_id(hass, "light", area.id, "light"))
    expected = "Éclairage" if language == "fr" else "Lighting"
    assert light.attributes["friendly_name"] == f"Ma pièce {expected}"
    scene = hass.states.get(entity_id(hass, "scene", area.id, "scene_cinema"))
    assert scene.attributes["friendly_name"] == "Ma pièce Cinéma personnel"
    sensor = hass.states.get(entity_id(hass, "sensor", area.id, "status"))
    expected = "État" if language == "fr" else "Status"
    assert sensor.attributes["friendly_name"] == f"Ma pièce {expected}"
    translations = await async_get_translations(hass, language, "entity", {DOMAIN})
    prefix = "component.halo.entity.sensor.room_status.state."
    assert translations[prefix + "off"] == ("Éteint" if language == "fr" else "Off")
    assert translations[prefix + "manual"] == (
        "Manuel" if language == "fr" else "Manual"
    )
    assert translations[prefix + "natural"] == (
        "Lumière naturelle" if language == "fr" else "Natural lighting"
    )


async def test_room_status_updates_and_scene_rename(hass, platforms):
    """The read-only sensor follows notifications and keeps a stable identity."""
    area = ar.async_get(hass).async_create("Office")
    platforms.add_room(area.id)
    await hass.async_block_till_done()
    sensor_id = entity_id(hass, "sensor", area.id, "status")
    engine = platforms.engines[area.id]
    assert hass.states.get(sensor_id).state == "off"

    for mode in ("natural", "manual", "off"):
        engine.lighting_status = {"mode": mode, "scene_id": None}
        platforms.notify()
        state = hass.states.get(sensor_id)
        assert state.state == mode
        assert state.attributes["mode"] == mode
        assert state.attributes["scene_id"] is None
        assert state.attributes["scene_name"] is None

    engine.lighting_status = {"mode": "scene", "scene_id": "cinema"}
    platforms.notify()
    assert hass.states.get(sensor_id).state == "Cinéma personnel"
    assert hass.states.get(sensor_id).attributes["mode"] == "scene"
    assert hass.states.get(sensor_id).attributes["scene_id"] == "cinema"
    platforms.config["rooms"][area.id]["scenes"][0]["name"] = "Mon cinéma"
    platforms.notify()
    assert hass.states.get(sensor_id).state == "Mon cinéma"
    assert hass.states.get(sensor_id).attributes["scene_name"] == "Mon cinéma"

    ar.async_get(hass).async_update(area.id, name="Bureau")
    platforms.notify()
    assert entity_id(hass, "sensor", area.id, "status") == sensor_id
    engine.available = False
    engine.lighting_status = None
    platforms.notify()
    assert hass.states.get(sensor_id).state == "unavailable"
    assert hass.states.get(sensor_id).attributes.get("scene_id") is None
    engine.available = True
    engine.lighting_status = {"mode": "off", "scene_id": None}
    platforms.notify()
    assert hass.states.get(sensor_id).state == "off"
    platforms.async_room_command.assert_not_called()
    platforms.async_activate_scene.assert_not_called()

    await hass.config_entries.async_reload(platforms.entry.entry_id)
    await hass.async_block_till_done()
    assert entity_id(hass, "sensor", area.id, "status") == sensor_id
    assert hass.states.get(sensor_id).state == "off"


@pytest.mark.parametrize("name", ["off", "manual", "natural", "unknown", "unavailable"])
async def test_scene_names_cannot_impersonate_sensor_states(hass, platforms, name):
    """Reserved names remain scenes, never HA sentinels or translated modes."""
    area = ar.async_get(hass).async_create("Office")
    platforms.add_room(area.id)
    platforms.config["rooms"][area.id]["scenes"][0]["name"] = name
    platforms.engines[area.id].lighting_status = {"mode": "scene", "scene_id": "cinema"}
    await hass.async_block_till_done()
    sensor = hass.states.get(entity_id(hass, "sensor", area.id, "status"))
    assert sensor.state == f"scene: {name}"
    assert sensor.attributes["scene_name"] == name
    assert sensor.attributes["mode"] == "scene"
