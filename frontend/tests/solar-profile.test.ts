import assert from "node:assert/strict";
import { test } from "node:test";
import { interpolate, newProfile } from "../src/model";
import { elevationLimits, profileSamples, solarElevation, solarPosition, temperatureColor, temperaturePosition, temperatureValue } from "../src/solar-profile";
import type { Profile } from "../src/types";

function close(actual: number, expected: number, tolerance = 1e-10): void {
  assert.ok(Math.abs(actual - expected) <= tolerance, `${actual} differs from ${expected}`);
}

test("solar journey has exact night, horizon and summit anchors with reversible branches", () => {
  assert.deepEqual([0, .25, .5, .75, 1].map(solarElevation), [-90, 0, 90, 0, -90]);
  for (const elevation of [-90, -89.9999, -20, -6.5, 0, .001, 20, 45.5, 89.9999, 90]) {
    const morning = solarPosition(elevation, "morning");
    const evening = solarPosition(elevation, "evening");
    assert.ok(morning >= 0 && morning <= .5);
    assert.ok(evening >= .5 && evening <= 1);
    close(morning + evening, 1);
    close(solarElevation(morning), elevation);
    close(solarElevation(evening), elevation);
  }
  for (const position of [.001, .12345, .249, .499, .501, .749, .98765, .999]) {
    close(solarPosition(solarElevation(position), position < .5 ? "morning" : "evening"), position);
  }
});

test("solar and logarithmic mappings do not disguise invalid input", () => {
  for (const value of [NaN, Infinity, -Infinity, -1, 1.1]) {
    assert.ok(Number.isNaN(solarElevation(value)));
    assert.ok(Number.isNaN(temperatureValue(value)));
  }
  for (const value of [NaN, Infinity, -Infinity, -90.1, 90.1]) {
    assert.ok(Number.isNaN(solarPosition(value, "morning")));
    assert.ok(Number.isNaN(solarPosition(value, "evening")));
  }
  for (const value of [NaN, Infinity, -Infinity, 999, 40001]) {
    assert.ok(Number.isNaN(temperaturePosition(value)));
    assert.throws(() => temperatureColor(value), RangeError);
  }
});

test("strict elevation limits allow adjacent representable thresholds without an arbitrary gap", () => {
  for (const [low, high] of [
    [1, 1 + Number.EPSILON],
    [-1 - Number.EPSILON, -1],
    [-Number.MIN_VALUE, 0],
    [0, Number.MIN_VALUE],
    [-90, -89.99999999999999],
    [89.99999999999999, 90],
    [-6.125, -6.124999999999999],
  ]) {
    const curve = { low_elevation: low, high_elevation: high, low: 0, high: 100 };
    assert.deepEqual(elevationLimits(curve, "low"), { min: -90, max: low });
    assert.deepEqual(elevationLimits(curve, "high"), { min: high, max: 90 });
  }
});

test("elevation limits remain inside the solar domain at extremes, zero and close decimals", () => {
  const wide = { low_elevation: -90, high_elevation: 90, low: 0, high: 100 };
  assert.deepEqual(elevationLimits(wide, "low"), { min: -90, max: 89.99999999999999 });
  assert.deepEqual(elevationLimits(wide, "high"), { min: -89.99999999999999, max: 90 });
  assert.equal(elevationLimits({ ...wide, high_elevation: 0 }, "low").max, -Number.MIN_VALUE);
  assert.equal(elevationLimits({ ...wide, low_elevation: -0 }, "high").min, Number.MIN_VALUE);
  for (const [low, high] of [[-6.125, -6.12], [12.3456781, 12.3456782], [-Number.MIN_VALUE, Number.MIN_VALUE]]) {
    const curve = { ...wide, low_elevation: low, high_elevation: high };
    const lower = elevationLimits(curve, "low"), upper = elevationLimits(curve, "high");
    assert.ok(lower.max < high && lower.max >= low);
    assert.ok(upper.min > low && upper.min <= high);
  }
});

test("elevation limits reject invalid ranges rather than manufacturing slider bounds", () => {
  for (const [low, high] of [[0, 0], [1, -1], [-91, 0], [0, 91], [NaN, 20], [-20, Infinity]]) {
    for (const bound of ["low", "high"] as const) assert.throws(() => elevationLimits({ low_elevation: low, high_elevation: high, low: 0, high: 100 }, bound), RangeError);
  }
});

test("linked sampling follows the morning curves and preserves the source profile", () => {
  const profile = newProfile("base", "Base");
  profile.evening.brightness.low = 5;
  profile.evening.temperature.high = 12000;
  const original = structuredClone(profile);
  const samples = profileSamples(profile);
  assert.equal(samples[0].position, 0);
  assert.equal(samples.at(-1)!.position, 1);
  assert.deepEqual(profile, original);
  const morning = samples.filter((sample) => sample.period === "morning");
  const evening = samples.filter((sample) => sample.period === "evening").reverse();
  assert.equal(morning.length, evening.length);
  for (let index = 0; index < morning.length; index++) {
    close(morning[index].position + evening[index].position, 1);
    assert.equal(morning[index].brightness, evening[index].brightness);
    assert.equal(morning[index].temperature, evening[index].temperature);
  }
  assert.equal(samples.at(-1)!.brightness, 40);
});

test("brightness and temperature have independent thresholds, interpolation and plateaus", () => {
  const profile = newProfile("independent", "Independent");
  profile.morning.brightness = { low_elevation: -20, high_elevation: 20, low: 10, high: 90, interpolation: "linear" };
  profile.morning.temperature = { low_elevation: 0, high_elevation: 40, low: 2000, high: 6000, interpolation: "ease_in_out" };
  const samples = profileSamples(profile);
  for (const sample of samples) {
    assert.equal(sample.brightness, interpolate(profile.morning.brightness, sample.elevation));
    assert.equal(sample.temperature, interpolate(profile.morning.temperature, sample.elevation));
  }
  const at = (elevation: number) => samples.find((sample) => sample.elevation === elevation)!;
  assert.equal(at(-20).brightness, 10);
  assert.equal(at(0).brightness, 50);
  assert.equal(at(0).temperature, 2000);
  assert.equal(at(20).brightness, 90);
  assert.equal(at(20).temperature, 4000);
  assert.equal(at(40).temperature, 6000);
  assert.equal(at(10).temperature, 2625);
  assert.equal(samples[0].brightness, 10);
  assert.equal(samples.find((sample) => sample.position === .5)!.temperature, 6000);
});

test("close decimal transitions retain exact thresholds and internal progression points", () => {
  const profile = newProfile("close", "Close");
  profile.morning.brightness = { low_elevation: 12.345678, high_elevation: 12.345679, low: 0, high: 100, interpolation: "ease_in_out" };
  profile.morning.temperature = { low_elevation: 12.3456781, high_elevation: 12.3456782, low: 1000, high: 40000, interpolation: "linear" };
  const samples = profileSamples(profile);
  for (const period of ["morning", "evening"] as const) {
    const branch = samples.filter((sample) => sample.period === period);
    for (const kind of ["brightness", "temperature"] as const) {
      const curve = profile.morning[kind];
      assert.equal(branch.find((sample) => sample.elevation === curve.low_elevation)![kind], curve.low);
      assert.equal(branch.find((sample) => sample.elevation === curve.high_elevation)![kind], curve.high);
      assert.ok(branch.filter((sample) => sample.elevation > curve.low_elevation && sample.elevation < curve.high_elevation).length >= 31);
      assert.ok(branch.some((sample) => sample[kind] > curve.low && sample[kind] < curve.high));
    }
  }
  assert.ok(samples.length < 500, "sampling stays bounded during pointer movements");
});

test("unlinked periods retain both sides of the summit and different night settings", () => {
  const profile = newProfile("split", "Split");
  profile.linked = false;
  profile.evening.brightness.low = 12;
  profile.evening.brightness.high = 75;
  profile.evening.temperature.low = 1500;
  profile.evening.temperature.high = 9000;
  const samples = profileSamples(profile);
  assert.deepEqual(samples.filter((sample) => sample.position === .5).map((sample) => [sample.period, sample.brightness, sample.temperature]), [
    ["morning", 100, 5500], ["evening", 75, 9000],
  ]);
  assert.equal(samples[0].brightness, 40);
  assert.equal(samples[0].temperature, 2000);
  assert.equal(samples.at(-1)!.brightness, 12);
  assert.equal(samples.at(-1)!.temperature, 1500);
  for (let index = 1; index < samples.length; index++) assert.ok(samples[index].position >= samples[index - 1].position);
});

test("constant and inverted values, legacy interpolation and extreme elevations remain accurate", () => {
  const profile = newProfile("extremes", "Extremes");
  profile.morning.brightness = { low_elevation: -90, high_elevation: 90, low: 42.5, high: 42.5, interpolation: "ease_in" };
  profile.morning.temperature = { low_elevation: -90, high_elevation: 90, low: 40000, high: 1000, interpolation: "ease_in_out" };
  const samples = profileSamples(profile);
  assert.ok(samples.every((sample) => sample.brightness === 42.5));
  assert.equal(samples[0].temperature, 40000);
  assert.equal(samples.find((sample) => sample.position === .5)!.temperature, 1000);
  assert.equal(samples.find((sample) => sample.elevation === 0)!.temperature, 20500);
  profile.morning.brightness.low = 100;
  profile.morning.brightness.high = 0;
  assert.equal(profileSamples(profile).find((sample) => sample.elevation === 45)!.brightness, 15.625);
});

test("invalid active curves cannot produce a misleading preview", () => {
  const cases: Array<(profile: Profile) => void> = [
    (profile) => { profile.morning.brightness.low_elevation = 20; },
    (profile) => { profile.morning.brightness.high_elevation = -30; },
    (profile) => { profile.morning.brightness.low_elevation = -91; },
    (profile) => { profile.morning.brightness.high = 101; },
    (profile) => { profile.morning.temperature.low = 999; },
    (profile) => { profile.morning.temperature.high = 40001; },
    (profile) => { profile.morning.temperature.low_elevation = NaN; },
    (profile) => { profile.morning.temperature.high = Infinity; },
  ];
  for (const mutate of cases) {
    const profile = newProfile("invalid", "Invalid");
    mutate(profile);
    assert.throws(() => profileSamples(profile), RangeError);
  }
  const profile = newProfile("linked", "Linked");
  profile.evening.brightness.low = NaN;
  assert.doesNotThrow(() => profileSamples(profile));
  profile.linked = false;
  assert.throws(() => profileSamples(profile), RangeError);
});

test("temperature slider is logarithmic across the full stored range without rounding decimals", () => {
  assert.equal(temperaturePosition(1000), 0);
  assert.equal(temperaturePosition(40000), 1);
  assert.equal(temperatureValue(0), 1000);
  assert.equal(temperatureValue(1), 40000);
  close(temperatureValue(.5), Math.sqrt(1000 * 40000));
  for (const kelvin of [1000, 1250.5, 2000, 2700, 5500.25, 6500, 12345.678, 40000]) close(temperatureValue(temperaturePosition(kelvin)), kelvin);
  assert.ok(temperaturePosition(5500) - temperaturePosition(2000) > .25);
});

test("preview temperature colors progress from warm through neutral to cool with valid RGB channels", () => {
  const channels = (kelvin: number) => temperatureColor(kelvin).match(/\d+/g)!.map(Number);
  for (const kelvin of [1000, 1900, 2000, 2700, 5500, 6600, 10000, 40000]) {
    assert.match(temperatureColor(kelvin), /^rgb\(\d+, \d+, \d+\)$/);
    assert.ok(channels(kelvin).every((channel) => channel >= 0 && channel <= 255));
  }
  assert.ok(channels(2000)[0] > channels(2000)[2]);
  assert.ok(channels(10000)[2] > channels(10000)[0]);
  assert.ok(channels(6600).every((channel) => channel > 245));
});
