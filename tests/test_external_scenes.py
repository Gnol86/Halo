"""Native scene metadata, persistence, authorization and recursion boundaries."""

import asyncio
from copy import deepcopy
from unittest.mock import Mock, patch

import pytest
from homeassistant.core import Context
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import entity_registry as er
from test_manager import configured

from custom_components.halo.external_scenes import (
    composition,
    feedback_lights,
    inspect_scene,
    scene_problem,
)
from custom_components.halo.manager import HaloError
from custom_components.halo.models import validate_scene


def linked(entity_id="scene.native"):
    return {
        "id": "linked",
        "type": "home_assistant",
        "name": "My native scene",
        "scene_entity_id": entity_id,
        "conditions": None,
        "can_turn_on": False,
    }


def test_legacy_normalization_and_independent_link():
    old = {"id": "old", "name": "Old", "lights": {"light.one": {"state": "on"}}}
    assert validate_scene(old, ["light.one"])["type"] == "halo"
    assert "type" not in old
    assert validate_scene(linked(), []) == linked()


@pytest.mark.parametrize(
    "invalid",
    [
        {"type": "other"},
        {"type": None},
        {"scene_entity_id": "light.one"},
        {"scene_entity_id": "scene."},
        {"scene_entity_id": None},
        {"lights": {}},
        {"type": "halo"},
    ],
)
def test_invalid_scene_variants_rejected(invalid):
    with pytest.raises(ValueError):
        validate_scene(linked() | invalid, ["light.one"])


async def test_metadata_expands_known_groups_without_side_effects(hass):
    hass.states.async_set("light.pair", "on", {"entity_id": {"light.a", "light.b"}})
    hass.states.async_set("light.outside", "off")
    hass.states.async_set(
        "scene.native",
        "unknown",
        {
            "friendly_name": "Native",
            "entity_id": ["light.a", "light.outside", "switch.tv"],
        },
    )
    result = inspect_scene(hass, ["light.pair"], "scene.native")
    assert result == {
        "entity_id": "scene.native",
        "name": "Native",
        "available": True,
        "complete": True,
        "lights": ["light.a", "light.outside"],
        "outside_lights": ["light.outside"],
        "missing_lights": ["light.b"],
        "other_entities": ["switch.tv"],
        "blocked": False,
    }
    assert feedback_lights(hass, ["light.pair", "light.unrelated"], "scene.native") == {
        "light.pair"
    }
    assert hass.states.get("scene.native").state == "unknown"
    assert scene_problem(hass, linked()) is None


async def test_opaque_or_partial_composition_never_claims_room_lights_missing(hass):
    hass.states.async_set("scene.native", "unknown")
    result = inspect_scene(hass, ["light.one"], "scene.native")
    assert not result["complete"]
    assert result["missing_lights"] == result["outside_lights"] == []
    assert feedback_lights(hass, ["light.one"], "scene.native") == {"light.one"}
    hass.states.async_set("light.hue", "on", {"is_hue_group": True})
    hass.states.async_set(
        "scene.native", "unknown", {"entity_id": ["light.hue", "light.outside"]}
    )
    result = inspect_scene(hass, ["light.one"], "scene.native")
    assert not result["complete"]
    assert not result["missing_lights"]
    assert result["lights"] == result["outside_lights"] == ["light.outside"]


async def test_opaque_room_group_does_not_create_false_scope_warnings(hass):
    hass.states.async_set("light.hue_opaque", "on", {"is_hue_group": True})
    hass.states.async_set("scene.native", "unknown", {"entity_id": ["light.member"]})
    result = inspect_scene(hass, ["light.hue_opaque"], "scene.native")
    assert not result["complete"]
    assert result["outside_lights"] == result["missing_lights"] == []


async def test_missing_and_cyclic_group_metadata_is_bounded(hass):
    hass.states.async_set("group.a", "on", {"entity_id": ["group.b"]})
    hass.states.async_set("group.b", "on", {"entity_id": ["group.a", 42, "bad"]})
    result = composition(hass, ["group.a"])
    assert not result.complete
    assert result.nodes == {"group.a", "group.b"}
    assert scene_problem(hass, linked()) == "external_scene_unavailable"
    hass.states.async_set("scene.native", "unavailable")
    assert scene_problem(hass, linked()) == "external_scene_unavailable"


async def test_halo_source_and_indirect_halo_targets_blocked(hass):
    entity = er.async_get(hass).async_get_or_create("switch", "halo", "mode")
    hass.states.async_set("group.nested", "on", {"entity_id": [entity.entity_id]})
    hass.states.async_set("scene.native", "unknown", {"entity_id": ["group.nested"]})
    assert inspect_scene(hass, [], "scene.native")["blocked"]
    assert scene_problem(hass, linked()) == "external_scene_recursive"
    own = er.async_get(hass).async_get_or_create("scene", "halo", "own")
    assert inspect_scene(hass, [], own.entity_id)["blocked"]


async def test_link_save_reload_no_commands_and_source_disappearance(hass):
    entry, area, manager = await configured(hass)
    hass.states.async_set("scene.native", "unknown", {"entity_id": ["light.bulb"]})
    config = deepcopy(manager.config)
    config["rooms"][area.id]["scenes"] = [linked()]
    with patch("homeassistant.core.ServiceRegistry.async_call") as calls:
        await manager.async_save_config(config, manager.revision)
        calls.assert_not_called()
    await hass.async_block_till_done()
    entity_id = er.async_get(hass).async_get_entity_id(
        "scene", "halo", f"{area.id}_scene_linked"
    )
    assert hass.states.get(entity_id).state != "unavailable"
    hass.states.async_remove("scene.native")
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "unavailable"
    # Preserve a missing reference while editing other settings.
    config["rooms"][area.id]["scenes"][0]["name"] = "Kept"
    await manager.async_save_config(config, manager.revision)
    assert await hass.config_entries.async_reload(entry.entry_id)
    manager = entry.runtime_data
    assert manager.config["rooms"][area.id]["scenes"][0]["name"] == "Kept"
    assert "lights" not in manager.config["rooms"][area.id]["scenes"][0]
    await hass.config_entries.async_unload(entry.entry_id)


async def test_unknown_source_rejected_and_link_cannot_use_capture(hass):
    entry, area, manager = await configured(hass)
    config = deepcopy(manager.config)
    config["rooms"][area.id]["scenes"] = [linked()]
    with pytest.raises(HaloError, match="existing Home Assistant scene"):
        await manager.async_save_config(config, manager.revision)
    token = await manager.async_begin_edit(area.id, "owner")
    with pytest.raises(HaloError, match="live editor"):
        await manager.async_end_edit(
            area.id, token, "owner", True, linked(), manager.revision, capture=True
        )
    await manager.async_end_edit(area.id, token, "owner", False)
    await hass.config_entries.async_unload(entry.entry_id)


async def test_source_and_outside_target_permissions_before_manual_pause(
    hass, hass_admin_user
):
    entry, area, manager = await configured(hass)
    hass.states.async_set(
        "scene.native", "unknown", {"entity_id": ["light.bulb", "light.outside"]}
    )
    config = deepcopy(manager.config)
    config["rooms"][area.id]["scenes"] = [linked()]
    await manager.async_save_config(config, manager.revision)
    user = Mock(id=hass_admin_user.id)
    for denied in ("scene.native", "light.outside"):
        user.permissions.check_entity.side_effect = lambda eid, policy, denied=denied: (
            eid != denied
        )
        with patch.object(hass.auth, "async_get_user", return_value=user):
            with pytest.raises(Unauthorized):
                await manager.async_activate_scene(
                    area.id, "linked", Context(user_id=user.id)
                )
        assert not manager.runtime_state[area.id].get("pause_until")
    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("command", ["turn_on", "turn_off", "mode", "resume", "scene"])
async def test_recursion_guard_rejects_before_waiting_for_any_lock(hass, command):
    entry, area, manager = await configured(hass)
    context = Context()
    await manager.engines[area.id]._lock.acquire()
    try:
        with manager.external_scene_context(context):
            with pytest.raises(HaloError, match="cannot control Halo"):
                if command == "mode":
                    await manager.async_set_mode(area.id, "automation", True, Context())
                elif command == "resume":
                    await manager.async_resume(area.id, Context())
                elif command == "scene":
                    await manager.async_activate_scene(area.id, "linked", Context())
                else:
                    await manager.async_room_command(area.id, command, Context())
    finally:
        manager.engines[area.id]._lock.release()
    assert not manager._external_contexts
    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("during_call", [True, False])
async def test_inherited_recursion_guard_expires_with_native_call(hass, during_call):
    """HA feedback can schedule children whose context outlives scene.turn_on."""
    entry, area, manager = await configured(hass)
    ready = asyncio.Event()

    async def later_action():
        await ready.wait()
        await manager.async_set_mode(area.id, "automation", False, Context())

    with manager.external_scene_context(Context()):
        pending = hass.async_create_task(later_action())
        if during_call:
            ready.set()
            with pytest.raises(HaloError, match="cannot control Halo"):
                await pending
    if not during_call:
        ready.set()
        await pending
    assert not manager._external_contexts
    await hass.config_entries.async_unload(entry.entry_id)


async def test_shared_group_branches_are_expanded_once(hass):
    """Repeated group references cannot multiply metadata work exponentially."""
    for index in range(12):
        hass.states.async_set(
            f"group.level_{index}",
            "on",
            {"entity_id": [f"group.level_{index + 1}"] * 2},
        )
    hass.states.async_set("group.level_12", "on", {"entity_id": ["light.bulb"]})
    read = hass.states.get
    calls = 0

    def bounded_read(entity_id):
        nonlocal calls
        calls += 1
        assert calls <= 20, "Repeated metadata traversal"
        return read(entity_id)

    with patch.object(type(hass.states), "get", side_effect=bounded_read):
        result = composition(hass, ["group.level_0"])
    assert result.complete
    assert result.lights == {"light.bulb"}


async def test_deep_group_metadata_does_not_exhaust_python_stack(hass):
    """Metadata depth is independent of Python's call-stack limit."""
    for index in range(1100):
        hass.states.async_set(
            f"group.level_{index}",
            "on",
            {"entity_id": [f"group.level_{index + 1}"]},
        )
    hass.states.async_set("group.level_1100", "on", {"entity_id": ["light.bulb"]})
    result = composition(hass, ["group.level_0"])
    assert result.complete
    assert result.lights == {"light.bulb"}
