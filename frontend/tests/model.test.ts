import assert from "node:assert/strict";
import { test } from "node:test";
import { createId, curveInterpolation, dimmable, interpolate, moveItem, newProfile, newRoom, optionalNumber } from "../src/model";
import { en, fr, language, translate } from "../src/translations";
import type { Curve } from "../src/types";

test("room defaults preserve manual turn-off policy and opt-in automation", () => {
  const room = newRoom("living_room");
  assert.equal(room.automation_enabled, false);
  assert.equal(room.allow_off_during_pause, true);
  assert.equal(room.manual_pause, 7200);
  assert.equal(room.absence_delay, 0);
  assert.equal(room.lux_off_delay, 30);
  assert.equal(room.lux_threshold, null);
  assert.equal(room.lux_off, false);
  assert.deepEqual(new Set(Object.values(room.transitions)), new Set(["inherit"]));
});

test("new profile and scene identifiers work without secure-context randomUUID", () => {
  const descriptor = Object.getOwnPropertyDescriptor(crypto, "randomUUID");
  Object.defineProperty(crypto, "randomUUID", { value: undefined, configurable: true });
  try {
    const ids = Array.from({ length: 100 }, () => createId());
    assert.equal(new Set(ids).size, ids.length);
    for (const id of ids) assert.match(id, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  } finally {
    if (descriptor) Object.defineProperty(crypto, "randomUUID", descriptor);
    else Reflect.deleteProperty(crypto, "randomUUID");
  }
});

test("curve preview preserves fractional elevation, interpolates and clamps", () => {
  const curve = { low_elevation: -2.5, high_elevation: 7.5, low: 2000, high: 4000 };
  assert.equal(interpolate(curve, -20), 2000);
  assert.equal(interpolate(curve, 2.5), 3000);
  assert.equal(interpolate(curve, 50), 4000);
  const profile = newProfile("a", "My profile");
  profile.evening.brightness.low = 80;
  assert.equal(profile.morning.brightness.low, 20);
  for (const period of [profile.morning, profile.evening]) {
    assert.equal(period.brightness.interpolation, "linear");
    assert.equal(period.temperature.interpolation, "linear");
  }
});

test("S-curves ease both ends and stay symmetric for increasing, decreasing and constant values", () => {
  for (const [low, high] of [[20, 100], [6500, 2200], [42, 42]]) {
    const curve: Curve = { low_elevation: -6.25, high_elevation: 45.25, low, high, interpolation: "ease_in_out" };
    const midpoint = (curve.low_elevation + curve.high_elevation) / 2;
    const span = curve.high_elevation - curve.low_elevation;
    for (const [progress, eased] of [[0, 0], [.25, .15625], [.5, .5], [.75, .84375], [1, 1]]) {
      const elevation = curve.low_elevation + span * progress;
      assert.equal(interpolate(curve, elevation), low + (high - low) * eased);
      assert.equal(interpolate({ ...curve, interpolation: "ease_in" }, elevation), interpolate(curve, elevation));
    }
    assert.equal(interpolate(curve, -90), low);
    assert.equal(interpolate(curve, curve.low_elevation), low);
    assert.equal(interpolate(curve, curve.high_elevation), high);
    assert.equal(interpolate(curve, 90), high);
    assert.equal(interpolate({ ...curve, interpolation: "linear" }, midpoint), low + (high - low) / 2);
  }
});

test("legacy acceleration resolves to the S-curve without mutating stored input", () => {
  const curve: Curve = { low_elevation: 0, high_elevation: 10, low: 0, high: 100, interpolation: "ease_in" };
  assert.equal(curveInterpolation(curve), "ease_in_out");
  assert.equal(curve.interpolation, "ease_in");
  assert.equal(curveInterpolation({ ...curve, interpolation: undefined }), "linear");
});

test("transition blank differs from an explicit immediate transition", () => {
  assert.equal(optionalNumber(""), null);
  assert.equal(optionalNumber("0"), 0);
  assert.equal(optionalNumber("0.25"), .25);
});

test("profile compatibility excludes on/off and unknown-only lights", () => {
  const base = { entity_id: "light.test", name: "Test", area_id: null, available: true, supported_features: 0 };
  for (const modes of [["onoff"], ["unknown"], []]) assert.equal(dimmable({ ...base, supported_color_modes: modes }), false);
  for (const mode of ["brightness", "color_temp", "rgb", "hs", "xy"]) assert.equal(dimmable({ ...base, supported_color_modes: [mode] }), true);
});

test("scene reordering preserves all scenes and their stable identifiers", () => {
  const scenes = [{ id: "cinema" }, { id: "reading" }, { id: "night" }];
  assert.deepEqual(moveItem(scenes, 2, 0).map((scene) => scene.id), ["night", "cinema", "reading"]);
  assert.deepEqual(moveItem(scenes, 0, -1), scenes);
  assert.equal(scenes[0].id, "cinema");
});

test("French locales select a complete catalog, other locales fall back to English", () => {
  assert.deepEqual(Object.keys(en).sort(), Object.keys(fr).sort());
  for (const locale of ["fr", "fr-BE", "fr_CA", "FR-fr"]) assert.equal(language(locale), "fr");
  for (const locale of [undefined, "en", "de", "fre"]) assert.equal(language(locale), "en");
  assert.equal(translate("rooms", "fr-BE"), "Pièces");
  assert.equal(translate("rooms", "de"), "Rooms");
  for (const text of Object.values(fr)) assert.ok(text.trim());
});
