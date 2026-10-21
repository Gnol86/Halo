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

test("unlinked day and night bridges are continuous at the summit and across midnight", () => {
  const profile = newProfile("split", "Split");
  profile.linked = false;
  profile.evening.brightness.low = 12;
  profile.evening.brightness.high = 75;
  profile.evening.temperature.low = 1500;
  profile.evening.temperature.high = 9000;
  const original = structuredClone(profile);
  const samples = profileSamples(profile);
  const summit = samples.filter((sample) => sample.position === .5);
  assert.ok(summit.length >= 1);
  for (const sample of summit) {
    close(sample.brightness, 87.5);
    close(sample.temperature, 7250);
  }
  close(samples[0].brightness, 26);
  close(samples[0].temperature, 1750);
  close(samples.at(-1)!.brightness, samples[0].brightness);
  close(samples.at(-1)!.temperature, samples[0].temperature);
  const dayStart = solarPosition(profile.morning.brightness.high_elevation, "morning");
  const dayEnd = solarPosition(profile.evening.brightness.high_elevation, "evening");
  const dayQuarter = samples.find((sample) => Math.abs(sample.position - (dayStart + (dayEnd - dayStart) / 4)) < 1e-12)!;
  close(dayQuarter.brightness, 96.09375, 1e-9);
  const nightStart = solarPosition(profile.evening.brightness.low_elevation, "evening");
  const nightEnd = solarPosition(profile.morning.brightness.low_elevation, "morning") + 1;
  const nightQuarter = samples.find((sample) => Math.abs(sample.position - (nightStart + (nightEnd - nightStart) / 4)) < 1e-12)!;
  close(nightQuarter.brightness, 16.375, 1e-9);
  for (const period of ["morning", "evening"] as const) {
    for (const kind of ["brightness", "temperature"] as const) {
      const curve = profile[period][kind];
      const branch = samples.filter((sample) => sample.period === period);
      close(branch.find((sample) => sample.elevation === curve.low_elevation)![kind], curve.low);
      close(branch.find((sample) => sample.elevation === curve.high_elevation)![kind], curve.high);
    }
  }
  for (let index = 1; index < samples.length; index++) assert.ok(samples[index].position >= samples[index - 1].position);
  assert.deepEqual(profile, original);
});

test("unlinked brightness and temperature join their own thresholds while retaining each ramp interpolation", () => {
  const profile = newProfile("independent-split", "Independent split");
  profile.linked = false;
  profile.morning.brightness = { low_elevation: -30, high_elevation: 10, low: 10, high: 90, interpolation: "linear" };
  profile.evening.brightness = { low_elevation: -15, high_elevation: 40, low: 20, high: 70, interpolation: "ease_in_out" };
  profile.morning.temperature = { low_elevation: -5, high_elevation: 50, low: 2000, high: 6500, interpolation: "ease_in" };
  profile.evening.temperature = { low_elevation: -35, high_elevation: 5, low: 3200, high: 9000 };
  const samples = profileSamples(profile);
  for (const period of ["morning", "evening"] as const) {
    for (const kind of ["brightness", "temperature"] as const) {
      const curve = profile[period][kind];
      const ramp = samples.filter((sample) => sample.period === period && sample.elevation >= curve.low_elevation && sample.elevation <= curve.high_elevation);
      assert.ok(ramp.length >= 33);
      for (const sample of ramp) close(sample[kind], interpolate(curve, sample.elevation), 1e-8);
    }
  }
  const midpoint = (kind: "brightness" | "temperature") => (solarPosition(profile.morning[kind].high_elevation, "morning") + solarPosition(profile.evening[kind].high_elevation, "evening")) / 2;
  const at = (position: number) => samples.find((sample) => Math.abs(sample.position - position) < 1e-12)!;
  assert.ok(at(midpoint("brightness")), "The brightness bridge retains its midpoint in the preview");
  assert.ok(at(midpoint("temperature")), "The temperature bridge retains its independent midpoint");
  close(at(midpoint("brightness")).brightness, 80);
  close(at(midpoint("temperature")).temperature, 7750);
  assert.ok(Math.abs(at(midpoint("brightness")).temperature - 7750) > 1, "Different thresholds do not share one bridge timeline");
});

test("unlinked bridges preserve constant values and remain bounded for inverted ramps", () => {
  const profile = newProfile("constant-split", "Constant split");
  profile.linked = false;
  for (const period of [profile.morning, profile.evening]) {
    period.brightness.low = period.brightness.high = 42.5;
    period.temperature.low = period.temperature.high = 4200;
  }
  assert.ok(profileSamples(profile).every((sample) => sample.brightness === 42.5 && sample.temperature === 4200));
  profile.morning.brightness.low = 100;
  profile.morning.brightness.high = 0;
  profile.evening.brightness.low = 20;
  profile.evening.brightness.high = 80;
  profile.morning.temperature.low = 6500;
  profile.morning.temperature.high = 2200;
  profile.evening.temperature.low = 1800;
  profile.evening.temperature.high = 6000;
  const samples = profileSamples(profile);
  const summit = samples.find((sample) => sample.position === .5)!;
  close(summit.brightness, 40);
  close(summit.temperature, 4100);
  close(samples[0].brightness, 60);
  close(samples[0].temperature, 4150);
  assert.ok(samples.every((sample) => sample.brightness >= 0 && sample.brightness <= 100 && sample.temperature >= 1800 && sample.temperature <= 6500));
});

test("coincident extreme anchors average both values and adapt adjacent ramps continuously", () => {
  const profile = newProfile("coincident", "Coincident");
  profile.linked = false;
  profile.morning.brightness = { low_elevation: -90, high_elevation: 90, low: 20, high: 100, interpolation: "linear" };
  profile.evening.brightness = { low_elevation: -90, high_elevation: 90, low: 40, high: 60, interpolation: "ease_in_out" };
  profile.morning.temperature = { low_elevation: -90, high_elevation: 90, low: 2000, high: 6500, interpolation: "ease_in_out" };
  profile.evening.temperature = { low_elevation: -90, high_elevation: 90, low: 3000, high: 4500, interpolation: "linear" };
  const original = structuredClone(profile);
  const samples = profileSamples(profile);
  for (const sample of samples.filter((point) => [0, .5, 1].includes(point.position))) {
    close(sample.brightness, sample.position === .5 ? 80 : 30);
    close(sample.temperature, sample.position === .5 ? 5500 : 2500);
  }
  const morningQuarter = samples.find((sample) => sample.period === "morning" && sample.elevation === -45)!;
  const eveningQuarter = samples.find((sample) => sample.period === "evening" && sample.elevation === -45)!;
  close(morningQuarter.brightness, 42.5);
  close(eveningQuarter.brightness, 37.8125);
  close(morningQuarter.temperature, 2968.75);
  close(eveningQuarter.temperature, 3250);
  assert.ok(samples.every((sample) => Number.isFinite(sample.brightness) && Number.isFinite(sample.temperature)));
  assert.deepEqual(profile, original, "Averaging coincident preview anchors never rewrites either profile endpoint");
});

test("very short day and night bridges keep interior samples and join without jumps", () => {
  const profile = newProfile("short-bridges", "Short bridges");
  profile.linked = false;
  profile.morning.brightness.high_elevation = 89.999999;
  profile.evening.brightness.high_elevation = 89.999998;
  profile.morning.brightness.high = 100;
  profile.evening.brightness.high = 20;
  profile.morning.temperature.low_elevation = -89.999999;
  profile.evening.temperature.low_elevation = -89.999998;
  profile.morning.temperature.low = 2000;
  profile.evening.temperature.low = 6000;
  const samples = profileSamples(profile);
  const dayStart = solarPosition(profile.morning.brightness.high_elevation, "morning");
  const dayEnd = solarPosition(profile.evening.brightness.high_elevation, "evening");
  const dayInterior = samples.filter((sample) => sample.position > dayStart && sample.position < dayEnd);
  assert.ok(new Set(dayInterior.map((sample) => sample.position)).size >= 31, "A narrow day bridge must remain curved instead of collapsing to one line segment");
  assert.ok(dayInterior.every((sample) => sample.brightness > 20 && sample.brightness < 100));
  const nightStart = solarPosition(profile.evening.temperature.low_elevation, "evening");
  const nightEnd = solarPosition(profile.morning.temperature.low_elevation, "morning") + 1;
  const nightInterior = samples.map((sample) => ({ ...sample, position: sample.position < .5 ? sample.position + 1 : sample.position }))
    .filter((sample) => sample.position > nightStart && sample.position < nightEnd);
  assert.ok(new Set(nightInterior.map((sample) => sample.position)).size >= 31, "The short night bridge remains sampled across the cycle boundary");
  assert.ok(nightInterior.every((sample) => sample.temperature > 2000 && sample.temperature < 6000));
  close(samples[0].temperature, samples.at(-1)!.temperature, 1e-8);
  assert.ok(samples.length < 1000, "Narrow bridges retain a bounded rendering cost");
});

test("unlinked close decimal ramps retain exact endpoints and their progression beside the bridges", () => {
  const profile = newProfile("split-close", "Split close");
  profile.linked = false;
  profile.morning.brightness = { low_elevation: 12.345678, high_elevation: 12.345679, low: 20, high: 80, interpolation: "ease_in_out" };
  profile.evening.brightness = { low_elevation: 12.3456781, high_elevation: 12.3456782, low: 35, high: 65, interpolation: "linear" };
  profile.morning.temperature = { low_elevation: -6.125, high_elevation: -6.12, low: 6500, high: 2200, interpolation: "linear" };
  profile.evening.temperature = { low_elevation: -6.125, high_elevation: -6.12, low: 1000, high: 40000, interpolation: "ease_in_out" };
  const samples = profileSamples(profile);
  for (const period of ["morning", "evening"] as const) {
    for (const kind of ["brightness", "temperature"] as const) {
      const curve = profile[period][kind];
      const ramp = samples.filter((sample) => sample.period === period && sample.elevation >= curve.low_elevation && sample.elevation <= curve.high_elevation);
      assert.ok(ramp.length >= 33);
      close(ramp.find((sample) => sample.elevation === curve.low_elevation)![kind], curve.low);
      close(ramp.find((sample) => sample.elevation === curve.high_elevation)![kind], curve.high);
      for (const sample of ramp) close(sample[kind], interpolate(curve, sample.elevation), 1e-7);
    }
  }
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
