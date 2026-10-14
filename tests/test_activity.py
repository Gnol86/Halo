"""Command attribution through native Activity, including its entity filters."""

import pytest
from homeassistant.components.logbook.models import LogbookConfig, async_event_to_row
from homeassistant.components.logbook.processor import EventProcessor
from homeassistant.const import EVENT_LOGBOOK_ENTRY, EVENT_STATE_CHANGED
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError
from test_engine import advance, enable, natural_profile, scene
from test_engine import room_engine as room_engine
from test_external_scene_engine import activate_condition
from test_external_scene_engine import linked_engine as linked_engine
from test_nightlight_engine import configured, depart

from custom_components.halo.const import DOMAIN, EVENT_LIGHT_COMMAND
from custom_components.halo.logbook import async_describe_events


@pytest.fixture
def activity(hass):
    """Listen to the real event bus and describe events with the native parser."""
    config = hass.data["logbook"] = LogbookConfig({})
    async_describe_events(
        hass,
        lambda domain, name, describe: config.external_events.update(
            {name: (domain, describe)}
        ),
    )
    events = []
    unsubscribers = [
        hass.bus.async_listen(event_type, events.append)
        for event_type in (
            EVENT_LIGHT_COMMAND,
            EVENT_LOGBOOK_ENTRY,
            EVENT_STATE_CHANGED,
        )
    ]
    yield events
    for unsubscribe in unsubscribers:
        unsubscribe()


def commands(events):
    return [event for event in events if event.event_type == EVENT_LIGHT_COMMAND]


def humanify(hass, events):
    processor = EventProcessor(hass, [EVENT_LIGHT_COMMAND, EVENT_LOGBOOK_ENTRY])
    return processor.humanify(iter(async_event_to_row(event) for event in events))


@pytest.mark.parametrize("language", ["en", "fr-BE"])
@pytest.mark.parametrize("origin", ["user", "automation", "unidentified"])
async def test_manual_pause_records_observed_values_and_actual_origin(
    hass, room_engine, activity, language, origin
):
    hass.config.language = language
    engine, _, _, _ = room_engine
    await enable(hass, engine)
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    activity.clear()
    old = hass.states.get("light.one")
    context = (
        Context(user_id="user")
        if origin == "user"
        else Context(parent_id="external")
        if origin == "automation"
        else Context()
    )
    hass.states.async_set(
        old.entity_id,
        "on",
        {**old.attributes, "friendly_name": "Ma lampe", "brightness": 42},
        context=context,
    )
    await hass.async_block_till_done()
    assert engine.status["pause_until"] is not None
    entries = [event for event in activity if event.event_type == EVENT_LOGBOOK_ENTRY]
    assert len(entries) == 1
    assert entries[0].context is context
    assert entries[0].data["entity_id"] == "light.one"
    message = entries[0].data["message"]
    assert "Ma lampe" in message
    assert "brightness: 128 → 42" in message
    if language == "fr-BE":
        assert "pause de la pièce" in message
        assert {
            "user": "commande utilisateur identifiée",
            "automation": "commande externe identifiée",
            "unidentified": "origine non identifiée",
        }[origin] in message
    else:
        assert "room paused" in message
        assert {
            "user": "identified user command",
            "automation": "identified external command",
            "unidentified": "unidentified origin",
        }[origin] in message
    assert any(row.get("message") == message for row in humanify(hass, activity))


@pytest.mark.parametrize(
    "language,label",
    [
        ("en", "presence detected"),
        ("fr", "présence détectée"),
        ("fr-BE", "présence détectée"),
        ("de", "presence detected"),
    ],
)
async def test_presence_attribution_and_live_context(
    hass, room_engine, activity, language, label
):
    hass.config.language = language
    engine, _, _, calls = room_engine
    await enable(hass, engine)
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    sent = commands(activity)
    assert len(sent) == len(calls) == 2
    assert all(event.data["name"] == f"Halo — {label}" for event in sent)
    assert all(event.data["reason"] == "presence" for event in sent)
    for event, call in zip(sent, calls, strict=True):
        assert event.context is call.context
        assert call.context.origin_event is event
    effects = [
        row
        for row in humanify(hass, activity)
        if row.get("state") == "on" and row["entity_id"].startswith("light.")
    ]
    assert len(effects) == 2
    assert all(row["context_name"] == f"Halo — {label}" for row in effects)
    assert all(row["context_domain"] == DOMAIN for row in effects)
    assert all("context_entity_id" not in row for row in effects)
    # A live entity stream does not subscribe to Halo's own event type.
    processor = EventProcessor(hass, [])
    processor.switch_to_live()
    feedback = next(
        event
        for event in activity
        if event.event_type == EVENT_STATE_CHANGED
        and event.data["entity_id"] == "light.one"
    )
    assert (
        processor.humanify(iter([async_event_to_row(feedback)]))[0]["context_name"]
        == f"Halo — {label}"
    )
    assert engine.status["pause_until"] is None


async def test_tv_scene_keeps_custom_name_and_does_not_repeat(
    hass, room_engine, activity
):
    hass.config.language = "fr"
    engine, _, room, calls = room_engine
    room["scenes"] = [scene(autonomous=True) | {"name": "TV du salon"}]
    await engine.async_reconfigure()
    await enable(hass, engine)
    hass.states.async_set("media_player.tv", "on")
    await hass.async_block_till_done()
    assert all(
        event.data["name"] == "Halo — scène « TV du salon »"
        for event in commands(activity)
    )
    assert commands(activity)
    count = len(commands(activity))
    await engine._async_wakeup("tick")
    await hass.async_block_till_done()
    assert len(commands(activity)) == count == len(calls)


async def test_nightlight_then_presence_restore_have_distinct_reasons(
    hass, freezer, room_engine, activity
):
    await configured(hass, room_engine)
    activity.clear()
    await depart(hass, freezer, room_engine)
    assert {event.data["reason"] for event in commands(activity)} == {"nightlight"}
    activity.clear()
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert {event.data["reason"] for event in commands(activity)} == {"presence"}


async def test_natural_adjustments_are_logged_only_when_dispatched(
    hass, room_engine, activity
):
    engine, manager, room, calls = room_engine
    manager.config["profiles"]["day"] = natural_profile()
    room["associations"] = [{"profile_id": "day", "lights": ["light.one"]}]
    await engine.async_reconfigure()
    await enable(hass, engine)
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    activity.clear()
    calls.clear()
    hass.states.async_set("sun.sun", "above_horizon", {"elevation": 7, "rising": True})
    await hass.async_block_till_done()
    sent = commands(activity)
    assert len(sent) == len(calls) == 1
    assert sent[0].data["reason"] == "natural"
    assert sent[0].data["action"] == "adjust"
    assert sent[0].data["entity_id"] == "light.one"
    assert any(
        event.event_type == EVENT_LOGBOOK_ENTRY
        and "natural light" in event.data["message"]
        for event in activity
    )
    activity.clear()
    await engine._async_wakeup("tick")
    await hass.async_block_till_done()
    assert not commands(activity)


async def test_mixed_base_and_natural_targets_do_not_share_a_false_reason(
    hass, room_engine, activity
):
    engine, manager, room, _ = room_engine
    manager.config["profiles"]["day"] = natural_profile()
    room["associations"] = [{"profile_id": "day", "lights": ["light.one"]}]
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    await engine.async_reconfigure()
    await enable(hass, engine)
    assert {
        event.data["entity_id"]: event.data["reason"] for event in commands(activity)
    } == {"light.one": "natural", "light.two": "base"}


@pytest.mark.parametrize("cause", ["absence", "bright"])
async def test_automatic_off_during_pause_keeps_actual_reason(
    hass, freezer, room_engine, activity, cause
):
    engine, _, room, _ = room_engine
    room["lux_off"] = True
    await enable(hass, engine)
    await engine.async_turn_on()
    await hass.async_block_till_done()
    activity.clear()
    if cause == "bright":
        hass.states.async_set("sensor.lux", "200")
    await advance(hass, freezer, 30 if cause == "bright" else 120)
    assert {event.data["reason"] for event in commands(activity)} == {cause}


async def test_manual_command_preserves_user_and_parent_and_skips_unavailable(
    hass, room_engine, activity
):
    engine, _, _, _ = room_engine
    hass.states.async_set("light.two", "unavailable")
    await hass.async_block_till_done()
    caller = Context(user_id="a" * 32)
    await engine.async_turn_on(caller)
    await hass.async_block_till_done()
    sent = commands(activity)
    assert len(sent) == 1
    assert sent[0].data["reason"] == "manual"
    assert sent[0].context.user_id == caller.user_id
    assert sent[0].context.parent_id == caller.id
    activity.clear()
    await engine.async_turn_off(caller)
    await hass.async_block_till_done()
    assert commands(activity)[0].data["action"] == "turn_off"
    assert commands(activity)[0].data["reason"] == "manual"


async def test_editor_preview_and_restore_have_explicit_reasons(
    hass, room_engine, activity
):
    engine, _, _, _ = room_engine
    token = await engine.async_begin_edit("owner")
    await engine.async_preview(token, {"light.one": {"state": "on"}})
    await hass.async_block_till_done()
    assert commands(activity)[0].data["reason"] == "preview"
    activity.clear()
    await engine.async_end_edit(token, False)
    await hass.async_block_till_done()
    assert {event.data["reason"] for event in commands(activity)} == {"restore"}


async def test_failed_service_records_a_request_not_a_success(
    hass, room_engine, activity
):
    engine, _, _, _ = room_engine

    async def fail(_call):
        raise HomeAssistantError("offline")

    hass.services.async_register("light", "turn_on", fail)
    await engine.async_turn_on()
    await hass.async_block_till_done()
    assert len(commands(activity)) == 2
    assert all("requested" in event.data["message"] for event in commands(activity))
    assert not any(row.get("state") == "on" for row in humanify(hass, activity))


async def test_native_scene_attributes_all_affected_lights(
    hass, linked_engine, activity
):
    engine, _, _, _, calls = linked_engine
    await activate_condition(hass, engine)
    sent = commands(activity)
    assert len(sent) == len(calls) == 1
    assert sent[0].data["entity_id"] == "scene.native"
    assert sent[0].data["reason"] == "scene"
    # The scene's known composition gets a request entry even if its provider
    # later loses context. Do not invent targets absent from its metadata.
    assert {
        event.data["entity_id"]
        for event in activity
        if event.event_type == EVENT_LOGBOOK_ENTRY
    } == {"scene.native", "light.one"}
    effects = [
        row
        for row in humanify(hass, activity)
        if row.get("state") == "on" and row["entity_id"].startswith("light.")
    ]
    assert {row["entity_id"] for row in effects} == {"light.one", "light.outside"}
    assert all(row["context_name"] == "Halo — scene “Movie night”" for row in effects)
