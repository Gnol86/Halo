import type { Condition, Curve, Light, Profile, Room, Transition } from "./types";

export const categories: Transition[] = ["turn_on", "lux_on", "natural", "scene", "turn_off"];

export function createId(): string {
  // getRandomValues is available on local HTTP Home Assistant instances too.
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function newRoom(id: string): Room {
  return { id, lights: [], presence_entity_id: null, presence_states: ["on"], lux_entity_id: null,
    lux_threshold: null, lux_hysteresis: 0, lux_off: false, absence_delay: 0, manual_pause: 7200,
    lux_off_delay: 30, allow_off_during_pause: true, automation_enabled: false, natural_enabled: true,
    transitions: { turn_on: "inherit", lux_on: "inherit", natural: "inherit", scene: "inherit", turn_off: "inherit" },
    base: {}, associations: [], scenes: [] };
}
export function newProfile(id: string, name: string): Profile {
  const morning = { brightness: { low_elevation: -6, high_elevation: 45, low: 20, high: 100 },
    temperature: { low_elevation: -6, high_elevation: 45, low: 2200, high: 6500 } };
  return { id, name, linked: true, morning, evening: structuredClone(morning) };
}
export function interpolate(curve: Curve, elevation: number): number {
  if (curve.high_elevation <= curve.low_elevation) return curve.low;
  const progress = Math.min(1, Math.max(0, (elevation - curve.low_elevation) / (curve.high_elevation - curve.low_elevation)));
  return curve.low + (curve.high - curve.low) * progress;
}
export function dimmable(light: Light): boolean {
  return light.supported_color_modes.some((mode) => !["onoff", "unknown"].includes(mode));
}
export function colorMode(light: Light): "rgb_color" | "hs_color" | "xy_color" | undefined {
  if (light.supported_color_modes.some((mode) => ["rgb", "rgbw", "rgbww"].includes(mode))) return "rgb_color";
  if (light.supported_color_modes.includes("hs")) return "hs_color";
  if (light.supported_color_modes.includes("xy")) return "xy_color";
  return undefined;
}
export function newCondition(type: Condition["type"]): Condition {
  switch (type) {
    case "and": case "or": return { type, conditions: [newCondition("state")] };
    case "not": return { type, condition: newCondition("state") };
    case "state": return { type, entity_id: "", state: "on" };
    case "numeric": return { type, entity_id: "", above: 0 };
    case "time": return { type, after: "18:00", before: "23:00" };
    case "sun": return { type, below: 0 };
  }
}
export function moveItem<T>(items: T[], from: number, to: number): T[] {
  const result = [...items];
  if (from < 0 || from >= result.length || to < 0 || to >= result.length) return result;
  result.splice(to, 0, result.splice(from, 1)[0]);
  return result;
}
export function optionalNumber(value: string): number | null {
  return value.trim() === "" ? null : Number(value);
}
