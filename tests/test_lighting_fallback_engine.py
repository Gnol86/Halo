"""Lighting permission from local schedules or solar elevation, without lux."""

import asyncio
from datetime import timedelta

import pytest
from homeassistant.core import Context
from homeassistant.util import dt as dt_util
from test_engine import advance, enable, natural_profile, scene
from test_engine import room_engine as room_engine

from custom_components.halo.engine import HaloRoomEngine


async def configure(
    hass,
    freezer,
    room_engine,
    *,
    mode="time",
    now="2026-10-10T17:59:41+00:00",
    present=True,
    timezone="UTC",
    **settings,
):
    engine, manager, room, calls = room_engine
    await hass.config.async_set_time_zone(timezone)
    freezer.move_to(now)
    room.update(
        lux_entity_id=None,
        absence_delay=0,
        lux_off_delay=20,
        base={
            entity: {"state": "on", "brightness_pct": 80} for entity in room["lights"]
        },
        lighting_fallback={
            "mode": mode,
            "start": "18:00",
            "end": "08:00",
            "linked": True,
            "morning_below": 0,
            "evening_below": 0,
            "turn_off": False,
            **settings,
        },
    )
    manager.config["transitions"] = {
        "turn_on": 1,
        "lux_on": 10,
        "turn_off": 2,
        "natural": 60,
        "scene": 8,
    }
    hass.states.async_set("binary_sensor.presence", "on" if present else "off")
    await hass.async_block_till_done()
    await engine.async_reconfigure()
    await enable(hass, engine)
    calls.clear()


async def sun(hass, elevation, **attributes):
    hass.states.async_set(
        "sun.sun", "above_horizon", {"elevation": elevation, **attributes}
    )
    await hass.async_block_till_done()


async def test_schedule_opens_at_exact_local_minute_without_new_presence(
    hass, freezer, room_engine
):
    engine, _, _, calls = room_engine
    await configure(
        hass,
        freezer,
        room_engine,
        now="2026-10-10T15:59:41+00:00",
        timezone="Europe/Brussels",
    )
    assert not engine.is_on
    assert engine.status["reason"] == "outside_schedule"
    assert engine.status["lighting_allowed"] is False
    assert engine.status["lighting_source"] == "time"
    assert engine.status["dark"] is None and engine.status["lux"] is None
    await advance(hass, freezer, 18)
    assert not calls
    await advance(hass, freezer, 1)
    assert engine.is_on
    assert len(calls) == 2
    assert all(call.data["transition"] == 10 for call in calls)
    calls.clear()
    await advance(hass, freezer, 60)
    hass.states.async_set("binary_sensor.presence", "on", {"battery": 90})
    await hass.async_block_till_done()
    assert not calls


@pytest.mark.parametrize(
    ("local_time", "allowed"),
    [
        ("07:59:59", True),
        ("08:00:00", False),
        ("17:59:59", False),
        ("18:00:00", True),
        ("00:00:00", True),
    ],
)
async def test_overnight_schedule_inclusive_start_exclusive_end(
    hass, freezer, room_engine, local_time, allowed
):
    engine, _, _, _ = room_engine
    await configure(hass, freezer, room_engine, now=f"2026-10-10T{local_time}+00:00")
    assert engine.is_on is allowed
    assert engine.status["lighting_allowed"] is allowed


@pytest.mark.parametrize(
    ("utc_before", "start", "end", "allowed_before", "allowed_after"),
    [
        ("2026-03-29T00:59:59+00:00", "02:30", "04:00", False, True),
        ("2026-10-25T00:59:59+00:00", "02:30", "03:30", True, False),
    ],
)
async def test_schedule_follows_local_clock_across_dst_jump(
    hass, freezer, room_engine, utc_before, start, end, allowed_before, allowed_after
):
    engine, _, _, _ = room_engine
    await configure(
        hass,
        freezer,
        room_engine,
        now=utc_before,
        timezone="Europe/Brussels",
        start=start,
        end=end,
        turn_off=True,
    )
    assert engine.is_on is allowed_before
    await advance(hass, freezer, 1)
    assert engine.is_on is allowed_after
    assert engine.status["lighting_allowed"] is allowed_after


@pytest.mark.parametrize("turn_off", [False, True])
async def test_schedule_closing_only_switches_off_when_requested(
    hass, freezer, room_engine, turn_off
):
    engine, _, _, calls = room_engine
    await configure(
        hass, freezer, room_engine, now="2026-10-10T07:59:59+00:00", turn_off=turn_off
    )
    await advance(hass, freezer, 1)
    assert engine.is_on is not turn_off
    if turn_off:
        assert len(calls) == 2
        assert all(
            call.service == "turn_off" and call.data["transition"] == 2
            for call in calls
        )
        assert engine.status["reason"] == "outside_schedule"
    else:
        assert not calls


async def test_presence_inside_window_uses_turn_on_and_quick_return_cannot_escape_it(
    hass, freezer, room_engine
):
    engine, _, _, calls = room_engine
    await configure(
        hass, freezer, room_engine, present=False, now="2026-10-10T07:59:50+00:00"
    )
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert all(call.data["transition"] == 1 for call in calls)
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    assert not engine.is_on
    calls.clear()
    await advance(hass, freezer, 10)
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert not calls
    assert not engine.is_on
    assert engine.status["reason"] == "outside_schedule"


@pytest.mark.parametrize("sensor_state", ["50", "200", "unknown", "unavailable"])
async def test_configured_lux_always_takes_precedence_even_when_unavailable(
    hass, freezer, room_engine, sensor_state
):
    engine, _, room, _ = room_engine
    await configure(hass, freezer, room_engine, present=False)
    room["lux_entity_id"] = "sensor.lux"
    hass.states.async_set("sensor.lux", sensor_state)
    await engine.async_reconfigure()
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert engine.status["lighting_source"] == "lux"
    assert engine.status["lighting_allowed"] == {"50": True, "200": False}.get(
        sensor_state
    )
    assert engine.is_on is (sensor_state == "50")


async def test_always_keeps_legacy_permission_without_claiming_a_lux_measurement(
    hass, freezer, room_engine
):
    engine, _, room, _ = room_engine
    await configure(hass, freezer, room_engine, mode="always")
    assert engine.is_on and engine.status["lighting_allowed"] is True
    assert engine.status["dark"] is None
    room.pop("lighting_fallback")
    await engine.async_reconfigure()
    assert engine.status["lighting_source"] == "always"
    assert engine.status["reason"] == "base"


async def test_solar_strict_threshold_opens_once_and_closes_after_confirmation(
    hass, freezer, room_engine
):
    engine, _, _, calls = room_engine
    await configure(hass, freezer, room_engine, mode="sun", turn_off=True)
    await sun(hass, 0)
    assert not calls and not engine.is_on
    await sun(hass, -0.1)
    assert engine.is_on and len(calls) == 2
    assert all(call.data["transition"] == 10 for call in calls)
    calls.clear()
    await sun(hass, -0.2)
    assert not calls
    await sun(hass, 0)
    deadline = engine.status["lighting_off_deadline"]
    assert deadline and engine.status["lux_off_deadline"] is None
    await advance(hass, freezer, 10)
    await sun(hass, 1)
    assert engine.status["lighting_off_deadline"] == deadline
    await advance(hass, freezer, 9)
    assert engine.is_on and not calls
    await advance(hass, freezer, 1)
    assert not engine.is_on
    assert all(
        call.service == "turn_off" and call.data["transition"] == 2 for call in calls
    )
    assert engine.status["reason"] == "sun_above_threshold"


async def test_solar_confirmation_cancels_on_permission_or_unknown_input(
    hass, freezer, room_engine
):
    engine, _, _, calls = room_engine
    await configure(hass, freezer, room_engine, mode="sun", turn_off=True)
    await sun(hass, -1)
    await sun(hass, 1)
    await advance(hass, freezer, 10)
    await sun(hass, -1)
    assert engine.status["lighting_off_deadline"] is None
    await sun(hass, 1)
    await advance(hass, freezer, 10)
    hass.states.async_set("sun.sun", "unavailable")
    await hass.async_block_till_done()
    calls.clear()
    await advance(hass, freezer, 30)
    assert not calls and engine.is_on
    assert engine.status["lighting_allowed"] is None
    assert engine.status["lighting_off_deadline"] is None


@pytest.mark.parametrize("rising", [None, "true", 1, False, True])
async def test_separate_solar_thresholds_require_a_boolean_direction(
    hass, freezer, room_engine, rising
):
    engine, _, _, calls = room_engine
    await configure(
        hass,
        freezer,
        room_engine,
        mode="sun",
        linked=False,
        morning_below=-4,
        evening_below=2,
    )
    await sun(hass, 0, rising=rising)
    expected = True if rising is False else False if rising is True else None
    assert engine.status["lighting_allowed"] is expected
    assert bool(calls) is (rising is False)
    assert engine.is_on is (rising is False)


@pytest.mark.parametrize(
    "invalid",
    [
        None,
        "unknown",
        "nan",
        "inf",
        False,
        True,
        -91,
        91,
        pytest.param(10**400, id="overflow"),
    ],
)
async def test_invalid_solar_elevation_never_becomes_dark(
    hass, freezer, room_engine, invalid
):
    engine, _, _, calls = room_engine
    await configure(hass, freezer, room_engine, mode="sun")
    await sun(hass, invalid)
    assert engine.status["lighting_allowed"] is None
    assert engine.status["reason"] == "unavailable"
    assert not calls


@pytest.mark.parametrize("mode", ["time", "sun"])
async def test_nightlight_follows_permission_even_without_normal_off(
    hass, freezer, room_engine, mode
):
    engine, _, room, calls = room_engine
    await configure(hass, freezer, room_engine, mode=mode, present=False)
    room["nightlight"] = {
        "enabled": True,
        "lights": {"light.one": {"state": "on", "brightness_pct": 5}},
    }
    await engine.async_reconfigure()
    if mode == "time":
        await advance(hass, freezer, 19)
    else:
        await sun(hass, -1)
    assert engine.lighting_status["mode"] == "nightlight"
    assert hass.states.get("light.one").attributes["brightness"] == 13
    assert hass.states.get("light.two").state == "off"
    assert len(calls) == 1 and calls[0].data["transition"] == 10
    calls.clear()
    if mode == "time":
        await advance(hass, freezer, 14 * 3600)
    else:
        await sun(hass, 0)
        assert engine.is_on
        await advance(hass, freezer, 20)
    assert not engine.is_on
    assert len(calls) == 1 and calls[0].data["transition"] == 2


async def test_nightlight_returns_full_natural_ambience_on_presence(
    hass, freezer, room_engine
):
    engine, manager, room, calls = room_engine
    await configure(hass, freezer, room_engine, mode="sun", present=False)
    manager.config["profiles"]["day"] = natural_profile()
    room["associations"] = [{"profile_id": "day", "lights": room["lights"]}]
    room["nightlight"] = {
        "enabled": True,
        "lights": {"light.one": {"state": "on", "brightness_pct": 5}},
    }
    await engine.async_reconfigure()
    await sun(hass, -1)
    calls.clear()
    await sun(hass, -2)
    assert not calls
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    assert len(calls) == 2 and all(call.data["transition"] == 1 for call in calls)
    assert all(call.data["brightness_pct"] != 5 for call in calls)
    assert engine.lighting_status["mode"] == "natural"


@pytest.mark.parametrize("autonomous", [False, True])
async def test_autonomous_scenes_keep_priority_and_regular_scenes_wait(
    hass, freezer, room_engine, autonomous
):
    engine, _, room, calls = room_engine
    await configure(hass, freezer, room_engine)
    room["scenes"] = [scene(autonomous=autonomous)]
    hass.states.async_set("media_player.tv", "on")
    await engine.async_reconfigure()
    assert engine.is_on is autonomous
    calls.clear()
    await advance(hass, freezer, 19)
    if autonomous:
        assert not calls
    else:
        assert calls and calls[0].data["transition"] == 10
    assert engine.status["reason"] == "scene"


async def test_manual_pause_disabled_and_editor_remain_authoritative(
    hass, freezer, room_engine
):
    engine, _, room, calls = room_engine
    await configure(hass, freezer, room_engine, mode="sun", turn_off=True)
    room["allow_off_during_pause"] = False
    await engine.async_turn_on(Context(user_id="user"))
    assert engine.is_on
    calls.clear()
    await sun(hass, -1)
    await sun(hass, 1)
    await advance(hass, freezer, 30)
    assert not calls and engine.status["reason"] == "manual_pause"
    await engine.async_set_mode("automation", False)
    calls.clear()
    await sun(hass, -1)
    assert not calls and engine.status["reason"] == "disabled"
    await engine.async_resume()
    token = await engine.async_begin_edit("user")
    calls.clear()
    await sun(hass, 1)
    await advance(hass, freezer, 30)
    assert not calls and engine.status["reason"] == "editing"
    await engine.async_end_edit(token, save=False)


async def test_restart_recomputes_permission_and_restores_pause(
    hass, freezer, room_engine
):
    engine, manager, _, calls = room_engine
    await configure(hass, freezer, room_engine, mode="sun")
    await engine.async_turn_off(Context(user_id="user"))
    await sun(hass, -1)
    pause = engine.status["pause_until"]
    await engine.async_stop()
    restored = HaloRoomEngine(hass, manager, "living")
    calls.clear()
    try:
        await restored.async_start()
        assert restored.status["lighting_allowed"] is True
        assert restored.status["pause_until"] == pause
        assert not calls
    finally:
        await restored.async_stop()


async def test_schedule_closing_interrupts_pending_automatic_on_before_lock(
    hass, freezer, room_engine
):
    engine, _, _, calls = room_engine
    await configure(
        hass,
        freezer,
        room_engine,
        now="2026-10-10T07:59:59+00:00",
        present=False,
        turn_off=True,
    )
    entered, finish = asyncio.Event(), asyncio.Event()

    async def slow_on(call):
        calls.append(call)
        entered.set()
        await finish.wait()
        old = hass.states.get(call.data["entity_id"])
        hass.states.async_set(
            old.entity_id, "on", dict(old.attributes), context=call.context
        )

    hass.services.async_register("light", "turn_on", slow_on)
    hass.states.async_set("binary_sensor.presence", "on")
    await entered.wait()
    freezer.move_to(dt_util.utcnow() + timedelta(seconds=1))
    closing = hass.async_create_task(engine._async_lighting_tick(dt_util.now()))
    await asyncio.sleep(0)
    finish.set()
    await closing
    await hass.async_block_till_done()
    assert [call.data["entity_id"] for call in calls if call.service == "turn_on"] == [
        "light.one"
    ]
    assert not engine.is_on


async def test_fallback_change_does_not_interrupt_newer_manual_command(
    hass, freezer, room_engine
):
    engine, _, room, calls = room_engine
    await configure(hass, freezer, room_engine, mode="sun", turn_off=True)
    room["allow_off_during_pause"] = False
    entered, finish = asyncio.Event(), asyncio.Event()

    async def slow_on(call):
        calls.append(call)
        if len(calls) == 1:
            entered.set()
            await finish.wait()
        old = hass.states.get(call.data["entity_id"])
        hass.states.async_set(
            old.entity_id, "on", dict(old.attributes), context=call.context
        )

    hass.services.async_register("light", "turn_on", slow_on)
    manual = hass.async_create_task(engine.async_turn_on(Context(user_id="user")))
    await entered.wait()
    hass.states.async_set("sun.sun", "above_horizon", {"elevation": -1})
    await asyncio.sleep(0)
    finish.set()
    await manual
    await hass.async_block_till_done()
    assert {call.data["entity_id"] for call in calls} == {"light.one", "light.two"}
    assert engine.status["reason"] == "manual_pause"


@pytest.mark.parametrize("ambience", ["base", "scene"])
async def test_reopening_cancels_slow_off_and_reapplies_full_ambience_with_lux_on(
    hass, freezer, room_engine, ambience
):
    engine, _, room, calls = room_engine
    await configure(hass, freezer, room_engine, mode="sun", turn_off=True)
    if ambience == "scene":
        room["scenes"] = [scene()]
        hass.states.async_set("media_player.tv", "on")
        await engine.async_reconfigure()
    await sun(hass, -1)
    await sun(hass, 1)
    calls.clear()
    entered, finish = asyncio.Event(), asyncio.Event()

    async def slow_fading_off(call):
        calls.append(call)
        entered.set()
        await finish.wait()
        # A fading lamp may still report on when the service has returned.

    hass.services.async_register("light", "turn_off", slow_fading_off)
    freezer.move_to(dt_util.utcnow() + timedelta(seconds=20))
    closing = hass.async_create_task(engine._async_tick(dt_util.utcnow()))
    await entered.wait()
    hass.states.async_set("sun.sun", "above_horizon", {"elevation": -1})
    for _ in range(3):
        await asyncio.sleep(0)
    finish.set()
    await closing
    await hass.async_block_till_done()
    on_calls = [call for call in calls if call.service == "turn_on"]
    assert on_calls and all(call.data["transition"] == 10 for call in on_calls)
    assert hass.states.get("light.one").state == "on"
    if ambience == "base":
        assert len(on_calls) == 2
        assert len([call for call in calls if call.service == "turn_off"]) == 1
    else:
        assert engine.status["reason"] == "scene"
    calls.clear()
    await sun(hass, -2)
    assert not calls


@pytest.mark.parametrize(
    ("manual_off", "allow_off", "expected"),
    [(False, True, True), (False, False, False), (True, True, False)],
)
async def test_nightlight_solar_open_respects_manual_pause_policy(
    hass, freezer, room_engine, manual_off, allow_off, expected
):
    engine, _, room, calls = room_engine
    await configure(hass, freezer, room_engine, mode="sun", present=False)
    room["nightlight"] = {
        "enabled": True,
        "lights": {"light.one": {"state": "on", "brightness_pct": 5}},
    }
    room["allow_off_during_pause"] = allow_off
    await engine.async_reconfigure()
    if manual_off:
        await engine.async_turn_off(Context(user_id="user"))
    else:
        await engine.async_turn_on(Context(user_id="user"))
    pause = engine.status["pause_until"]
    calls.clear()
    await sun(hass, -1)
    assert engine.status["pause_until"] == pause
    if expected:
        assert engine.lighting_status["mode"] == "nightlight"
        assert calls and calls[0].data["transition"] == 10
    else:
        assert not calls


async def test_reconfiguration_discards_previous_solar_confirmation(
    hass, freezer, room_engine
):
    engine, _, room, _ = room_engine
    await configure(hass, freezer, room_engine, mode="sun", turn_off=True)
    await sun(hass, -1)
    await sun(hass, 1)
    old_deadline = engine.status["lighting_off_deadline"]
    await advance(hass, freezer, 10)
    room["lux_off_delay"] = 40
    await engine.async_reconfigure()
    assert engine.status["lighting_off_deadline"] != old_deadline
    await advance(hass, freezer, 39)
    assert engine.is_on
    await advance(hass, freezer, 1)
    assert not engine.is_on


@pytest.mark.parametrize("source", [None, "sun.missing"])
async def test_missing_solar_entity_blocks_without_falling_back_to_always(
    hass, freezer, room_engine, source
):
    engine, manager, _, calls = room_engine
    await configure(hass, freezer, room_engine, mode="sun")
    manager.config["sun_entity_id"] = source
    await engine.async_reconfigure()
    assert engine.status["lighting_allowed"] is None
    assert engine.status["reason"] == "unavailable"
    assert not calls


@pytest.mark.parametrize("invalid", [-91, 91, pytest.param(10**400, id="overflow")])
async def test_invalid_solar_data_leaves_an_active_natural_ambience_unchanged(
    hass, freezer, room_engine, invalid
):
    engine, manager, room, calls = room_engine
    await configure(hass, freezer, room_engine, mode="sun", turn_off=True)
    manager.config["profiles"]["day"] = natural_profile()
    room["associations"] = [{"profile_id": "day", "lights": room["lights"]}]
    candidate = scene()
    candidate["conditions"] = {"type": "sun", "below": -80}
    room["scenes"] = [candidate]
    await engine.async_reconfigure()
    await sun(hass, -1)
    assert engine.is_on
    calls.clear()
    # Evaluate directly so an internal exception fails this test, instead of
    # becoming only a log entry from Home Assistant's event task.
    hass.states.async_set("sun.sun", "above_horizon", {"elevation": invalid})
    await engine._async_wakeup("condition")
    await hass.async_block_till_done()
    assert engine.status["lighting_allowed"] is None
    assert engine.status["reason"] == "unavailable"
    assert engine.is_on and not calls


@pytest.mark.parametrize(
    ("mode", "sensor"),
    [("always", False), ("time", False), ("sun", False), ("always", True)],
)
async def test_inactive_lux_off_does_not_prevent_return_during_fade(
    hass, freezer, room_engine, mode, sensor
):
    engine, _, room, calls = room_engine
    await configure(
        hass,
        freezer,
        room_engine,
        mode=mode,
        now="2026-10-10T19:00:00+00:00",
        turn_off=True,
    )
    room["lux_off"] = True  # Preserved setting from a previous sensor.
    if sensor:
        room["lux_entity_id"] = "sensor.lux"
    await sun(hass, -1)
    await engine.async_reconfigure()
    assert engine.is_on and engine.status["lighting_allowed"] is True

    async def fading_off(call):
        calls.append(call)
        # The accepted off transition has not yet reached the real off state.

    hass.services.async_register("light", "turn_off", fading_off)
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    assert engine.is_on
    calls.clear()
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    if sensor:
        # A configured lux sensor retains its existing lux_off=true contract.
        assert not calls
    else:
        assert len(calls) == 2
        assert all(
            call.service == "turn_on" and call.data["transition"] == 1 for call in calls
        )


async def test_inactive_lux_off_does_not_leave_pending_absence_commands(
    hass, freezer, room_engine
):
    engine, _, room, calls = room_engine
    await configure(hass, freezer, room_engine, mode="always", turn_off=True)
    room["lux_off"] = True
    await engine.async_reconfigure()
    calls.clear()
    entered, finish = asyncio.Event(), asyncio.Event()

    async def slow_off(call):
        calls.append(call)
        if not entered.is_set():
            entered.set()
            await finish.wait()
        old = hass.states.get(call.data["entity_id"])
        hass.states.async_set(
            old.entity_id, "off", dict(old.attributes), context=call.context
        )

    hass.services.async_register("light", "turn_off", slow_off)
    hass.states.async_set("binary_sensor.presence", "off")
    await entered.wait()
    hass.states.async_set("binary_sensor.presence", "on")
    for _ in range(3):
        await asyncio.sleep(0)
    finish.set()
    await hass.async_block_till_done()
    assert len([call for call in calls if call.service == "turn_off"]) == 1
    on_calls = [call for call in calls if call.service == "turn_on"]
    assert len(on_calls) == 2
    assert all(call.data["transition"] == 1 for call in on_calls)
    assert all(hass.states.get(entity).state == "on" for entity in room["lights"])
