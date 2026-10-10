export type Transition = "turn_on" | "lux_on" | "natural" | "scene" | "turn_off";
export type Transitions = Record<Transition, number | null | "inherit">;
export interface LampState {
  state: "on" | "off";
  brightness?: number;
  brightness_pct?: number;
  color_mode?: string;
  color_temp_kelvin?: number;
  rgb_color?: number[];
  rgbw_color?: number[];
  rgbww_color?: number[];
  hs_color?: number[];
  xy_color?: number[];
  white?: number;
  effect?: string;
}
export type Condition =
  | { type: "and" | "or"; conditions: Condition[] }
  | { type: "not"; condition: Condition }
  | { type: "state"; entity_id: string; state: string }
  | { type: "numeric"; entity_id: string; attribute?: string; above?: number; below?: number }
  | { type: "time"; after?: string; before?: string }
  | { type: "sun"; above?: number; below?: number };
interface SceneSettings {
  id: string;
  name: string;
  can_turn_on: boolean;
  conditions: Condition | null;
}
export interface HaloScene extends SceneSettings {
  type?: "halo";
  lights: Record<string, LampState>;
}
export interface HomeAssistantScene extends SceneSettings {
  type: "home_assistant";
  scene_entity_id: string;
}
export type Scene = HaloScene | HomeAssistantScene;
export interface SceneInspection {
  entity_id: string;
  name: string;
  available: boolean;
  complete: boolean;
  lights: string[];
  outside_lights: string[];
  missing_lights: string[];
  other_entities: string[];
  blocked: boolean;
}
export type CurveInterpolation = "linear" | "ease_in_out";
// ease_in is accepted when reading a profile saved before the S-curve correction.
export interface Curve { low_elevation: number; high_elevation: number; low: number; high: number; interpolation?: CurveInterpolation | "ease_in" }
export interface Curves { brightness: Curve; temperature: Curve }
export interface Profile { id: string; name: string; linked: boolean; morning: Curves; evening: Curves }
export interface Association { profile_id: string; lights: string[]; brightness_offset: number }
export interface Nightlight { enabled: boolean; lights: Record<string, LampState> }
export interface LightingFallback {
  mode: "always" | "time" | "sun";
  start: string;
  end: string;
  linked: boolean;
  morning_below: number;
  evening_below: number;
  turn_off: boolean;
}
export interface Room {
  id: string;
  lights: string[];
  presence_entity_id: string | null;
  presence_states: string[];
  lux_entity_id: string | null;
  lux_threshold: number | null;
  lux_hysteresis: number;
  lux_off: boolean;
  lighting_fallback: LightingFallback;
  absence_delay: number;
  manual_pause: number;
  lux_off_delay: number;
  allow_off_during_pause: boolean;
  automation_enabled: boolean;
  natural_enabled: boolean;
  transitions: Transitions;
  base: Record<string, LampState>;
  nightlight: Nightlight;
  associations: Association[];
  scenes: Scene[];
}
export interface Config { sun_entity_id: string | null; presence_return_window: number; transitions: Transitions; profiles: Record<string, Profile>; rooms: Record<string, Room> }
export interface Light {
  entity_id: string;
  name: string;
  is_group?: boolean;
  group_members?: string[];
  group_members_complete?: boolean;
  member_of?: string[];
  area_id: string | null;
  available: boolean;
  supported_color_modes: string[];
  min_color_temp_kelvin?: number;
  max_color_temp_kelvin?: number;
  supported_features: number;
}
export interface Entity { entity_id: string; name: string; state: string; attributes: Record<string, unknown>; platform?: string }
export interface RoomStatus {
  [key: string]: unknown;
  reason?: string;
  state?: string;
  selected_scene?: string | null;
  scene_id?: string | null;
  pause_until?: string | number | null;
  is_on?: boolean;
  available?: boolean;
  scene_errors?: Record<string, string>;
  lighting_allowed?: boolean | null;
  lighting_source?: "lux" | "always" | "time" | "sun";
  lighting_off_deadline?: string | null;
}
export interface Snapshot {
  config: Config;
  areas: { id: string; name: string }[];
  lights: Light[];
  entities: Entity[];
  status: Record<string, RoomStatus>;
  is_admin: boolean;
  revision: number;
}
export interface Hass {
  language?: string;
  locale?: { language?: string };
  themes?: { darkMode?: boolean };
  states?: Record<string, { state: string; attributes: Record<string, unknown> }>;
  callWS<T>(message: Record<string, unknown>): Promise<T>;
  callApi<T>(method: "GET", path: string): Promise<T>;
  connection: { subscribeMessage<T>(callback: (event: T) => void, message: Record<string, unknown>): Promise<() => void> };
}
