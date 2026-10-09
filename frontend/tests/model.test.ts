import assert from "node:assert/strict";
import { test } from "node:test";
import { createId, dimmable, interpolate, moveItem, newProfile, newRoom, optionalNumber } from "../src/model";
import { en, fr, language, translate } from "../src/translations";

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
