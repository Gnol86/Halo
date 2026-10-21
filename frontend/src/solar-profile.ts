import { curveInterpolation, interpolate } from "./model";
import type { Curve, Curves, Profile } from "./types";

export type SolarPeriod = "morning" | "evening";
export type CurveKind = "brightness" | "temperature";
export type CurveBound = "low" | "high";
export interface ProfileSample {
  position: number;
  elevation: number;
  brightness: number;
  temperature: number;
  period: SolarPeriod;
}

const minimumTemperature = 1000;
const maximumTemperature = 40000;
const temperatureRatio = maximumTemperature / minimumTemperature;
const adjacentFloat = new DataView(new ArrayBuffer(8));

function inRange(value: number, minimum: number, maximum: number): boolean {
  return Number.isFinite(value) && value >= minimum && value <= maximum;
}

/** Schematic night-to-night journey, independent of geography and clock time. */
export function solarElevation(position: number): number {
  if (!inRange(position, 0, 1)) return NaN;
  if (position === 0 || position === 1) return -90;
  if (position === .25 || position === .75) return 0;
  if (position === .5) return 90;
  return -90 * Math.cos(2 * Math.PI * position);
}

export function solarPosition(elevation: number, period: SolarPeriod): number {
  if (!inRange(elevation, -90, 90)) return NaN;
  const morning = Math.acos(-elevation / 90) / (2 * Math.PI);
  return period === "morning" ? morning : 1 - morning;
}

/** Next representable finite value toward +Infinity (including both signed zeros). */
function nextElevation(value: number): number {
  if (value === 0) return Number.MIN_VALUE;
  adjacentFloat.setFloat64(0, value);
  const bits = adjacentFloat.getBigUint64(0);
  adjacentFloat.setBigUint64(0, bits + (value > 0 ? 1n : -1n));
  return adjacentFloat.getFloat64(0);
}

/** Strict slider bounds preserve even neighbouring floating-point thresholds. */
export function elevationLimits(curve: Curve, bound: CurveBound): { min: number; max: number } {
  if (!inRange(curve.low_elevation, -90, 90) || !inRange(curve.high_elevation, -90, 90)
    || curve.low_elevation >= curve.high_elevation) throw new RangeError("Invalid solar elevations");
  const adjacent = bound === "low" ? -nextElevation(-curve.high_elevation) : nextElevation(curve.low_elevation);
  const limit = adjacent === 0 ? 0 : adjacent;
  return bound === "low" ? { min: -90, max: limit } : { min: limit, max: 90 };
}

function validateCurve(curve: Curve, kind: CurveKind): void {
  const minimum = kind === "brightness" ? 0 : minimumTemperature;
  const maximum = kind === "brightness" ? 100 : maximumTemperature;
  if (!inRange(curve.low_elevation, -90, 90) || !inRange(curve.high_elevation, -90, 90)
    || curve.low_elevation >= curve.high_elevation
    || !inRange(curve.low, minimum, maximum) || !inRange(curve.high, minimum, maximum)) {
    throw new RangeError(`Invalid ${kind} curve`);
  }
}

interface SolarNode { position: number; elevation: number; value: number; outgoing: "bridge" | SolarPeriod; }

function smoothstep(value: number): number {
  const fraction = Math.min(1, Math.max(0, value));
  return fraction * fraction * (3 - 2 * fraction);
}

/** Four anchors repeated across midnight, with coincident extrema averaged. */
function cycleNodes(morning: Curve, evening: Curve): SolarNode[] {
  const anchors: SolarNode[] = [
    { position: solarPosition(morning.low_elevation, "morning"), elevation: morning.low_elevation, value: morning.low, outgoing: "morning" },
    { position: solarPosition(morning.high_elevation, "morning"), elevation: morning.high_elevation, value: morning.high, outgoing: "bridge" },
    { position: solarPosition(evening.high_elevation, "evening"), elevation: evening.high_elevation, value: evening.high, outgoing: "evening" },
    { position: solarPosition(evening.low_elevation, "evening"), elevation: evening.low_elevation, value: evening.low, outgoing: "bridge" },
  ];
  const repeated = [-1, 0, 1].flatMap((day) => anchors.map((node) => ({ ...node, position: node.position + day })));
  const nodes: SolarNode[] = [];
  for (let index = 0; index < repeated.length;) {
    const first = repeated[index];
    let end = index + 1, total = first.value;
    while (end < repeated.length && repeated[end].position === first.position) total += repeated[end++].value;
    nodes.push({ ...repeated[end - 1], value: total / (end - index) });
    index = end;
  }
  return nodes;
}

function cycleValue(nodes: SolarNode[], morning: Curve, evening: Curve, position: number, elevation: number): number {
  const next = nodes.findIndex((node) => node.position > position);
  const start = nodes[next - 1], end = nodes[next];
  if (position === start.position) return start.value;
  const bridge = start.outgoing === "bridge";
  const fraction = Math.min(1, Math.max(0, bridge
    ? (position - start.position) / (end.position - start.position)
    : (elevation - start.elevation) / (end.elevation - start.elevation)));
  const progress = bridge || curveInterpolation(start.outgoing === "morning" ? morning : evening) === "ease_in_out"
    ? smoothstep(fraction) : fraction;
  return start.value + (end.value - start.value) * progress;
}

function branchSamples(curves: Curves, period: SolarPeriod): ProfileSample[] {
  validateCurve(curves.brightness, "brightness");
  validateCurve(curves.temperature, "temperature");
  // Evenly spaced screen positions preserve the sun's shape and broad plateaus.
  const elevations = new Set(Array.from({ length: 121 }, (_, index) => solarElevation(index / 240)));
  for (const curve of [curves.brightness, curves.temperature]) {
    // Sample each transition independently, even when its thresholds are very close.
    // Retain the original elevations instead of a lossy acos/cos round trip.
    for (let index = 0; index <= 32; index++) {
      elevations.add(index === 32 ? curve.high_elevation
        : curve.low_elevation + (curve.high_elevation - curve.low_elevation) * index / 32);
    }
  }
  return [...elevations].sort((left, right) => period === "morning" ? left - right : right - left)
    .map((elevation) => ({
      position: solarPosition(elevation, period), elevation, period,
      brightness: interpolate(curves.brightness, elevation),
      temperature: interpolate(curves.temperature, elevation),
    }));
}

/** Reject invalid drafts instead of rendering a plausible but invented profile. */
export function profileSamples(profile: Profile): ProfileSample[] {
  const morning = branchSamples(profile.morning, "morning");
  const evening = branchSamples(profile.linked ? profile.morning : profile.evening, "evening");
  const samples = [...morning, ...evening];
  if (profile.linked) return samples;
  const cycles = { brightness: cycleNodes(profile.morning.brightness, profile.evening.brightness),
    temperature: cycleNodes(profile.morning.temperature, profile.evening.temperature) };
  const positions = new Set(samples.map((sample) => sample.position));
  for (const nodes of Object.values(cycles)) {
    for (let index = 0; index < nodes.length - 1; index++) {
      const start = nodes[index], end = nodes[index + 1];
      if (start.outgoing !== "bridge" || end.position < 0 || start.position > 1) continue;
      for (let step = 1; step < 32; step++) {
        const position = start.position + (end.position - start.position) * step / 32;
        if (position < 0 || position > 1 || positions.has(position)) continue;
        positions.add(position);
        samples.push({ position, elevation: solarElevation(position), period: position < .5 ? "morning" : "evening", brightness: 0, temperature: 0 });
      }
    }
  }
  samples.sort((left, right) => left.position - right.position);
  for (const kind of ["brightness", "temperature"] as const) {
    for (const sample of samples) {
      sample[kind] = cycleValue(cycles[kind], profile.morning[kind], profile.evening[kind], sample.position, sample.elevation);
    }
  }
  return samples;
}

export function temperaturePosition(kelvin: number): number {
  if (!inRange(kelvin, minimumTemperature, maximumTemperature)) return NaN;
  return Math.log(kelvin / minimumTemperature) / Math.log(temperatureRatio);
}

export function temperatureValue(position: number): number {
  if (!inRange(position, 0, 1)) return NaN;
  return minimumTemperature * temperatureRatio ** position;
}

/** Approximate black-body RGB for the preview; never a lamp command or calibration. */
export function temperatureColor(kelvin: number): string {
  if (!inRange(kelvin, minimumTemperature, maximumTemperature)) throw new RangeError("Invalid white temperature");
  const temperature = kelvin / 100;
  const red = temperature <= 66 ? 255 : 329.698727446 * (temperature - 60) ** -.1332047592;
  const green = temperature <= 66 ? 99.4708025861 * Math.log(temperature) - 161.1195681661
    : 288.1221695283 * (temperature - 60) ** -.0755148492;
  const blue = temperature >= 66 ? 255 : temperature <= 19 ? 0
    : 138.5177312231 * Math.log(temperature - 10) - 305.0447927307;
  return `rgb(${[red, green, blue].map((channel) => Math.round(Math.max(0, Math.min(255, channel)))).join(", ")})`;
}
