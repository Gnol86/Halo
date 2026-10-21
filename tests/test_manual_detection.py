"""Explicit intent detection uses HA service requests, never delayed lamp states."""

import asyncio
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.core import Context
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import label_registry as lr
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, MockUser

from custom_components.halo.manual import CommandOrigins, IdentifiedCommandListener


@pytest.fixture
async def detection(hass):
    MockUser(id="user", is_owner=True).add_to_hass(hass)
    room = {
        "lights": ["light.one"],
        "manual_control": {"mode": "identified", "duration": 1800, "inputs": []},
    }
    received = []
    origins = CommandOrigins()
    listener = IdentifiedCommandListener(hass, lambda: room, origins, received.append)

    async def no_change(call):
        """Accept commands without generating a state change or touching hardware."""

    for domain, services in {
        "light": ["turn_on", "turn_off", "toggle"],
        "homeassistant": ["turn_on", "turn_off", "toggle"],
        "scene": ["turn_on"],
        "input_button": ["press"],
    }.items():
        for service in services:
            hass.services.async_register(domain, service, no_change)
    hass.states.async_set("light.one", "on", {"brightness": 100})
    hass.states.async_set("light.other", "off")
    await hass.async_block_till_done()
    listener.start()
    yield room, received, origins, listener
    listener.stop()


async def request(hass, *, domain="light", service="turn_on", context=None, **target):
    await hass.services.async_call(
        domain,
        service,
        {},
        target=target or {"entity_id": "light.one"},
        context=context or Context(user_id="user"),
        blocking=True,
    )
    await hass.async_block_till_done()


@pytest.mark.parametrize("service", ["turn_on", "turn_off", "toggle"])
@pytest.mark.parametrize("domain", ["light", "homeassistant"])
async def test_authenticated_request_without_state_change(
    hass, detection, domain, service
):
    _, received, _, _ = detection
    before = hass.states.get("light.one")
    await request(hass, domain=domain, service=service)
    assert hass.states.get("light.one") is before
    assert len(received) == 1
    assert received[0]["source"] == "user"
    assert received[0]["entity_id"] == "light.one"
    assert received[0]["command"] == f"{domain}.{service}"
    assert isinstance(received[0]["at"], float)


@pytest.mark.parametrize(
    "context",
    [
        Context(),
        Context(parent_id="automation"),
        Context(user_id="user", parent_id="automation"),
    ],
)
async def test_no_attribution_or_automation_is_not_manual(hass, detection, context):
    _, received, _, listener = detection
    await request(hass, context=context)
    assert not received
    assert listener.diagnostics[-1]["result"] in {"rejected", "unknown"}


async def test_shared_own_lineage_overrides_user_attribution(hass, detection):
    _, received, origins, listener = detection
    own = Context(user_id="user")
    origins.add(own)
    await request(hass, context=own)
    await request(hass, context=Context(user_id="user", parent_id=own.id))
    assert not received
    assert listener.diagnostics[-1]["reason"] == "halo_context"


@pytest.mark.parametrize("kind", ["missing", "inactive", "read_only", "partial"])
async def test_user_must_exist_be_active_and_control_whole_room(hass, detection, kind):
    room, received, _, listener = detection
    room["lights"].append("light.other")
    if kind != "missing":
        user = MockUser(id="limited", is_active=kind != "inactive").add_to_hass(hass)
        user.mock_policy(
            {"entities": {"entity_ids": {"light.one": {"control": kind == "partial"}}}}
        )
    await request(hass, context=Context(user_id="limited"))
    assert not received
    assert listener.diagnostics[-1]["reason"] in {
        "control_denied",
        "unknown_or_inactive_user",
    }


async def test_forbidden_service_target_prevents_hold_even_if_room_allowed(
    hass, detection
):
    _, received, _, _ = detection
    user = MockUser(id="limited").add_to_hass(hass)
    user.mock_policy({"entities": {"entity_ids": {"light.one": {"control": True}}}})
    await request(
        hass, entity_id=["light.one", "light.other"], context=Context(user_id=user.id)
    )
    assert not received
    await request(hass, entity_id="all", context=Context(user_id=user.id))
    assert len(received) == 1


async def test_wrapper_and_scene_fanout_deduplicate_context(hass, detection):
    _, received, _, listener = detection
    context = Context(user_id="user")
    hass.states.async_set("scene.evening", "unknown", {"entity_id": ["light.one"]})
    await request(hass, domain="scene", entity_id="scene.evening", context=context)
    await request(hass, domain="homeassistant", context=context)
    await request(hass, context=context)
    await request(hass, service="turn_off", context=context)
    assert len(received) == 1
    assert received[0]["command"] == "scene.turn_on"
    assert listener.diagnostics[-1]["reason"] == "duplicate_context"
    await request(hass, service="turn_off")
    assert len(received) == 2


async def test_group_in_both_directions_and_nested_cycles(hass, detection):
    room, received, _, _ = detection
    hass.states.async_set(
        "group.inner", "on", {"entity_id": ["light.one", "group.outer"]}
    )
    hass.states.async_set("group.outer", "on", {"entity_id": ["group.inner"]})
    await request(hass, domain="homeassistant", entity_id="group.outer")
    assert len(received) == 1
    room["lights"] = ["light.group"]
    hass.states.async_set(
        "light.group", "on", {"entity_id": ["light.one", "light.other"]}
    )
    await request(hass, entity_id="light.one")
    assert len(received) == 2
    assert received[-1]["entity_id"] == "light.group"


@pytest.mark.parametrize("container", [set, frozenset])
async def test_hue_group_members_accept_sets(hass, detection, container):
    room, received, _, _ = detection
    room["lights"] = ["light.group"]
    hass.states.async_set("light.group", "on", {"entity_id": container(["light.one"])})
    await request(hass)
    assert len(received) == 1
    assert received[0]["entity_id"] == "light.group"


@pytest.mark.parametrize("selector", ["area_id", "device_id", "label_id"])
async def test_native_target_resolution(hass, detection, selector):
    room, received, _, _ = detection
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    area = ar.async_get(hass).async_create("Office")
    label = lr.async_get(hass).async_create("Desk")
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("test", "desk")}
    )
    dr.async_get(hass).async_update_device(device.id, area_id=area.id)
    lamp = er.async_get(hass).async_get_or_create(
        "light", "test", "desk", device_id=device.id
    )
    er.async_get(hass).async_update_entity(lamp.entity_id, labels={label.label_id})
    room["lights"] = [lamp.entity_id]
    values = {"area_id": area.id, "device_id": device.id, "label_id": label.label_id}
    await request(hass, **{selector: values[selector]})
    assert len(received) == 1
    assert received[0]["entity_id"] == lamp.entity_id


async def test_indirect_entities_in_other_domain_are_not_light_targets(hass, detection):
    room, received, _, _ = detection
    area = ar.async_get(hass).async_create("Office")
    selected = er.async_get(hass).async_get_or_create("scene", "test", "evening")
    er.async_get(hass).async_update_entity(selected.entity_id, area_id=area.id)
    hass.states.async_set(selected.entity_id, "unknown", {"entity_id": ["light.one"]})
    await request(hass, area_id=area.id)
    assert not received
    await request(hass, domain="scene", area_id=area.id)
    assert len(received) == 1


async def test_opaque_scene_and_unrelated_targets_are_not_guessed(hass, detection):
    _, received, _, _ = detection
    hass.states.async_set("scene.opaque", "unknown")
    await request(hass, domain="scene", entity_id="scene.opaque")
    await request(hass, entity_id="light.other")
    assert not received


async def test_all_and_comma_separated_target(hass, detection):
    _, received, _, _ = detection
    await request(hass, entity_id="light.other, light.one")
    await request(hass, entity_id="all")
    assert len(received) == 2


async def test_disabled_reconfiguration_and_stop_are_effective(hass, detection):
    room, received, _, listener = detection
    listener.start()
    room["manual_control"]["mode"] = "disabled"
    await request(hass)
    assert not received
    room["manual_control"]["mode"] = "identified"
    await request(hass)
    assert len(received) == 1
    listener.stop()
    listener.stop()
    await request(hass)
    assert len(received) == 1


async def test_stopped_restarted_listener_discards_inflight_auth(hass, detection):
    _, received, _, listener = detection
    entered = asyncio.Event()
    release = asyncio.Event()
    original = hass.auth.async_get_user

    async def delayed_user(user_id):
        entered.set()
        await release.wait()
        return await original(user_id)

    with patch.object(hass.auth, "async_get_user", side_effect=delayed_user):
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": "light.one"},
            context=Context(user_id="user"),
            blocking=True,
        )
        await entered.wait()
        listener.stop()
        listener.start()
        release.set()
        await hass.async_block_till_done()
    assert not received


async def test_disabled_while_auth_pending_does_not_emit(hass, detection):
    room, received, _, _ = detection
    original = hass.auth.async_get_user

    async def changed_mode(user_id):
        room["manual_control"]["mode"] = "disabled"
        return await original(user_id)

    with patch.object(hass.auth, "async_get_user", side_effect=changed_mode):
        await request(hass)
    assert not received


async def test_newer_engine_intent_invalidates_pending_auth(hass, detection):
    _, received, _, listener = detection
    original = hass.auth.async_get_user

    async def newer_intent(user_id):
        listener.invalidate_pending()
        return await original(user_id)

    with patch.object(hass.auth, "async_get_user", side_effect=newer_intent):
        await request(hass)
    assert not received
    # Invalidation keeps subscriptions alive for genuinely subsequent actions.
    await request(hass)
    assert len(received) == 1


async def test_late_auth_completion_cannot_replace_newer_intent(
    hass, detection, freezer
):
    _, received, _, listener = detection
    entered = asyncio.Event()
    release = asyncio.Event()
    original = hass.auth.async_get_user
    calls = 0

    async def first_delayed(user_id):
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            await release.wait()
        return await original(user_id)

    with patch.object(hass.auth, "async_get_user", side_effect=first_delayed):
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": "light.one"},
            context=Context(user_id="user"),
            blocking=True,
        )
        await entered.wait()
        freezer.move_to(dt_util.utcnow() + timedelta(seconds=1))
        await hass.services.async_call(
            "light",
            "turn_off",
            {"entity_id": "light.one"},
            context=Context(user_id="user"),
            blocking=True,
        )
        # The second listener task can finish while the first waits for auth.
        for _ in range(5):
            await asyncio.sleep(0)
        assert len(received) == 1
        release.set()
        await hass.async_block_till_done()
    assert len(received) == 1
    assert received[0]["command"] == "light.turn_off"
    assert listener.diagnostics[-1]["reason"] == "older_command"


async def test_old_lamp_context_never_starts_or_renews_pause(hass, detection):
    _, received, _, _ = detection
    context = Context(user_id="user")
    for brightness in (92, 66, 92, 128, 127):
        hass.states.async_set(
            "light.one", "on", {"brightness": brightness}, context=context
        )
        await hass.async_block_till_done()
    assert not received
    await request(hass, context=context)
    assert len(received) == 1
    hass.states.async_set("light.one", "off", context=context)
    await hass.async_block_till_done()
    assert len(received) == 1


@pytest.mark.parametrize("entity_id", ["event.remote", "input_button.remote"])
async def test_configured_input_accepts_new_timestamp_without_user(
    hass, detection, entity_id
):
    room, received, _, _ = detection
    room["manual_control"]["inputs"] = [entity_id]
    now = dt_util.utcnow()
    hass.states.async_set(
        entity_id, (now - timedelta(seconds=1)).isoformat(), {"event_type": "press"}
    )
    await hass.async_block_till_done()
    assert not received
    hass.states.async_set(entity_id, now.isoformat(), {"event_type": "press"})
    await hass.async_block_till_done()
    assert len(received) == 1
    assert received[0]["source"] == "input"
    assert received[0]["entity_id"] == entity_id
    hass.states.async_set(entity_id, now.isoformat(), {"event_type": "release"})
    await hass.async_block_till_done()
    assert len(received) == 1


@pytest.mark.parametrize("old", ["unknown", "unavailable"])
async def test_input_recovery_is_not_a_press(hass, detection, old):
    room, received, _, _ = detection
    room["manual_control"]["inputs"] = ["event.remote"]
    hass.states.async_set("event.remote", old)
    await hass.async_block_till_done()
    hass.states.async_set(
        "event.remote", dt_util.utcnow().isoformat(), {"event_type": "press"}
    )
    await hass.async_block_till_done()
    assert not received


async def test_authenticated_input_button_request_detects_first_press(hass, detection):
    room, received, _, _ = detection
    room["manual_control"]["inputs"] = ["input_button.remote"]
    hass.states.async_set("input_button.remote", "unknown")
    await hass.async_block_till_done()
    context = Context(user_id="user")
    await request(
        hass,
        domain="input_button",
        service="press",
        entity_id="input_button.remote",
        context=context,
    )
    hass.states.async_set(
        "input_button.remote", dt_util.utcnow().isoformat(), context=context
    )
    await hass.async_block_till_done()
    assert len(received) == 1
    assert received[0]["source"] == "input"


async def test_physical_input_reused_context_still_recognizes_new_presses(
    hass, detection
):
    room, received, _, _ = detection
    room["manual_control"]["inputs"] = ["event.remote"]
    now = dt_util.utcnow()
    context = Context()
    for seconds in (-2, -1, 0):
        hass.states.async_set(
            "event.remote",
            (now + timedelta(seconds=seconds)).isoformat(),
            context=context,
        )
        await hass.async_block_till_done()
    assert len(received) == 2


async def test_input_attributed_to_unauthorized_user_cannot_suspend_room(
    hass, detection
):
    room, received, _, _ = detection
    room["manual_control"]["inputs"] = ["input_button.remote"]
    user = MockUser(id="limited").add_to_hass(hass)
    user.mock_policy(
        {"entities": {"entity_ids": {"input_button.remote": {"control": True}}}}
    )
    now = dt_util.utcnow()
    hass.states.async_set(
        "input_button.remote", (now - timedelta(seconds=1)).isoformat()
    )
    await hass.async_block_till_done()
    hass.states.async_set(
        "input_button.remote", now.isoformat(), context=Context(user_id=user.id)
    )
    await hass.async_block_till_done()
    assert not received


@pytest.mark.parametrize("context_kind", ["own", "automation"])
async def test_input_own_or_automated_changes_are_rejected(
    hass, detection, context_kind
):
    room, received, origins, _ = detection
    room["manual_control"]["inputs"] = ["event.remote"]
    now = dt_util.utcnow()
    hass.states.async_set("event.remote", (now - timedelta(seconds=1)).isoformat())
    await hass.async_block_till_done()
    context = Context() if context_kind == "own" else Context(parent_id="automation")
    if context_kind == "own":
        origins.add(context)
    hass.states.async_set("event.remote", now.isoformat(), context=context)
    await hass.async_block_till_done()
    assert not received


async def test_input_stale_replayed_or_naive_timestamps_are_rejected(hass, detection):
    room, received, _, _ = detection
    room["manual_control"]["inputs"] = ["event.remote"]
    now = dt_util.utcnow()
    for timestamp in (
        now - timedelta(minutes=3),
        now - timedelta(minutes=2),
        now - timedelta(minutes=4),
        now.replace(tzinfo=None),
    ):
        hass.states.async_set("event.remote", timestamp.isoformat())
        await hass.async_block_till_done()
    assert not received


def test_origins_are_bounded_expire_and_clear():
    origins = CommandOrigins()
    first = Context()
    origins.add(first, now=0)
    assert origins.contains(Context(parent_id=first.id), now=599)
    assert not origins.contains(first, now=600)
    for index in range(300):
        origins.add(Context(id=f"origin-{index}"), now=700)
    assert not origins.contains(Context(id="origin-0"), now=701)
    assert origins.contains(Context(id="origin-299"), now=701)
    assert len(origins._contexts) == 256
    origins.clear()
    assert not origins.contains(Context(id="origin-299"), now=701)


async def test_diagnostic_and_dedup_storage_are_bounded(hass, detection):
    _, received, _, listener = detection
    for _ in range(270):
        await request(hass)
    assert len(received) == 270
    assert len(listener._seen) == 256
    assert len(listener.diagnostics) == 64
    copy = listener.diagnostics
    copy[0]["reason"] = "mutated"
    assert listener.diagnostics[0]["reason"] != "mutated"
