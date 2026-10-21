import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { Window } from "happy-dom";
import { newProfile, newRoom } from "../src/model";
import { translate } from "../src/translations";
import type { HaloEntityPicker } from "../src/entity-picker";
import type { Curve, Hass, HaloScene, HomeAssistantScene, SceneInspection, Scene, Snapshot } from "../src/types";

const window = new Window({ url: "http://192.168.1.4:8123" });
for (const key of ["window", "document", "customElements", "HTMLElement", "Element", "Node", "Document", "ShadowRoot", "CSSStyleSheet", "Event", "CustomEvent", "KeyboardEvent", "FocusEvent", "PointerEvent"] as const) {
  Object.defineProperty(globalThis, key, { configurable: true, value: key === "window" ? window : window[key] });
}
const { HaloPanel } = await import("../src/halo-panel");

function fixture(admin = true): Snapshot {
  const room = newRoom("lounge");
  room.lights = ["light.colour", "light.simple"];
  room.scenes = [{ id: "cinema", name: "Cinéma perso", conditions: { type: "state", entity_id: "media_player.tv", state: "on" }, can_turn_on: false,
    lights: { "light.colour": { state: "on", brightness_pct: 20 }, "light.simple": { state: "off" } } }];
  return { revision: 7, is_admin: admin, areas: [{ id: "lounge", name: "Salon personnalisé" }, { id: "kitchen", name: "Cuisine" }],
    config: { sun_entity_id: "sun.sun", presence_return_window: 30, profiles: {}, rooms: { lounge: room }, transitions: { turn_on: null, lux_on: null, natural: null, scene: null, turn_off: null } },
    status: { lounge: { reason: "disabled", is_on: true, available: true } },
    lights: [{ entity_id: "light.colour", name: "Lampe couleur", area_id: "lounge", available: true, supported_color_modes: ["rgb"], supported_features: 32 },
      { entity_id: "light.simple", name: "Lampe simple", area_id: "lounge", available: true, supported_color_modes: ["onoff"], supported_features: 0 },
      { entity_id: "light.extra", name: "Lampe libre", area_id: "kitchen", available: true, supported_color_modes: ["brightness"], supported_features: 0 }],
    entities: [{ entity_id: "sun.sun", name: "Sun", state: "above_horizon", attributes: { elevation: 15 } },
      { entity_id: "light.colour", name: "Lampe couleur", state: "on", attributes: { brightness: 128, color_mode: "rgb", rgb_color: [255, 128, 0], effect: "Rainbow" } },
      { entity_id: "light.simple", name: "Lampe simple", state: "off", attributes: {} },
      { entity_id: "media_player.tv", name: "TV", state: "off", attributes: {} }] };
}

async function settle(panel: InstanceType<typeof HaloPanel>) {
  await new Promise((resolve) => setTimeout(resolve, 10));
  await panel.updateComplete;
}

async function mount(admin = true, initial = fixture(admin), pending: { command?: () => Promise<Snapshot>; end?: () => Promise<Snapshot>; save?: (message: Record<string, unknown>) => Promise<Snapshot>; begin?: () => Promise<void>; preview?: () => Promise<void>; touch?: () => Promise<void>; api?: () => Promise<unknown>; import?: () => Promise<{ scene: Scene; ignored_entities: number }>; inspect?: (message: Record<string, unknown>) => Promise<SceneInspection> } = {}) {
  let snapshot = initial;
  const calls: Record<string, unknown>[] = [];
  let callback: ((snapshot: Snapshot) => void) | undefined;
  let unsubscribed = 0;
  const hass: Hass = { locale: { language: "fr-BE" }, language: "en", states: {},
    async callApi<T>(method: "GET", path: string) { calls.push({ type: "api", method, path }); return await pending.api?.() as T; },
    async callWS<T>(message: Record<string, unknown>) {
      calls.push(structuredClone(message));
      if (message.type === "halo/get") return structuredClone(snapshot) as T;
      if (message.type === "halo/command" && pending.command) return await pending.command() as T;
      if (message.type === "halo/save") {
        if (pending.save) return await pending.save(structuredClone(message)) as T;
        snapshot = { ...snapshot, config: structuredClone(message.config) as Snapshot["config"], revision: snapshot.revision + 1 };
        return structuredClone(snapshot) as T;
      }
      if (message.type === "halo/edit/begin") { await pending.begin?.(); return { token: "editor-token" } as T; }
      if (message.type === "halo/edit/preview") await pending.preview?.();
      if (message.type === "halo/edit/touch") await pending.touch?.();
      if (message.type === "halo/edit/end") return pending.end ? await pending.end() as T : structuredClone(snapshot) as T;
      if (message.type === "halo/scene/import") return await pending.import?.() as T;
      if (message.type === "halo/scene/inspect") return await pending.inspect?.(message) as T;
      return undefined as T;
    },
    connection: { async subscribeMessage<T>(handler: (event: T) => void) { callback = handler as (snapshot: Snapshot) => void; return () => { unsubscribed++; }; } } };
  const panel = window.document.createElement("halo-panel") as unknown as InstanceType<typeof HaloPanel>;
  panel.hass = hass;
  window.document.body.appendChild(panel as never);
  await settle(panel);
  return { panel, calls, hass, emit: (next: Snapshot) => { snapshot = next; callback?.(next); }, get unsubscribed() { return unsubscribed; } };
}

function button(panel: InstanceType<typeof HaloPanel>, text: string): HTMLButtonElement {
  const match = [...panel.shadowRoot!.querySelectorAll<HTMLButtonElement>("button")].find((item) => item.textContent?.trim() === text);
  assert.ok(match, `Button ${text} should exist`);
  return match;
}

function roomTab(panel: InstanceType<typeof HaloPanel>, name: string): HTMLButtonElement {
  const match = [...panel.shadowRoot!.querySelectorAll<HTMLButtonElement>('[role="tab"]')].find((item) => item.textContent?.trim() === name);
  assert.ok(match, `Room tab ${name} should exist`);
  return match;
}

async function selectRoomTab(panel: InstanceType<typeof HaloPanel>, name: string) {
  roomTab(panel, name).click();
  await settle(panel);
}

async function openRoom(panel: InstanceType<typeof HaloPanel>, section = "Pilotage", name = "Salon personnalisé") {
  const link = [...panel.shadowRoot!.querySelectorAll<HTMLButtonElement>(".room-link")].find((item) => item.getAttribute("aria-label") === name);
  assert.ok(link, `Room ${name} should exist`);
  link.click();
  await settle(panel);
  if (section !== "Pilotage") await selectRoomTab(panel, section);
}

function inputByLabel(panel: InstanceType<typeof HaloPanel>, text: string): HTMLInputElement {
  const label = [...panel.shadowRoot!.querySelectorAll<HTMLLabelElement>("label")].find((item) => item.textContent?.includes(text));
  assert.ok(label, `Label ${text} should exist`);
  const input = label.querySelector<HTMLInputElement>("input");
  assert.ok(input, `Input ${text} should exist`);
  return input;
}

afterEach(() => { window.document.body.replaceChildren(); });

test("Home Assistant menu follows host layout and sidebar preferences in every language", async () => {
  const { panel, hass } = await mount(false);
  const menu = () => panel.shadowRoot!.querySelector<HTMLButtonElement>(".sidebar-toggle");
  assert.equal(menu(), null);
  panel.narrow = true;
  for (const locale of ["fr-BE", "en", "es-MX"]) {
    panel.hass = { ...hass, locale: { language: locale } }; await settle(panel);
    assert.equal(menu()!.getAttribute("aria-label"), translate("openSidebar", locale));
    assert.equal(menu()!.disabled, false);
  }
  panel.narrow = false;
  for (const dockedSidebar of ["always_hidden", "docked", "auto"] as const) {
    panel.hass = { ...hass, dockedSidebar }; await settle(panel);
    assert.equal(Boolean(menu()), dockedSidebar === "always_hidden");
  }
  panel.narrow = true;
  panel.hass = { ...hass, kioskMode: true }; await settle(panel);
  assert.equal(menu(), null);
  panel.hass = { ...hass, auth: { external: { config: { hasSidebar: true } } } }; await settle(panel);
  assert.equal(menu(), null);
});

test("opening the host menu crosses shadow roots and preserves the unsaved draft", async () => {
  const { panel, hass, calls } = await mount();
  const host = document.createElement("div");
  document.body.appendChild(host);
  host.attachShadow({ mode: "open" }).appendChild(panel);
  await settle(panel);
  panel.narrow = true;
  await openRoom(panel, "Automatisation");
  const delay = inputByLabel(panel, "Délai d’absence");
  delay.value = "123"; delay.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  const callsBefore = structuredClone(calls);
  let received: CustomEvent | undefined;
  host.addEventListener("hass-toggle-menu", event => { received = event as CustomEvent; });
  panel.shadowRoot!.querySelector<HTMLButtonElement>(".sidebar-toggle")!.click(); await settle(panel);
  assert.deepEqual(received?.detail, { open: true });
  assert.equal(received?.composed, true);
  assert.equal(received?.bubbles, true);
  assert.equal(inputByLabel(panel, "Délai d’absence").value, "123");
  assert.ok(panel.shadowRoot!.querySelector(".savebar"));
  assert.deepEqual(calls, callsBefore);
  panel.hass = { ...hass }; await settle(panel);
  assert.equal(inputByLabel(panel, "Délai d’absence").value, "123");
});

test("room controls keep direct commands and automation without pause controls in all supported languages", async () => {
  for (const locale of ["fr-BE", "en", "es-MX"]) {
    const { panel, hass, calls } = await mount();
    panel.hass = { ...hass, locale: { language: locale } }; await settle(panel);
    await openRoom(panel, translate("controlTab", locale));
    assert.doesNotMatch(panel.shadowRoot!.textContent!, /Pause manuelle|Manual pause|Reprendre|Resume|Pause jusqu’à|Pause until/);
    assert.ok(panel.shadowRoot!.textContent!.includes(translate("directControlHelp", locale)));
    button(panel, translate("turnOn", locale)).click(); await settle(panel);
    button(panel, translate("turnOff", locale)).click(); await settle(panel);
    button(panel, translate("run", locale)).click(); await settle(panel);
    inputByLabel(panel, translate("automationShort", locale)).click(); await settle(panel);
    assert.deepEqual(calls.filter((call) => call.type === "halo/command").map((call) => call.command), ["turn_on", "turn_off", "scene", "automation"]);
    await selectRoomTab(panel, translate("automationShort", locale));
    assert.doesNotMatch(panel.shadowRoot!.textContent!, /Pause manuelle|Manual pause|Autoriser l’extinction automatique pendant|Allow automatic turn-off during/);
    assert.ok(inputByLabel(panel, translate("absenceDelay", locale)));
    panel.remove();
  }
});

function manualMode(panel: InstanceType<typeof HaloPanel>) {
  const select = panel.shadowRoot!.querySelector<HTMLSelectElement>(".manual-control select");
  assert.ok(select);
  return select;
}

async function setManualMode(panel: InstanceType<typeof HaloPanel>, value: "disabled" | "identified") {
  const select = manualMode(panel);
  select.value = value; select.dispatchEvent(new Event("change", { bubbles: true })); await settle(panel);
}

function heldFixture(admin = true): Snapshot {
  const snapshot = fixture(admin);
  snapshot.config.rooms.lounge.automation_enabled = true;
  snapshot.config.rooms.lounge.manual_control.mode = "identified";
  snapshot.status.lounge = { reason: "manual_hold", is_on: true, available: true, manual_hold: {
    version: 1, source: "user", entity_id: "light.colour", command: "light.turn_on", started_at: "2026-10-21T20:00:00Z", until: "2026-10-21T20:30:00Z",
  } };
  return snapshot;
}

test("manual detection stays disabled for existing snapshots and only exposes the identified mode", async () => {
  const snapshot = fixture();
  delete (snapshot.config.rooms.lounge as Partial<typeof snapshot.config.rooms.lounge>).manual_control;
  const { panel, calls } = await mount(true, snapshot);
  await openRoom(panel, "Automatisation");
  assert.equal(manualMode(panel).value, "disabled");
  assert.deepEqual([...manualMode(panel).options].map((option) => option.value), ["disabled", "identified"]);
  assert.equal(panel.shadowRoot!.querySelectorAll(".manual-control input").length, 0);
  assert.equal(panel.shadowRoot!.querySelectorAll(".manual-control halo-entity-picker").length, 0);
  assert.equal(calls.some((call) => call.type === "halo/save" || call.type === "halo/command"), false);
  await setManualMode(panel, "identified");
  assert.equal(inputByLabel(panel, "Durée de pause (minutes)").value, "120");
  assert.match(panel.shadowRoot!.querySelector(".manual-control")!.textContent!, /API authentifiée/);
});

test("existing thirty-minute manual settings remain unchanged when saving an unrelated room setting", async () => {
  const snapshot = fixture();
  snapshot.config.rooms.lounge.manual_control = { mode: "identified", duration: 1800, inputs: [] };
  const { panel, calls } = await mount(true, snapshot);
  await openRoom(panel, "Automatisation");
  assert.equal(inputByLabel(panel, "Durée de pause (minutes)").value, "30");
  const field = inputByLabel(panel, "Délai d’absence");
  field.value = "12"; field.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  const saved = calls.find((call) => call.type === "halo/save")!.config as Snapshot["config"];
  assert.equal(saved.rooms.lounge.manual_control.duration, 1800);
});

test("identified configuration is a multilingual draft that preserves seconds and saves only explicitly", async () => {
  const snapshot = fixture();
  snapshot.config.rooms.lounge.manual_control = { mode: "identified", duration: 1, inputs: [] };
  const { panel, hass, calls, emit } = await mount(true, snapshot);
  await openRoom(panel, "Automatisation");
  const field = inputByLabel(panel, "Durée de pause (minutes)");
  assert.equal(Number(field.value) * 60, 1);
  assert.equal(field.validity.valid, true);
  field.value = "12.5"; field.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  await selectRoomTab(panel, "Pilotage");
  const remote = structuredClone(snapshot); remote.status.lounge = { reason: "base" };
  emit(remote); await settle(panel);
  panel.hass = { ...hass, locale: { language: "es-MX" } }; await settle(panel);
  await selectRoomTab(panel, "Automatización");
  assert.equal(inputByLabel(panel, "Duración de la pausa (minutos)").value, "12.5");
  assert.equal(manualMode(panel).selectedOptions[0].textContent, "Órdenes identificadas");
  assert.equal(calls.some((call) => call.type === "halo/save" || call.type === "halo/command"), false);
  button(panel, "Guardar cambios").click(); await settle(panel);
  const saved = calls.find((call) => call.type === "halo/save")!.config as Snapshot["config"];
  assert.deepEqual(saved.rooms.lounge.manual_control, { mode: "identified", duration: 750, inputs: [] });
  assert.equal(snapshot.config.rooms.lounge.manual_control.duration, 1);
});

test("associated button picker limits domains, prevents duplicates and preserves missing inputs", async () => {
  const snapshot = heldFixture();
  snapshot.config.rooms.lounge.manual_control.inputs = ["event.removed"];
  snapshot.entities.push(
    { entity_id: "event.wall", name: "Bouton mural perso", state: "2026-10-21T20:00:00Z", attributes: {} },
    { entity_id: "input_button.remote", name: "Bouton virtuel perso", state: "unknown", attributes: {} },
    { entity_id: "button.restart", name: "Redémarrer", state: "unknown", attributes: {} },
    { entity_id: "binary_sensor.button", name: "Capteur", state: "off", attributes: {} },
  );
  const { panel, calls } = await mount(true, snapshot);
  await openRoom(panel, "Automatisation");
  const control = picker(panel, "Associer un bouton");
  assert.deepEqual(control.entities.map((entity) => entity.entity_id), ["event.wall", "input_button.remote"]);
  assert.equal(control.entities[1].state, undefined, "An input button with no previous activation is not unavailable");
  assert.match(panel.shadowRoot!.querySelector(".manual-inputs")!.textContent!, /event.removed.*Indisponible/);
  await searchEntity(control, "mural");
  control.shadowRoot!.querySelector<HTMLButtonElement>('[role="option"]')!.click(); await settle(panel);
  assert.deepEqual(picker(panel, "Associer un bouton").entities.map((entity) => entity.entity_id), ["input_button.remote"]);
  assert.equal(picker(panel, "Associer un bouton").value, null, "Adding a button resets the picker for the next association");
  assert.match(panel.shadowRoot!.querySelector(".manual-inputs")!.textContent!, /Bouton mural perso/);
  panel.shadowRoot!.querySelector<HTMLButtonElement>(`.manual-inputs button[aria-label="${translate("remove", "fr")} · event.removed"]`)!.click(); await settle(panel);
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  const saved = calls.find((call) => call.type === "halo/save")!.config as Snapshot["config"];
  assert.deepEqual(saved.rooms.lounge.manual_control.inputs, ["event.wall"]);
});

test("active pause shows honest sources, custom names, deadline and translated resume controls", async () => {
  const snapshot = heldFixture();
  const { panel, hass, emit } = await mount(true, snapshot);
  await openRoom(panel);
  for (const locale of ["en", "fr-BE", "es-MX"]) {
    panel.hass = { ...hass, locale: { language: locale } }; await settle(panel);
    for (const [source, key] of [["user", "manualSourceUser"], ["input", "manualSourceInput"], ["halo", "manualSourceHalo"], ["automation", "manualSourceAutomation"]] as const) {
      const next = structuredClone(snapshot); next.status.lounge.manual_hold!.source = source;
      emit(next); await settle(panel);
      const hold = panel.shadowRoot!.querySelector(".manual-hold")!;
      assert.ok(hold.textContent!.includes(translate("manual_hold", locale)));
      assert.ok(hold.textContent!.includes(translate(key, locale)));
      assert.match(hold.textContent!, /Lampe couleur/);
      assert.equal(hold.querySelector("time")!.getAttribute("datetime"), "2026-10-21T20:30:00Z");
      assert.equal(button(panel, translate("manualResume", locale)).disabled, false);
    }
  }
});

test("pause labels translate native service records, retain real scene names and hide unknown technical commands", async () => {
  const snapshot = heldFixture();
  const { panel, hass, emit } = await mount(true, snapshot);
  await openRoom(panel);
  const commands = [
    ["turn_on", "turnOn"], ["light.turn_on", "turnOn"], ["homeassistant.turn_on", "turnOn"],
    ["turn_off", "turnOff"], ["light.turn_off", "turnOff"], ["homeassistant.turn_off", "turnOff"],
    ["light.toggle", "manualToggle"], ["homeassistant.toggle", "manualToggle"],
    ["scene.turn_on", "scene"], ["input", "manualInputPress"], ["input_button.press", "manualInputPress"],
    ["manual_hold", "manualExplicitHold"], ["provider.unknown_action", "manualExplicitCommand"],
  ] as const;
  for (const locale of ["en", "fr-BE", "es-MX"]) {
    panel.hass = { ...hass, locale: { language: locale } }; await settle(panel);
    for (const [command, key] of commands) {
      const next = structuredClone(snapshot); next.status.lounge.manual_hold!.command = command;
      emit(next); await settle(panel);
      const label = panel.shadowRoot!.querySelector(".manual-hold .status-line")!.textContent!;
      assert.ok(label.endsWith(` · ${translate(key, locale)}`), `${command} should use ${key} in ${locale}`);
      assert.doesNotMatch(label, /light\.turn_|homeassistant\.|scene\.turn_on|input_button\.|provider\./);
    }
    for (const sceneId of ["cinema", "removed-private-id"]) {
      const next = structuredClone(snapshot); next.status.lounge.manual_hold!.command = `scene:${sceneId}`;
      next.status.lounge.manual_hold!.entity_id = null;
      emit(next); await settle(panel);
      const label = panel.shadowRoot!.querySelector(".manual-hold .status-line")!.textContent!;
      assert.ok(label.endsWith(` · ${translate("scene", locale)}${sceneId === "cinema" ? " · Cinéma perso" : ""}`));
      assert.doesNotMatch(label, /scene:|removed-private-id/);
    }
  }
});

test("manual-control errors remain localized and keep the active hold visible", async () => {
  for (const locale of ["en", "fr-BE", "es-MX"]) {
    for (const code of ["manual_control_disabled", "automation_disabled"] as const) {
      const { panel, hass } = await mount(true, heldFixture(), { command: async () => { throw { code }; } });
      panel.hass = { ...hass, locale: { language: locale } }; await settle(panel);
      await openRoom(panel, translate("controlTab", locale));
      button(panel, translate("manualResume", locale)).click(); await settle(panel);
      assert.ok(panel.shadowRoot!.querySelector('[role="alert"]')!.textContent!.includes(translate(code, locale)));
      assert.ok(panel.shadowRoot!.querySelector(".manual-hold"));
      panel.remove();
    }
  }
});

test("resume is available to non-admin controls but disabled while another session edits the room", async () => {
  const snapshot = heldFixture(false);
  const { panel, calls, emit } = await mount(false, snapshot);
  await openRoom(panel);
  assert.equal(panel.shadowRoot!.querySelectorAll('[role="tab"]').length, 1);
  assert.equal(panel.shadowRoot!.querySelector(".manual-control"), null);
  button(panel, "Reprendre").click(); await settle(panel);
  assert.deepEqual(calls.filter((call) => call.type === "halo/command"), [{ type: "halo/command", room_id: "lounge", command: "manual_resume" }]);
  assert.equal(calls.some((call) => call.type === "halo/save"), false);
  const editing = structuredClone(snapshot); editing.status.lounge.editing = true; editing.status.lounge.reason = "editing";
  emit(editing); await settle(panel);
  assert.equal(button(panel, "Reprendre").disabled, true);
  button(panel, "Reprendre").click(); await settle(panel);
  assert.equal(calls.filter((call) => call.type === "halo/command").length, 1);
});

test("resume neither saves nor discards a configuration draft and uses current runtime state", async () => {
  const snapshot = heldFixture();
  const resumed = structuredClone(snapshot); resumed.status.lounge.manual_hold = null; resumed.status.lounge.reason = "natural";
  const { panel, calls } = await mount(true, snapshot, { command: async () => resumed });
  await openRoom(panel, "Automatisation");
  const duration = inputByLabel(panel, "Durée de pause (minutes)");
  duration.value = "45"; duration.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  await selectRoomTab(panel, "Pilotage");
  button(panel, "Reprendre").click(); await settle(panel);
  assert.equal(calls.some((call) => call.type === "halo/save"), false);
  assert.equal(panel.shadowRoot!.querySelector(".manual-hold"), null);
  assert.ok(button(panel, "Enregistrer les modifications"));
  await selectRoomTab(panel, "Automatisation");
  assert.equal(inputByLabel(panel, "Durée de pause (minutes)").value, "45");
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  assert.equal((calls.find((call) => call.type === "halo/save")!.config as Snapshot["config"]).rooms.lounge.manual_control.duration, 2700);
});

test("invalid manual duration prevents hiding the field and disabling detection is only a draft", async () => {
  const snapshot = heldFixture();
  const { panel, calls } = await mount(true, snapshot);
  await openRoom(panel, "Automatisation");
  const field = inputByLabel(panel, "Durée de pause (minutes)");
  field.value = "0"; field.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  await setManualMode(panel, "disabled");
  assert.equal(manualMode(panel).value, "identified");
  assert.equal(field.value, "0");
  field.value = "30"; field.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  await setManualMode(panel, "disabled");
  assert.equal(panel.shadowRoot!.querySelector(".manual-control input"), null);
  assert.ok(panel.shadowRoot!.querySelector(".manual-hold"), "Unsaved configuration must not hide the active runtime pause");
  assert.equal(calls.some((call) => call.type === "halo/save" || call.type === "halo/command"), false);
  button(panel, "Abandonner les modifications").click(); await settle(panel);
  assert.equal(manualMode(panel).value, "identified");
});

test("failed resume keeps the pause visible and does not claim a successful return to automation", async () => {
  const { panel, calls } = await mount(true, heldFixture(), { command: async () => { throw { code: "edit_locked" }; } });
  await openRoom(panel);
  button(panel, "Reprendre").click(); await settle(panel);
  assert.ok(panel.shadowRoot!.querySelector(".manual-hold"));
  assert.match(panel.shadowRoot!.querySelector('[role="alert"]')!.textContent!, /session/);
  assert.equal(button(panel, "Reprendre").disabled, false);
  assert.equal(calls.some((call) => call.type === "halo/save"), false);
});

function solarHandle(panel: InstanceType<typeof HaloPanel>, period: "morning" | "evening", kind: "brightness" | "temperature", bound: "low" | "high") {
  const handle = panel.shadowRoot!.querySelector<HTMLButtonElement>(`.solar-handle[data-period="${period}"][data-kind="${kind}"][data-bound="${bound}"]`);
  assert.ok(handle, `${period} ${kind} ${bound} handle should exist`);
  return handle;
}

async function solarStage(panel: InstanceType<typeof HaloPanel>, period: "morning" | "evening", bound: "low" | "high") {
  const stage = panel.shadowRoot!.querySelector<HTMLButtonElement>(`.solar-stage[data-period="${period}"][data-bound="${bound}"]`);
  assert.ok(stage, `${period} ${bound} stage should exist`);
  stage.click(); await settle(panel);
}

function solarValue(panel: InstanceType<typeof HaloPanel>, kind: "brightness" | "temperature") {
  const slider = panel.shadowRoot!.querySelector<HTMLInputElement>(`.solar-value-slider[data-kind="${kind}"]`);
  assert.ok(slider, `${kind} value slider should exist`);
  return slider;
}

async function changeSolarValue(panel: InstanceType<typeof HaloPanel>, kind: "brightness" | "temperature", value: number) {
  const slider = solarValue(panel, kind);
  slider.value = String(value); slider.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
}

test("one daily chart exposes every exact threshold and keeps numerical settings collapsed without changing profiles", async () => {
  const curves: Curve[] = [
    { low_elevation: -6, high_elevation: 45, low: 20, high: 100 },
    { low_elevation: -6.125, high_elevation: -6.12, low: 6500, high: 2200 },
    { low_elevation: -90, high_elevation: 90, low: 45.5, high: 46 },
    { low_elevation: 89.75, high_elevation: 90, low: 4500.5, high: 4500.5 },
  ];
  const snapshot = fixture();
  const profile = newProfile("solar", "Natural");
  profile.linked = false;
  [profile.morning.brightness, profile.morning.temperature, profile.evening.brightness, profile.evening.temperature] = curves;
  snapshot.config.profiles.solar = profile;
  const { panel, calls } = await mount(true, snapshot);
  button(panel, "Profils de lumière naturelle").click(); await settle(panel);
  const charts = panel.shadowRoot!.querySelectorAll<SVGSVGElement>('svg[role="img"]');
  assert.equal(charts.length, 1);
  assert.ok(charts[0].classList.contains("solar-chart"));
  assert.ok(charts[0].getAttribute("aria-label"));
  assert.ok(charts[0].querySelector(".solar-sun-path"));
  const path = charts[0].querySelector(".solar-brightness-path")!.getAttribute("d")!;
  assert.ok(path.length > 0);
  assert.doesNotMatch(path, /NaN|Infinity/);
  assert.ok(charts[0].querySelectorAll(".solar-temperature-gradient stop").length > 2);
  assert.equal(panel.shadowRoot!.querySelectorAll('.solar-handle[role="slider"]').length, 8);
  assert.equal(panel.shadowRoot!.querySelectorAll(".solar-stage").length, 4);
  for (const [index, curve] of curves.entries()) {
    const period = index < 2 ? "morning" : "evening";
    const kind = index % 2 === 0 ? "brightness" : "temperature";
    for (const bound of ["low", "high"] as const) {
      const handle = solarHandle(panel, period, kind, bound);
      assert.equal(Number(handle.getAttribute("aria-valuenow")), curve[`${bound}_elevation`]);
      assert.ok(handle.getAttribute("aria-label"));
    }
  }
  assert.equal(panel.shadowRoot!.querySelector<HTMLDetailsElement>("details.profile-advanced")!.open, false);
  assert.equal(panel.shadowRoot!.querySelectorAll(".curve-editor").length, 4);
  assert.equal(panel.shadowRoot!.querySelector(".savebar"), null, "Rendering an existing decimal profile must not create a draft");
  const name = inputByLabel(panel, "Nom");
  name.value = "Natural renamed"; name.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  const saved = (calls.find((call) => call.type === "halo/save")!.config as Snapshot["config"]).profiles.solar;
  assert.deepEqual(saved.morning, profile.morning);
  assert.deepEqual(saved.evening, profile.evening);
});

test("the visual profile editor localizes chart descriptions, stages and value controls without renaming the profile", async () => {
  const snapshot = fixture();
  snapshot.config.profiles.solar = newProfile("solar", "Mon profil personnel");
  const { panel, hass } = await mount(true, snapshot);
  button(panel, "Profils de lumière naturelle").click(); await settle(panel);
  for (const [locale, description, start, end, advanced] of [
    ["fr-BE", "Journée solaire schématique", "Matin · Début", "Soir · Fin", "Réglages avancés"],
    ["en", "Schematic solar day", "Morning · Start", "Evening · End", "Advanced settings"],
    ["es-ES", "Día solar esquemático", "Mañana · Inicio", "Tarde · Fin", "Ajustes avanzados"],
  ]) {
    panel.hass = { ...hass, locale: { language: locale } }; await settle(panel);
    assert.ok(panel.shadowRoot!.querySelector(".solar-chart")!.getAttribute("aria-label")!.includes(description));
    assert.equal(panel.shadowRoot!.querySelector('.solar-stage[data-period="morning"][data-bound="low"]')!.textContent?.trim(), start);
    assert.equal(panel.shadowRoot!.querySelector('.solar-stage[data-period="evening"][data-bound="low"]')!.textContent?.trim(), end);
    assert.ok(solarHandle(panel, "morning", "brightness", "low").getAttribute("aria-label")!.includes(start));
    assert.ok(solarValue(panel, "temperature").getAttribute("aria-label")!.includes(start));
    assert.equal(panel.shadowRoot!.querySelector(".profile-advanced > summary")!.textContent?.trim(), advanced);
    assert.equal(panel.shadowRoot!.querySelector<HTMLInputElement>('.profile input[type="text"]')!.value, "Mon profil personnel");
  }
});

test("value sliders preview brightness and white temperature independently and only save configuration", async () => {
  const snapshot = fixture();
  const profile = newProfile("solar", "Natural");
  profile.morning.brightness.interpolation = "ease_in";
  profile.morning.temperature.interpolation = "ease_in_out";
  snapshot.config.profiles.solar = profile;
  const { panel, calls } = await mount(true, snapshot);
  button(panel, "Profils de lumière naturelle").click(); await settle(panel);
  assert.deepEqual([...panel.shadowRoot!.querySelectorAll<HTMLSelectElement>('.profile select[aria-describedby]')].map((select) => select.value), ["ease_in_out", "ease_in_out"]);
  await solarStage(panel, "morning", "low");
  const brightness = solarValue(panel, "brightness");
  assert.deepEqual([brightness.min, brightness.max, brightness.step], ["0", "100", "1"]);
  const temperature = solarValue(panel, "temperature");
  assert.deepEqual([temperature.min, temperature.max], ["0", "1"]);
  assert.match(brightness.closest("label")!.querySelector(".solar-value-elevation")!.textContent!, /-20/);
  assert.match(temperature.closest("label")!.querySelector(".solar-value-elevation")!.textContent!, /0/);
  const brightnessPath = () => panel.shadowRoot!.querySelector(".solar-brightness-path")!.getAttribute("d");
  const temperatureFill = () => panel.shadowRoot!.querySelector(".solar-temperature-gradient")!.innerHTML;
  const before = brightnessPath();
  const initialFill = temperatureFill();
  await changeSolarValue(panel, "brightness", 24);
  assert.notEqual(brightnessPath(), before);
  assert.equal(temperatureFill(), initialFill, "Brightness leaves the white temperature unchanged");
  const updatedPath = brightnessPath();
  await changeSolarValue(panel, "temperature", Math.log(3000.6 / 1000) / Math.log(40000 / 1000));
  assert.equal(brightnessPath(), updatedPath, "White temperature leaves brightness unchanged");
  assert.notEqual(temperatureFill(), initialFill);
  assert.ok(Math.abs(Number(solarValue(panel, "temperature").value) - Math.log(3001 / 1000) / Math.log(40000 / 1000)) < 1e-12, "The logarithmic position follows the selected integer kelvin value");
  assert.equal(solarValue(panel, "temperature").closest("label")!.querySelector("output")!.textContent!.replace(/\s/g, ""), "3001K");
  assert.equal(calls.some((call) => ["halo/save", "halo/command", "halo/edit/begin", "halo/edit/preview"].includes(String(call.type))), false);
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  const saved = (calls.find((call) => call.type === "halo/save")!.config as Snapshot["config"]).profiles.solar;
  assert.equal(saved.morning.brightness.low, 24);
  assert.equal(saved.morning.temperature.low, 3001);
  assert.equal(saved.morning.brightness.low_elevation, -20);
  assert.equal(saved.morning.temperature.low_elevation, 0);
  assert.equal(calls.some((call) => ["halo/command", "halo/edit/begin", "halo/edit/preview"].includes(String(call.type))), false);
});

test("integer brightness sliders preserve untouched legacy decimals and exact advanced values until moved", async () => {
  const snapshot = fixture();
  const profile = newProfile("solar", "Natural");
  profile.morning.brightness.low = 24.5;
  profile.morning.brightness.high = 95.25;
  profile.morning.brightness.interpolation = "linear";
  delete profile.morning.temperature.interpolation;
  snapshot.config.profiles.solar = profile;
  const { panel, calls } = await mount(true, snapshot);
  button(panel, "Profils de lumière naturelle").click(); await settle(panel);
  assert.equal(solarValue(panel, "brightness").step, "1");
  assert.equal(solarValue(panel, "brightness").checkValidity(), true, "The integer slider must not block saving an untouched fractional value");
  const name = inputByLabel(panel, "Nom");
  name.value = "Renamed"; name.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  const saved = () => (calls.filter((call) => call.type === "halo/save").at(-1)!.config as Snapshot["config"]).profiles.solar;
  assert.equal(saved().morning.brightness.low, 24.5);
  assert.equal(saved().morning.brightness.high, 95.25);
  assert.equal(saved().morning.brightness.interpolation, "linear");
  assert.equal(saved().morning.temperature.interpolation, undefined);
  const advancedLow = panel.shadowRoot!.querySelector(".curve-editor")!.querySelectorAll<HTMLInputElement>('input[type="number"]')[2];
  advancedLow.value = "24.25"; advancedLow.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  assert.equal(saved().morning.brightness.low, 24.25, "Advanced fields retain their exact numerical precision");
  await changeSolarValue(panel, "brightness", 25);
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  assert.equal(saved().morning.brightness.low, 25);
  assert.equal(saved().morning.brightness.high, 95.25, "Moving one endpoint never quantizes the other endpoint");
});

test("integer kelvin edits retain logarithmic controls and preserve untouched legacy and advanced decimals", async () => {
  const snapshot = fixture();
  const profile = newProfile("solar", "Natural");
  profile.morning.temperature.low = 2000.25;
  profile.morning.temperature.high = 5500.5;
  snapshot.config.profiles.solar = profile;
  const { panel, calls } = await mount(true, snapshot);
  button(panel, "Profils de lumière naturelle").click(); await settle(panel);
  const slider = solarValue(panel, "temperature");
  assert.deepEqual([slider.min, slider.max, slider.step], ["0", "1", "any"]);
  const name = inputByLabel(panel, "Nom");
  name.value = "Renamed"; name.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  const saved = () => (calls.filter((call) => call.type === "halo/save").at(-1)!.config as Snapshot["config"]).profiles.solar;
  assert.equal(saved().morning.temperature.low, 2000.25);
  assert.equal(saved().morning.temperature.high, 5500.5);
  const advancedLow = panel.shadowRoot!.querySelectorAll(".curve-editor")[1].querySelectorAll<HTMLInputElement>('input[type="number"]')[2];
  advancedLow.value = "2200.75"; advancedLow.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  assert.equal(saved().morning.temperature.low, 2200.75);
  await changeSolarValue(panel, "temperature", Math.log(2700.4 / 1000) / Math.log(40000 / 1000));
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  assert.equal(saved().morning.temperature.low, 2700);
  assert.equal(saved().morning.temperature.high, 5500.5);
  assert.equal(solarValue(panel, "temperature").getAttribute("aria-valuetext")!.replace(/\s/g, ""), "2700K");
  await changeSolarValue(panel, "temperature", Math.log(2700.2 / 1000) / Math.log(40000 / 1000));
  assert.equal(panel.shadowRoot!.querySelector(".savebar"), null, "A movement rounding to the same kelvin does not create an unsaved change");
  assert.ok(Math.abs(Number(solarValue(panel, "temperature").value) - Math.log(2700 / 1000) / Math.log(40000 / 1000)) < 1e-12);
});

test("stage selection raises both handles above an overlapping opposite-period handle after temperature was selected", async () => {
  const snapshot = fixture();
  const profile = newProfile("solar", "Natural");
  profile.linked = false;
  profile.morning.brightness.high_elevation = 90;
  profile.evening.brightness.high_elevation = 90;
  snapshot.config.profiles.solar = profile;
  const { panel } = await mount(true, snapshot);
  button(panel, "Profils de lumière naturelle").click(); await settle(panel);
  solarHandle(panel, "evening", "temperature", "low").click(); await settle(panel);
  await solarStage(panel, "morning", "high");
  const morningBrightness = solarHandle(panel, "morning", "brightness", "high");
  const eveningBrightness = solarHandle(panel, "evening", "brightness", "high");
  assert.equal(morningBrightness.style.left, eveningBrightness.style.left, "Both solar maxima overlap at the apex");
  for (const kind of ["brightness", "temperature"] as const) {
    const selected = solarHandle(panel, "morning", kind, "high");
    const opposite = solarHandle(panel, "evening", kind, "high");
    assert.equal(selected.dataset.active, "true");
    assert.ok(Number(selected.style.zIndex) > Number(opposite.style.zIndex), "Selecting a stage must make both of its handles reachable");
  }
});

test("each visual value label names its range control rather than the preceding output", async () => {
  const snapshot = fixture();
  snapshot.config.profiles.solar = newProfile("solar", "Natural");
  const { panel } = await mount(true, snapshot);
  button(panel, "Profils de lumière naturelle").click(); await settle(panel);
  const ids = new Set<string>();
  for (const kind of ["brightness", "temperature"] as const) {
    const slider = solarValue(panel, kind);
    const label = slider.closest("label")!;
    assert.ok(label.querySelector("output"), "The current value remains visible beside the label");
    assert.ok(slider.id, "The range has an explicit label target");
    assert.equal(label.htmlFor, slider.id);
    assert.equal(label.control, slider);
    ids.add(slider.id);
  }
  assert.equal(ids.size, 2, "Each range has its own label target");
});

test("linked evening edits update the morning reference, unlink copies it and relink keeps morning values", async () => {
  const snapshot = fixture();
  snapshot.config.profiles.solar = newProfile("solar", "Natural");
  const { panel, calls } = await mount(true, snapshot);
  button(panel, "Profils de lumière naturelle").click(); await settle(panel);
  await solarStage(panel, "evening", "high");
  assert.equal(solarValue(panel, "brightness").value, "100", "Evening starts at the high solar bound");
  await changeSolarValue(panel, "brightness", 75);
  await solarStage(panel, "morning", "high");
  assert.equal(solarValue(panel, "brightness").value, "75");
  solarHandle(panel, "evening", "brightness", "high").dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
  await settle(panel);
  assert.equal(Number(solarHandle(panel, "morning", "brightness", "high").getAttribute("aria-valuenow")), 19);
  assert.equal(Number(solarHandle(panel, "evening", "brightness", "high").getAttribute("aria-valuenow")), 19);
  const linked = () => panel.shadowRoot!.querySelector<HTMLInputElement>('.profile input[type="checkbox"]')!;
  linked().checked = false; linked().dispatchEvent(new Event("change", { bubbles: true })); await settle(panel);
  await solarStage(panel, "evening", "high");
  assert.equal(solarValue(panel, "brightness").value, "75", "Unlinking starts with the shared profile");
  await changeSolarValue(panel, "brightness", 55);
  await solarStage(panel, "morning", "high");
  assert.equal(solarValue(panel, "brightness").value, "75", "Independent evening changes leave morning untouched");
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  const separate = (calls.filter((call) => call.type === "halo/save").at(-1)!.config as Snapshot["config"]).profiles.solar;
  assert.equal(separate.linked, false);
  assert.equal(separate.morning.brightness.high, 75);
  assert.equal(separate.evening.brightness.high, 55);
  linked().checked = true; linked().dispatchEvent(new Event("change", { bubbles: true })); await settle(panel);
  await solarStage(panel, "evening", "high");
  assert.equal(solarValue(panel, "brightness").value, "75");
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  const relinked = (calls.filter((call) => call.type === "halo/save").at(-1)!.config as Snapshot["config"]).profiles.solar;
  assert.equal(relinked.linked, true);
  assert.equal(relinked.morning.brightness.high, 75);
});

test("keyboard threshold movement follows each solar direction and never crosses close decimal bounds", async () => {
  const snapshot = fixture();
  const profile = newProfile("solar", "Natural");
  profile.linked = false;
  profile.morning.temperature.low_elevation = -6.125;
  profile.morning.temperature.high_elevation = -6.12;
  snapshot.config.profiles.solar = profile;
  const { panel } = await mount(true, snapshot);
  button(panel, "Profils de lumière naturelle").click(); await settle(panel);
  const key = async (period: "morning" | "evening", kind: "brightness" | "temperature", bound: "low" | "high", name: string, shiftKey = false) => {
    solarHandle(panel, period, kind, bound).dispatchEvent(new KeyboardEvent("keydown", { key: name, shiftKey, bubbles: true, cancelable: true }));
    await settle(panel);
    return Number(solarHandle(panel, period, kind, bound).getAttribute("aria-valuenow"));
  };
  assert.equal(await key("morning", "brightness", "low", "ArrowRight"), -19);
  assert.equal(await key("evening", "brightness", "high", "ArrowRight"), 19);
  assert.equal(await key("evening", "brightness", "high", "ArrowLeft", true), 19.01);
  assert.equal(Number(solarHandle(panel, "morning", "temperature", "low").getAttribute("aria-valuenow")), -6.125, "Existing decimals remain exact before manipulation");
  const closeLow = await key("morning", "temperature", "low", "ArrowRight");
  assert.equal(closeLow, -6.125, "Without a legal centesimal step toward the neighbouring bound, the existing decimal remains untouched");
  assert.equal(Number(solarHandle(panel, "morning", "temperature", "high").getAttribute("aria-valuenow")), -6.12);
  assert.equal(await key("morning", "temperature", "low", "ArrowLeft", true), -6.13, "Moving away from a close bound reaches the next centesimal value");
  assert.equal(await key("morning", "brightness", "low", "Home"), -90);
  const end = await key("morning", "brightness", "low", "End");
  assert.equal(end, Number(solarHandle(panel, "morning", "brightness", "low").getAttribute("aria-valuemax")), "End reaches the maximum announced to assistive technology");
  assert.ok(end < Number(solarHandle(panel, "morning", "brightness", "high").getAttribute("aria-valuenow")));
  assert.equal(end, 19.99, "The last selectable centesimal elevation remains strictly below the high bound");
  const highStart = await key("morning", "brightness", "high", "Home");
  assert.equal(highStart, Number(solarHandle(panel, "morning", "brightness", "high").getAttribute("aria-valuemin")), "Home reaches the minimum announced to assistive technology");
  assert.ok(highStart > end);
  assert.equal(await key("morning", "brightness", "high", "End"), 90);
  assert.equal(Number(solarHandle(panel, "evening", "brightness", "low").getAttribute("aria-valuenow")), -20);
});

test("mouse and touch dragging update only the selected threshold and stop after release or cancellation", async () => {
  for (const pointerType of ["mouse", "touch"]) {
    const snapshot = fixture();
    const profile = newProfile("solar", "Natural");
    profile.linked = false;
    snapshot.config.profiles.solar = profile;
    const { panel, calls } = await mount(true, snapshot);
    button(panel, "Profils de lumière naturelle").click(); await settle(panel);
    const handle = solarHandle(panel, "morning", "brightness", "low");
    let captured: number | undefined;
    handle.setPointerCapture = (pointerId) => { captured = pointerId; };
    handle.hasPointerCapture = (pointerId) => captured === pointerId;
    handle.releasePointerCapture = (pointerId) => { assert.equal(captured, pointerId); captured = undefined; };
    handle.parentElement!.getBoundingClientRect = () => ({ left: 100, right: 900, top: 0, bottom: 44, x: 100, y: 0, width: 800, height: 44, toJSON() {} });
    const pointer = async (type: string, clientX: number, pointerId = 7) => {
      handle.dispatchEvent(new PointerEvent(type, { pointerId, pointerType, button: 0, clientX, bubbles: true, cancelable: true }));
      await settle(panel);
    };
    const before = panel.shadowRoot!.querySelector(".solar-brightness-path")!.getAttribute("d");
    await pointer("pointerdown", 240);
    assert.equal(captured, 7);
    assert.equal(panel.shadowRoot!.querySelector(".savebar"), null, "Selecting a handle does not change its value");
    await pointer("pointermove", 300, 8);
    assert.equal(Number(handle.getAttribute("aria-valuenow")), -20, "Another pointer cannot move the active handle");
    await pointer("pointermove", 300);
    assert.ok(Math.abs(Number(handle.getAttribute("aria-valuenow"))) < 1e-8, "The dawn position maps back to zero elevation");
    assert.notEqual(panel.shadowRoot!.querySelector(".solar-brightness-path")!.getAttribute("d"), before);
    assert.equal(Number(solarHandle(panel, "morning", "temperature", "low").getAttribute("aria-valuenow")), 0);
    assert.equal(Number(solarHandle(panel, "evening", "brightness", "low").getAttribute("aria-valuenow")), -20);
    await pointer("pointermove", 301);
    assert.equal(Number(handle.getAttribute("aria-valuenow")), 0.71, "Pointer motion selects hundredths of a degree instead of long cosine decimals");
    await pointer("pointermove", 500);
    const bounded = Number(handle.getAttribute("aria-valuenow"));
    assert.equal(bounded, 19.99, "Dragging beyond the next threshold reaches its last legal hundredth without crossing");
    assert.equal(bounded, Number(handle.getAttribute("aria-valuemax")));
    await pointer(pointerType === "mouse" ? "pointerup" : "pointercancel", 500);
    assert.equal(captured, undefined);
    await pointer("pointermove", 200);
    assert.equal(Number(handle.getAttribute("aria-valuenow")), bounded, "Released handles ignore subsequent pointer motion");
    assert.equal(calls.some((call) => ["halo/save", "halo/command", "halo/edit/preview"].includes(String(call.type))), false);
    panel.remove();
  }
});

test("dragging toward a very close decimal threshold preserves it when no centesimal movement is legal", async () => {
  const snapshot = fixture();
  const profile = newProfile("solar", "Natural");
  profile.morning.temperature.low_elevation = -6.125;
  profile.morning.temperature.high_elevation = -6.12;
  snapshot.config.profiles.solar = profile;
  const { panel, calls } = await mount(true, snapshot);
  button(panel, "Profils de lumière naturelle").click(); await settle(panel);
  const handle = solarHandle(panel, "morning", "temperature", "low");
  let captured = false;
  handle.setPointerCapture = () => { captured = true; };
  handle.hasPointerCapture = () => captured;
  handle.releasePointerCapture = () => { captured = false; };
  handle.parentElement!.getBoundingClientRect = () => ({ left: 100, right: 900, top: 0, bottom: 44, x: 100, y: 0, width: 800, height: 44, toJSON() {} });
  for (const [type, clientX] of [["pointerdown", 280], ["pointermove", 500], ["pointerup", 500]] as const) {
    handle.dispatchEvent(new PointerEvent(type, { pointerId: 1, pointerType: "mouse", button: 0, clientX, bubbles: true }));
    await settle(panel);
  }
  assert.equal(Number(handle.getAttribute("aria-valuenow")), -6.125);
  assert.equal(Number(solarHandle(panel, "morning", "temperature", "high").getAttribute("aria-valuenow")), -6.12);
  assert.equal(panel.shadowRoot!.querySelector(".savebar"), null);
  assert.equal(calls.some((call) => call.type === "halo/save"), false);
});

test("visual profile drafts survive a remote conflict and discard restores the latest server curve", async () => {
  const snapshot = fixture();
  snapshot.config.profiles.solar = newProfile("solar", "Natural");
  const { panel, emit, calls } = await mount(true, snapshot);
  button(panel, "Profils de lumière naturelle").click(); await settle(panel);
  await solarStage(panel, "morning", "low");
  await changeSolarValue(panel, "brightness", 25);
  const remote = structuredClone(snapshot);
  remote.revision++;
  remote.config.profiles.solar.morning.brightness.low = 65;
  emit(remote); await settle(panel);
  assert.equal(solarValue(panel, "brightness").value, "25");
  assert.equal(button(panel, "Enregistrer les modifications").disabled, true);
  assert.equal(calls.some((call) => call.type === "halo/save"), false);
  button(panel, "Abandonner les modifications").click(); await settle(panel);
  assert.equal(solarValue(panel, "brightness").value, "65");
  assert.equal(panel.shadowRoot!.querySelector(".savebar"), null);
});

test("each natural curve type can be selected and saved independently while old profiles stay linear", async () => {
  const snapshot = fixture();
  const profile = newProfile("solar", "Natural");
  for (const period of [profile.morning, profile.evening]) {
    delete period.brightness.interpolation;
    delete period.temperature.interpolation;
  }
  snapshot.config.profiles.solar = profile;
  const { panel, calls, hass } = await mount(true, snapshot);
  button(panel, "Profils de lumière naturelle").click();
  await settle(panel);
  const selectors = () => [...panel.shadowRoot!.querySelectorAll<HTMLSelectElement>('.profile select[aria-describedby]')];
  assert.deepEqual(selectors().map((select) => select.value), ["linear", "linear"]);
  assert.deepEqual([...selectors()[0].options].map((option) => option.textContent), ["Linéaire", "Accélération et décélération"]);
  selectors()[0].value = "ease_in_out";
  selectors()[0].dispatchEvent(new Event("change", { bubbles: true }));
  await settle(panel);
  assert.deepEqual(selectors().map((select) => select.value), ["ease_in_out", "linear"]);
  assert.match(panel.shadowRoot!.getElementById(selectors()[0].getAttribute("aria-describedby")!)!.textContent!, /hauteur solaire basse/);
  button(panel, "Enregistrer les modifications").click();
  await settle(panel);
  const firstSave = calls.find((call) => call.type === "halo/save")!.config as Snapshot["config"];
  assert.equal(firstSave.profiles.solar.morning.brightness.interpolation, "ease_in_out");
  assert.equal(firstSave.profiles.solar.morning.temperature.interpolation, undefined);

  const linked = panel.shadowRoot!.querySelector<HTMLInputElement>('.profile input[type="checkbox"]')!;
  linked.checked = false;
  linked.dispatchEvent(new Event("change", { bubbles: true }));
  await settle(panel);
  assert.deepEqual(selectors().map((select) => select.value), ["ease_in_out", "linear", "ease_in_out", "linear"]);
  selectors()[2].value = "linear";
  selectors()[2].dispatchEvent(new Event("change", { bubbles: true }));
  await settle(panel);
  selectors()[3].value = "ease_in_out";
  selectors()[3].dispatchEvent(new Event("change", { bubbles: true }));
  await settle(panel);
  button(panel, "Enregistrer les modifications").click();
  await settle(panel);
  const lastSave = calls.filter((call) => call.type === "halo/save").at(-1)!.config as Snapshot["config"];
  const saved = lastSave.profiles.solar;
  assert.equal(saved.linked, false);
  assert.deepEqual([saved.morning.brightness.interpolation, saved.morning.temperature.interpolation, saved.evening.brightness.interpolation, saved.evening.temperature.interpolation], ["ease_in_out", undefined, "linear", "ease_in_out"]);
  assert.deepEqual(selectors().map((select) => select.value), ["ease_in_out", "linear", "linear", "ease_in_out"]);
  panel.hass = { ...hass, locale: { language: "en" } };
  await settle(panel);
  assert.deepEqual([...selectors()[0].options].map((option) => option.textContent), ["Linear", "Gradual acceleration and deceleration"]);
});

test("panel follows HA user locale and keeps custom names without changing entity IDs", async () => {
  const { panel, hass } = await mount();
  assert.match(panel.shadowRoot!.textContent!, /Pièces/);
  assert.match(panel.shadowRoot!.textContent!, /Salon personnalisé/);
  assert.match(panel.shadowRoot!.textContent!, /Désactivé/);
  panel.hass = { ...hass, locale: { language: "es-MX" } };
  await settle(panel);
  assert.match(panel.shadowRoot!.textContent!, /Habitaciones/);
  assert.match(panel.shadowRoot!.textContent!, /Salon personnalisé/);
  assert.match(panel.shadowRoot!.textContent!, /Desactivado/);
  assert.equal(panel.shadowRoot!.querySelector("main")!.lang, "es");
  panel.hass = { ...hass, locale: { language: "de" } };
  await settle(panel);
  assert.match(panel.shadowRoot!.textContent!, /Rooms/);
  assert.match(panel.shadowRoot!.textContent!, /Salon personnalisé/);
  assert.match(panel.shadowRoot!.textContent!, /Disabled/);
  panel.hass = { ...hass, locale: undefined, language: "es" };
  await settle(panel);
  assert.match(panel.shadowRoot!.textContent!, /Habitaciones/);
});

test("switching to Spanish preserves the room draft, custom names and entity picker selection", async () => {
  const { panel, hass, calls } = await mount();
  await openRoom(panel, "Automatisation");
  await fill(panel, "Délai d’absence", "42");
  const picker = panel.shadowRoot!.querySelector<HaloEntityPicker>("halo-entity-picker")!;
  picker.dispatchEvent(new CustomEvent("entity-changed", { detail: { value: "media_player.tv" }, bubbles: true, composed: true }));
  await settle(panel);
  panel.hass = { ...hass, locale: { language: "es_ES" } }; await settle(panel);
  assert.equal(inputByLabel(panel, "Retardo de ausencia").value, "42");
  const translatedPicker = panel.shadowRoot!.querySelector<HaloEntityPicker>("halo-entity-picker")!;
  await translatedPicker.updateComplete;
  assert.equal(translatedPicker.value, "media_player.tv");
  assert.match(translatedPicker.shadowRoot!.textContent!, /Entidad de presencia/);
  assert.equal(translatedPicker.shadowRoot!.querySelector("input")!.getAttribute("placeholder"), "Buscar por nombre o ID de entidad");
  await selectRoomTab(panel, "Control");
  assert.match(panel.shadowRoot!.textContent!, /Cinéma perso/);
  assert.match(panel.shadowRoot!.textContent!, /Salon personnalisé/);
  button(panel, "Guardar cambios").click(); await settle(panel);
  const saved = calls.find((call) => call.type === "halo/save")!.config as Snapshot["config"];
  assert.equal(saved.rooms.lounge.absence_delay, 42);
  assert.equal(saved.rooms.lounge.presence_entity_id, "media_player.tv");
  assert.deepEqual(saved.rooms.lounge.lights, ["light.colour", "light.simple"]);
  assert.equal(saved.rooms.lounge.scenes[0].name, "Cinéma perso");
  assert.match(panel.shadowRoot!.textContent!, /Cambios guardados/);
});

test("native control color scheme follows the effective HA theme and inherits when it is absent", async () => {
  const { panel, hass } = await mount();
  assert.equal(panel.style.colorScheme, "");
  panel.hass = { ...hass, themes: { darkMode: true } };
  await settle(panel);
  assert.equal(panel.style.colorScheme, "dark");
  panel.hass = { ...hass, themes: { darkMode: false } };
  await settle(panel);
  assert.equal(panel.style.colorScheme, "light");
  panel.hass = { ...hass };
  await settle(panel);
  assert.equal(panel.style.colorScheme, "");
});

test("room tabs provide one labelled panel and roving keyboard navigation with wraparound", async () => {
  const { panel } = await mount();
  await openRoom(panel);
  assert.equal(panel.shadowRoot!.querySelectorAll('[role="tabpanel"]').length, 1);
  assert.equal(panel.shadowRoot!.querySelector('[role="tablist"]')!.getAttribute("aria-label"), "Rubriques de la pièce");
  const active = () => panel.shadowRoot!.querySelector<HTMLButtonElement>('[role="tab"][aria-selected="true"]')!;
  const verifySelection = (name: string) => {
    const selected = roomTab(panel, name);
    assert.equal(active(), selected);
    assert.equal(selected.tabIndex, 0);
    assert.ok([...panel.shadowRoot!.querySelectorAll<HTMLButtonElement>('[role="tab"]')].filter((tab) => tab !== selected).every((tab) => tab.tabIndex === -1));
    assert.equal(panel.shadowRoot!.querySelector('[role="tabpanel"]')!.getAttribute("aria-labelledby"), selected.id);
    assert.equal(selected.getAttribute("aria-controls"), "room-panel");
  };
  verifySelection("Pilotage");
  for (const [key, name] of [["ArrowRight", "Lumières"], ["End", "Réglages"], ["ArrowRight", "Pilotage"], ["ArrowLeft", "Réglages"], ["Home", "Pilotage"]]) {
    const event = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true });
    active().dispatchEvent(event);
    await settle(panel);
    assert.equal(event.defaultPrevented, true);
    verifySelection(name);
    assert.equal(panel.shadowRoot!.activeElement, active());
  }
  assert.equal(panel.shadowRoot!.querySelector(".light-list"), null, "Only the selected subsection is mounted");
  assert.ok(panel.shadowRoot!.querySelector(".scenes-section"));
});

test("the room rail filters names and its power control does not open or configure a room", async () => {
  const { panel, calls } = await mount();
  const toggle = panel.shadowRoot!.querySelector<HTMLButtonElement>(".quick-toggle")!;
  assert.equal(toggle.getAttribute("aria-label"), "Éteindre · Salon personnalisé");
  assert.equal(toggle.getAttribute("aria-pressed"), "true");
  toggle.click(); await settle(panel);
  assert.deepEqual(calls.find((call) => call.type === "halo/command"), { type: "halo/command", room_id: "lounge", command: "turn_off" });
  assert.ok(panel.shadowRoot!.querySelector(".welcome"));
  assert.equal(panel.shadowRoot!.querySelector(".savebar"), null);
  const search = panel.shadowRoot!.querySelector<HTMLInputElement>(".rail-search input")!;
  search.value = "personnalise"; search.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  assert.deepEqual([...panel.shadowRoot!.querySelectorAll(".room-link")].map((link) => link.getAttribute("aria-label")), ["Salon personnalisé"]);
  search.value = "introuvable"; search.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  assert.equal(panel.shadowRoot!.querySelectorAll(".room-link").length, 0);
  assert.equal(calls.some((call) => call.type === "halo/save"), false);
});

test("room drafts survive subsection, room and top navigation before saving once", async () => {
  const { panel, calls } = await mount();
  await openRoom(panel, "Automatisation");
  const delay = inputByLabel(panel, "Délai d’absence");
  delay.value = "27"; delay.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  await selectRoomTab(panel, "Pilotage");
  assert.equal(button(panel, "Créer une scène").disabled, true);
  assert.ok(panel.shadowRoot!.querySelector(".savebar"));
  await openRoom(panel, "Pilotage", "Cuisine");
  assert.ok(button(panel, "Configurer la pièce"));
  button(panel, "Réglages globaux").click(); await settle(panel);
  assert.ok(panel.shadowRoot!.querySelector(".global-settings"));
  button(panel, "Pièces").click(); await settle(panel);
  await openRoom(panel, "Automatisation");
  assert.equal(inputByLabel(panel, "Délai d’absence").value, "27");
  assert.equal(calls.some((call) => call.type === "halo/save"), false);
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  const saves = calls.filter((call) => call.type === "halo/save");
  assert.equal(saves.length, 1);
  assert.equal((saves[0].config as Snapshot["config"]).rooms.lounge.absence_delay, 27);
  assert.equal((saves[0].config as Snapshot["config"]).rooms.kitchen, undefined);
});

test("the global presence return window saves zero and fractional durations through the shared draft", async () => {
  const { panel, calls, hass } = await mount();
  button(panel, "Réglages globaux").click(); await settle(panel);
  const label = "Délai de protection de présence (secondes)";
  assert.equal(inputByLabel(panel, label).value, "30");
  assert.match(panel.shadowRoot!.textContent!, /uniquement les pièces où l’extinction sur forte luminosité est désactivée/);
  assert.match(panel.shadowRoot!.textContent!, /Zéro désactive le rallumage rapide/);
  for (const value of ["0", "45.5", "604800"]) {
    const field = inputByLabel(panel, label);
    field.value = value; field.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
    assert.equal(field.checkValidity(), true);
    button(panel, "Pièces").click(); await settle(panel);
    button(panel, "Réglages globaux").click(); await settle(panel);
    assert.equal(inputByLabel(panel, label).value, value, "Navigation preserves the unsaved value");
    button(panel, "Enregistrer les modifications").click(); await settle(panel);
    const saved = calls.filter((call) => call.type === "halo/save").at(-1)!;
    assert.equal((saved.config as Snapshot["config"]).presence_return_window, Number(value));
    assert.equal(panel.shadowRoot!.querySelector(".savebar"), null);
  }
  panel.hass = { ...hass, locale: { language: "en" } }; await settle(panel);
  assert.equal(inputByLabel(panel, "Presence protection delay (seconds)").value, "604800");
  assert.match(panel.shadowRoot!.textContent!, /Zero disables quick turn-on/);
});

test("the global presence return window rejects missing, negative, excessive and non-finite values", async () => {
  const { panel, calls } = await mount();
  button(panel, "Réglages globaux").click(); await settle(panel);
  const label = "Délai de protection de présence (secondes)";
  for (const value of ["", "-1", "604800.1", "1e309"]) {
    const field = inputByLabel(panel, label);
    field.value = value; field.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
    assert.equal(field.checkValidity(), false, `${value} must be rejected`);
    for (const target of [button(panel, "Enregistrer les modifications"), button(panel, "Pièces")]) {
      target.click(); await settle(panel);
      assert.ok(panel.shadowRoot!.querySelector(".global-settings"));
      assert.equal(panel.shadowRoot!.activeElement, field);
    }
    assert.equal(calls.some((call) => call.type === "halo/save"), false);
    button(panel, "Abandonner les modifications").click(); await settle(panel);
    assert.equal(inputByLabel(panel, label).value, "30");
    assert.equal(panel.shadowRoot!.querySelector(".savebar"), null);
  }
});

test("the global presence return window disappears when administrator rights are lost", async () => {
  const { panel, emit, calls } = await mount();
  button(panel, "Réglages globaux").click(); await settle(panel);
  assert.ok(inputByLabel(panel, "Délai de protection de présence"));
  emit(fixture(false)); await settle(panel);
  assert.equal(panel.shadowRoot!.querySelector(".global-settings"), null);
  assert.ok(!panel.shadowRoot!.textContent!.includes("Délai de protection de présence"));
  assert.ok(![...panel.shadowRoot!.querySelectorAll("button")].some((item) => item.textContent?.trim() === "Réglages globaux"));
  assert.equal(calls.some((call) => call.type === "halo/save"), false);
});

test("an invalid room field stays visible and focused instead of being lost by any navigation", async () => {
  const { panel, calls } = await mount();
  await openRoom(panel, "Automatisation");
  const delay = inputByLabel(panel, "Délai d’absence");
  delay.value = "-1"; delay.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  assert.equal(delay.checkValidity(), false);
  for (const target of [roomTab(panel, "Pilotage"), panel.shadowRoot!.querySelector<HTMLButtonElement>('.room-link[aria-label="Cuisine"]')!, button(panel, "Réglages globaux"), button(panel, "Enregistrer les modifications")]) {
    target.click(); await settle(panel);
    assert.equal(roomTab(panel, "Automatisation").getAttribute("aria-selected"), "true");
    assert.equal(panel.shadowRoot!.activeElement, delay);
    assert.equal(delay.value, "-1");
  }
  assert.equal(calls.some((call) => call.type === "halo/save"), false);
  delay.value = "12"; delay.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  await selectRoomTab(panel, "Pilotage");
  assert.equal(roomTab(panel, "Pilotage").getAttribute("aria-selected"), "true");
});

test("discarding an invalid number restores the saved control value and releases navigation", async () => {
  const { panel, calls } = await mount();
  await openRoom(panel, "Automatisation");
  const delay = inputByLabel(panel, "Délai d’absence");
  const original = delay.value;
  delay.value = "-1"; delay.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  assert.equal(panel.shadowRoot!.activeElement, delay);
  button(panel, "Abandonner les modifications").click(); await settle(panel);
  assert.equal(inputByLabel(panel, "Délai d’absence").value, original);
  assert.equal(inputByLabel(panel, "Délai d’absence").checkValidity(), true);
  assert.equal(panel.shadowRoot!.querySelector(".savebar"), null);
  await selectRoomTab(panel, "Pilotage");
  assert.equal(roomTab(panel, "Pilotage").getAttribute("aria-selected"), "true");
  assert.equal(calls.some((call) => call.type === "halo/save"), false);
});

test("profile details preserve separate drafts and block leaving an invalid solar range", async () => {
  const snapshot = fixture();
  snapshot.config.profiles.first = newProfile("first", "Chaud");
  snapshot.config.profiles.second = newProfile("second", "Clair");
  const { panel, calls } = await mount(true, snapshot);
  button(panel, "Profils de lumière naturelle").click(); await settle(panel);
  const profileLinks = () => [...panel.shadowRoot!.querySelectorAll<HTMLButtonElement>(".profile-link")];
  assert.equal(profileLinks()[0].getAttribute("aria-current"), "page");
  const name = inputByLabel(panel, "Nom");
  name.value = "Chaud personnalisé"; name.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  profileLinks()[1].click(); await settle(panel);
  assert.equal(panel.shadowRoot!.querySelectorAll(".profile").length, 1);
  assert.equal(inputByLabel(panel, "Nom").value, "Clair");
  assert.equal(profileLinks()[1].getAttribute("aria-current"), "page");
  profileLinks()[0].click(); await settle(panel);
  assert.equal(inputByLabel(panel, "Nom").value, "Chaud personnalisé");
  const advanced = panel.shadowRoot!.querySelector<HTMLDetailsElement>("details.profile-advanced")!;
  assert.equal(advanced.open, false);
  const high = inputByLabel(panel, "Hauteur solaire haute");
  high.value = "-30"; high.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  for (const target of [profileLinks()[1], button(panel, "Nouveau profil"), button(panel, "Pièces"), button(panel, "Enregistrer les modifications")]) {
    target.click(); await settle(panel);
    assert.equal(inputByLabel(panel, "Nom").value, "Chaud personnalisé");
    assert.equal(panel.shadowRoot!.activeElement, high);
    assert.equal(advanced.open, true, "Invalid numerical settings are revealed before focusing their field");
    assert.equal(profileLinks().length, 2);
  }
  assert.equal(calls.some((call) => call.type === "halo/save"), false);
  high.value = "40"; high.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  profileLinks()[1].click(); await settle(panel);
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  const config = calls.find((call) => call.type === "halo/save")!.config as Snapshot["config"];
  assert.equal(config.profiles.first.name, "Chaud personnalisé");
  assert.equal(config.profiles.first.morning.brightness.high_elevation, 40);
  assert.equal(config.profiles.second.name, "Clair");
});

test("losing admin rights removes the selected configuration section while room control stays available", async () => {
  const { panel, emit, calls } = await mount();
  await openRoom(panel, "Automatisation");
  assert.ok(picker(panel, "Entité de présence"));
  emit(fixture(false)); await settle(panel);
  assert.deepEqual([...panel.shadowRoot!.querySelectorAll('[role="tab"]')].map((tab) => tab.textContent?.trim()), ["Pilotage"]);
  assert.equal(panel.shadowRoot!.querySelectorAll(".room-panel input, .room-panel select, .room-panel halo-entity-picker").length, 0);
  assert.equal(panel.shadowRoot!.querySelector(".create-scene, .import-scene"), null);
  button(panel, "Allumer").click(); await settle(panel);
  assert.ok(calls.some((call) => call.type === "halo/command" && call.command === "turn_on"));
});

test("scene editing locks workspace navigation and returns focus to the correct room action", async () => {
  const { panel } = await mount();
  await openRoom(panel);
  for (const action of ["Régler", "Créer une scène"]) {
    button(panel, action).click(); await settle(panel);
    assert.ok([...panel.shadowRoot!.querySelectorAll<HTMLButtonElement>(".room-link, .quick-toggle, .top-nav button")].every((item) => item.disabled));
    assert.equal(panel.shadowRoot!.querySelector('[role="tablist"]'), null);
    button(panel, "Annuler").click(); await settle(panel);
    assert.equal(roomTab(panel, "Pilotage").getAttribute("aria-selected"), "true");
    assert.equal(panel.shadowRoot!.activeElement, action === "Créer une scène" ? panel.shadowRoot!.querySelector(".add-scene") : button(panel, action));
  }
});

test("non-admins can control and run scenes but see no configuration actions", async () => {
  const { panel, calls } = await mount(false);
  assert.equal([...panel.shadowRoot!.querySelectorAll("button")].some((item) => item.textContent?.includes("Réglages globaux")), false);
  await openRoom(panel);
  button(panel, "Allumer").click();
  await settle(panel);
  assert.deepEqual(calls.find((call) => call.type === "halo/command"), { type: "halo/command", room_id: "lounge", command: "turn_on" });
  assert.deepEqual([...panel.shadowRoot!.querySelectorAll('[role="tab"]')].map((tab) => tab.textContent?.trim()), ["Pilotage"]);
  assert.equal(panel.shadowRoot!.querySelectorAll(".room-panel input, .room-panel select, .room-panel halo-entity-picker").length, 0);
  button(panel, "Lancer").click();
  await settle(panel);
  assert.ok(calls.some((call) => call.type === "halo/command" && call.scene_id === "cinema"));
  assert.equal([...panel.shadowRoot!.querySelectorAll("button")].some((item) => item.textContent?.includes("Créer une scène")), false);
  assert.equal([...panel.shadowRoot!.querySelectorAll("button")].some((item) => item.textContent?.includes("Importer depuis Home Assistant")), false);
});

test("configuring a room is explicit, preserves safe defaults and sends the draft revision", async () => {
  const { panel, calls } = await mount();
  await openRoom(panel, "Pilotage", "Cuisine");
  button(panel, "Configurer la pièce").click();
  await settle(panel);
  const freeLight = [...panel.shadowRoot!.querySelectorAll<HTMLLabelElement>("label.check")].find((label) => label.textContent?.includes("Lampe libre"))!.querySelector<HTMLInputElement>("input")!;
  freeLight.checked = true;
  freeLight.dispatchEvent(new Event("change", { bubbles: true }));
  await settle(panel);
  button(panel, "Enregistrer les modifications").click();
  await settle(panel);
  const save = calls.find((call) => call.type === "halo/save")!;
  assert.equal(save.revision, 7);
  const room = (save.config as Snapshot["config"]).rooms.kitchen;
  assert.deepEqual(room.lights, ["light.extra"]);
  assert.equal(room.automation_enabled, false);
  assert.equal("allow_off_during_pause" in room, false);
  assert.equal("manual_pause" in room, false);
});

test("new remote configuration does not overwrite unsaved changes and disables stale save", async () => {
  const { panel, emit, calls } = await mount();
  await openRoom(panel, "Pilotage", "Cuisine");
  button(panel, "Configurer la pièce").click();
  await settle(panel);
  emit({ ...fixture(), revision: 8 });
  await settle(panel);
  assert.equal(button(panel, "Enregistrer les modifications").disabled, true);
  assert.match(panel.shadowRoot!.textContent!, /configuration a changé ailleurs/);
  assert.equal(calls.some((call) => call.type === "halo/save"), false);
  button(panel, "Abandonner les modifications").click();
  await settle(panel);
  assert.ok(button(panel, "Configurer la pièce"));
  assert.equal(panel.shadowRoot!.querySelector(".savebar"), null);
});

test("scene editing opens Home Assistant through its public action event after applying the initial preview and renewing its lock", async () => {
  const { panel, calls } = await mount();
  await openRoom(panel);
  button(panel, "Régler").click();
  await settle(panel);
  assert.ok(calls.some((call) => call.type === "halo/edit/begin" && call.room_id === "lounge"));
  assert.match(panel.shadowRoot!.textContent!, /Tu modifies les lampes réelles/);
  assert.equal(panel.shadowRoot!.querySelector<HaloEntityPicker>(".condition halo-entity-picker")!.value, "media_player.tv");
  const lamps = [...panel.shadowRoot!.querySelectorAll<HTMLButtonElement>(".scene-lamp")];
  assert.equal(lamps.length, 2);
  assert.match(lamps[0].textContent!, /Allumé · 50 % · Effet: Rainbow/);
  assert.match(lamps[1].textContent!, /Éteint/);
  assert.equal(panel.shadowRoot!.querySelector(".lamp, more-info-light, ha-more-info-dialog"), null);
  const actions: CustomEvent[] = [];
  panel.addEventListener("hass-action", (event) => actions.push(event as CustomEvent));
  lamps[0].click();
  await settle(panel);
  const preview = calls.find((call) => call.type === "halo/edit/preview")!;
  assert.equal(preview.token, "editor-token");
  assert.equal(calls.filter((call) => call.type === "halo/edit/preview").length, 1);
  assert.ok(calls.findIndex((call) => call.type === "halo/edit/touch") > calls.indexOf(preview));
  assert.equal(actions.length, 1);
  assert.equal(actions[0].bubbles, true);
  assert.equal(actions[0].composed, true);
  assert.deepEqual(actions[0].detail, { config: { entity: "light.colour", tap_action: { action: "more-info" } }, action: "tap" });
  button(panel, "Annuler").click();
  await settle(panel);
  assert.ok(calls.some((call) => call.type === "halo/edit/end" && call.save === false && call.token === "editor-token"));
  assert.equal(panel.shadowRoot!.querySelector(".editor"), null);
});

test("unmount unsubscribes state events", async () => {
  const context = await mount();
  context.panel.remove();
  assert.equal(context.unsubscribed, 1);
});

test("saving captures real native changes without sending a stale scene preview", async () => {
  const { panel, calls, hass } = await mount();
  await openRoom(panel);
  button(panel, "Régler").click(); await settle(panel);
  panel.shadowRoot!.querySelector<HTMLButtonElement>(".scene-lamp")!.click(); await settle(panel);
  panel.hass = { ...hass, states: { "light.colour": { state: "on", attributes: { brightness: 161, effect: "Candle", color_mode: "rgbww", rgbww_color: [1, 2, 3, 4, 5] } } } };
  await settle(panel);
  assert.match(panel.shadowRoot!.querySelector(".scene-lamp")!.textContent!, /63 % · Effet: Candle/);
  button(panel, "Enregistrer la scène").click();
  await settle(panel);
  const previewIndex = calls.findIndex((call) => call.type === "halo/edit/preview");
  const endIndex = calls.findIndex((call) => call.type === "halo/edit/end");
  assert.ok(previewIndex >= 0 && endIndex > previewIndex);
  assert.equal(calls.filter((call) => call.type === "halo/edit/preview").length, 1);
  assert.equal(calls[endIndex].capture, true);
  assert.equal(calls[endIndex].revision, 7);
});

test("cancelling clears pending preview work and does not send delayed lamp commands", async () => {
  const { panel, calls } = await mount();
  await openRoom(panel);
  button(panel, "Régler").click(); await settle(panel);
  button(panel, "Annuler").click(); await settle(panel);
  const endIndex = calls.findIndex((call) => call.type === "halo/edit/end");
  await new Promise((resolve) => setTimeout(resolve, 180));
  assert.equal(calls.slice(endIndex + 1).some((call) => call.type === "halo/edit/preview"), false);
});

test("a pending initial scene preview blocks native controls and saving until the preview is complete", async () => {
  let release!: () => void;
  const preview = new Promise<void>((resolve) => { release = resolve; });
  const { panel, calls } = await mount(true, fixture(), { preview: () => preview });
  const actions: Event[] = [];
  panel.addEventListener("hass-action", (event) => actions.push(event));
  await openRoom(panel);
  button(panel, "Régler").click(); await settle(panel);
  const lamp = panel.shadowRoot!.querySelector<HTMLButtonElement>(".scene-lamp")!;
  assert.equal(lamp.disabled, true);
  assert.equal(button(panel, "Enregistrer la scène").disabled, true);
  assert.match(panel.shadowRoot!.textContent!, /Application de l’aperçu/);
  lamp.click();
  assert.equal(actions.length, 0);
  assert.equal(calls.some((call) => call.type === "halo/edit/end"), false);
  release(); await settle(panel);
  assert.equal(lamp.disabled, false);
  lamp.click(); await settle(panel);
  assert.equal(actions.length, 1);
  button(panel, "Annuler").click(); await settle(panel);
});

test("an expired edit session never opens native controls after a failed lock renewal", async () => {
  let rejectTouch!: (error: unknown) => void;
  const touch = new Promise<void>((_, reject) => { rejectTouch = reject; });
  const { panel } = await mount(true, fixture(), { touch: () => touch });
  const actions: Event[] = [];
  panel.addEventListener("hass-action", (event) => actions.push(event));
  await openRoom(panel);
  button(panel, "Régler").click(); await settle(panel);
  panel.shadowRoot!.querySelector<HTMLButtonElement>(".scene-lamp")!.click(); await settle(panel);
  assert.equal(actions.length, 0);
  rejectTouch({ code: "invalid_edit" }); await settle(panel);
  assert.equal(actions.length, 0);
  assert.equal(panel.shadowRoot!.querySelector(".editor"), null);
});

test("a failed initial preview remains cancellable and cannot be saved as though it had applied", async () => {
  const { panel, calls } = await mount(true, fixture(), { preview: async () => { throw { code: "unknown_error" }; } });
  await openRoom(panel);
  button(panel, "Régler").click(); await settle(panel);
  assert.equal(button(panel, "Enregistrer la scène").disabled, true);
  assert.equal(panel.shadowRoot!.querySelector<HTMLButtonElement>(".scene-lamp")!.disabled, true);
  assert.equal(button(panel, "Annuler").disabled, false);
  button(panel, "Annuler").click(); await settle(panel);
  assert.ok(calls.some((call) => call.type === "halo/edit/end" && call.save === false));
});

test("new scenes preserve native light precision and effects without inventing states for unavailable lamps", async () => {
  const snapshot = fixture();
  const colour = snapshot.entities.find((entity) => entity.entity_id === "light.colour")!;
  colour.attributes = { brightness: 127, color_mode: "rgbww", rgbww_color: [1, 2, 3, 4, 5], rgb_color: [80, 90, 100], effect: "Candle" };
  snapshot.entities.find((entity) => entity.entity_id === "light.simple")!.state = "unavailable";
  const { panel, calls, hass } = await mount(true, snapshot);
  await openRoom(panel);
  button(panel, "Créer une scène").click(); await settle(panel);
  const lamps = [...panel.shadowRoot!.querySelectorAll<HTMLButtonElement>(".scene-lamp")];
  assert.equal(lamps.length, 2);
  assert.equal(lamps[1].disabled, true);
  assert.match(lamps[1].textContent!, /Indisponible/);
  assert.doesNotMatch(lamps[1].textContent!, /Éteint/);
  const name = panel.shadowRoot!.querySelector<HTMLInputElement>('.editor input[type="text"]')!;
  name.value = "Effet"; name.dispatchEvent(new Event("change", { bubbles: true })); await settle(panel);
  panel.hass = { ...hass, locale: { language: "en" } }; await settle(panel);
  assert.match(lamps[0].getAttribute("aria-label")!, /Open Home Assistant light controls/);
  assert.match(lamps[0].textContent!, /Effect: Candle/);
  button(panel, "Save scene").click(); await settle(panel);
  const end = calls.find((call) => call.type === "halo/edit/end")!;
  assert.equal(end.capture, true);
  assert.deepEqual(end.capture_entities, ["light.colour", "light.simple"]);
  assert.equal(calls.some((call) => call.type === "halo/edit/preview"), false);
  assert.deepEqual((end.scene as { lights: unknown }).lights, { "light.colour": { state: "on", brightness: 127, color_mode: "rgbww", rgbww_color: [1, 2, 3, 4, 5], effect: "Candle" } });
});

test("reattaching a panel opens a fresh subscription and abandons its old editor heartbeat", async () => {
  const context = await mount();
  await openRoom(context.panel);
  button(context.panel, "Régler").click(); await settle(context.panel);
  context.panel.remove();
  window.document.body.appendChild(context.panel as never);
  await settle(context.panel);
  assert.equal(context.unsubscribed, 1);
  assert.equal(context.calls.filter((call) => call.type === "halo/get").length, 2);
  assert.equal(context.panel.shadowRoot!.querySelector(".editor"), null);
});

test("leaving while a scene lock is pending cannot start a late preview or heartbeat", async () => {
  let release!: () => void;
  const begin = new Promise<void>((resolve) => { release = resolve; });
  const { panel, calls } = await mount(true, fixture(), { begin: () => begin });
  await openRoom(panel);
  button(panel, "Régler").click(); await settle(panel);
  panel.remove();
  release();
  await new Promise((resolve) => setTimeout(resolve, 10));
  assert.equal(calls.some((call) => call.type === "halo/edit/preview" || call.type === "halo/edit/touch"), false);
});

test("live state snapshots do not erase text while the user is still typing", async () => {
  const { panel, emit } = await mount();
  await openRoom(panel);
  button(panel, "Régler").click(); await settle(panel);
  const name = panel.shadowRoot!.querySelector<HTMLInputElement>('.editor input[type="text"]')!;
  name.value = "Nouvelle ambiance en cours";
  name.dispatchEvent(new Event("input", { bubbles: true }));
  emit({ ...fixture(), status: { lounge: { reason: "editing", is_on: false, available: true } } });
  await settle(panel);
  assert.equal(name.value, "Nouvelle ambiance en cours");
  button(panel, "Annuler").click(); await settle(panel);
});


function picker(panel: InstanceType<typeof HaloPanel>, label: string) {
  const found = [...panel.shadowRoot!.querySelectorAll<HaloEntityPicker>("halo-entity-picker")].find((item) => item.label === label);
  assert.ok(found, `Entity picker ${label} should exist`);
  return found;
}

async function searchEntity(control: HaloEntityPicker, query: string) {
  const input = control.shadowRoot!.querySelector<HTMLInputElement>("input")!;
  input.focus();
  input.value = query;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  await control.updateComplete;
  return input;
}

test("entity search matches names, accents and identifiers and commits only an explicit keyboard choice", async () => {
  const snapshot = fixture();
  snapshot.entities.push({ entity_id: "input_boolean.office_presence", name: "Présence Bureau", state: "on", attributes: {} });
  const { panel, calls, emit } = await mount(true, snapshot);
  await openRoom(panel, "Automatisation");
  const control = picker(panel, "Entité de présence");
  const input = await searchEntity(control, "presence office");
  assert.equal(control.shadowRoot!.querySelectorAll('[role="option"]').length, 1);
  assert.match(control.shadowRoot!.textContent!, /Présence Bureau/);
  input.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
  await control.updateComplete;
  assert.equal(input.getAttribute("aria-activedescendant"), "entity-option-0");
  input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
  await settle(panel);
  assert.equal(control.value, "input_boolean.office_presence");
  await searchEntity(control, "impossible");
  assert.match(control.shadowRoot!.textContent!, /Aucune entité correspondante/);
  emit({ ...snapshot, status: { lounge: { reason: "base" } } }); await settle(panel);
  assert.equal(input.value, "impossible");
  input.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
  await settle(panel);
  assert.equal(input.value, "Présence Bureau (input_boolean.office_presence)");
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  assert.equal((calls.find((call) => call.type === "halo/save")!.config as Snapshot["config"]).rooms.lounge.presence_entity_id, "input_boolean.office_presence");
});

test("entity pickers filter domains, support pointer focus transfer and preserve unavailable selections", async () => {
  const snapshot = fixture();
  snapshot.config.rooms.lounge.presence_entity_id = "binary_sensor.removed";
  snapshot.entities.push({ entity_id: "sensor.brightness", name: "Luminosité", state: "42", attributes: { unit_of_measurement: "%" } });
  const { panel } = await mount(true, snapshot);
  await openRoom(panel, "Automatisation");
  const presence = picker(panel, "Entité de présence");
  assert.match(presence.shadowRoot!.querySelector("label")!.textContent!, /Indisponible/);
  assert.match(presence.shadowRoot!.querySelector<HTMLInputElement>("input")!.value, /binary_sensor.removed/);
  const control = picker(panel, "Capteur de luminosité");
  const input = await searchEntity(control, "luminosite");
  const option = control.shadowRoot!.querySelector<HTMLElement>('[role="option"]')!;
  input.dispatchEvent(new FocusEvent("blur", { relatedTarget: null }));
  await control.updateComplete;
  assert.ok(control.shadowRoot!.contains(option));
  option.click(); await settle(panel);
  assert.equal(control.value, "sensor.brightness");
  assert.equal(control.entities.some((entity) => entity.entity_id === "media_player.tv"), false);
  control.shadowRoot!.querySelector<HTMLButtonElement>("button")!.click(); await settle(panel);
  assert.equal(control.value, null);
  button(panel, "Abandonner les modifications").click(); await settle(panel);
  button(panel, "Réglages globaux").click(); await settle(panel);
  const sun = picker(panel, "Entité soleil");
  await searchEntity(sun, "");
  assert.deepEqual(sun.entities.map((entity) => entity.entity_id), ["sun.sun"]);
});

test("required entity search rejects arbitrary typed text rather than saving an empty condition", async () => {
  const { panel, calls } = await mount();
  await openRoom(panel);
  button(panel, "Régler").click(); await settle(panel);
  const control = picker(panel, "Entité");
  const automation = panel.shadowRoot!.querySelector<HTMLDetailsElement>(".scene-automation")!;
  assert.equal(automation.open, false);
  control.shadowRoot!.querySelector<HTMLButtonElement>("button")!.click(); await settle(panel);
  await searchEntity(control, "media_player.typo");
  button(panel, "Enregistrer la scène").click(); await settle(panel);
  assert.equal(calls.some((call) => call.type === "halo/edit/end"), false);
  assert.match(panel.shadowRoot!.textContent!, /Vérifie les champs/);
  assert.equal(automation.open, true, "The invalid condition is revealed inside its collapsed section");
  assert.equal(panel.shadowRoot!.activeElement, control);
  button(panel, "Annuler").click(); await settle(panel);
});

test("brightness uses live sensor units without converting configured values", async () => {
  const snapshot = fixture();
  Object.assign(snapshot.config.rooms.lounge, { lux_entity_id: "sensor.daylight", lux_threshold: 30, lux_hysteresis: 5 });
  snapshot.entities.push({ entity_id: "sensor.daylight", name: "Daylight", state: "50", attributes: { unit_of_measurement: "%" } });
  const { panel, hass, calls } = await mount(true, snapshot);
  await openRoom(panel, "Automatisation");
  const contents = () => panel.shadowRoot!.textContent!.replace(/\s+/g, " ");
  assert.match(contents(), /Seuil d’allumage \(%\)/);
  assert.match(contents(), /Hystérésis \(%\)/);
  assert.match(contents(), /Seuil bas: 30 % · Seuil haut: 35 %/);
  panel.hass = { ...hass, states: { "sensor.daylight": { state: "100", attributes: { unit_of_measurement: "lx" } } } }; await settle(panel);
  assert.match(contents(), /Seuil d’allumage \(lx\)/);
  assert.match(contents(), /Seuil bas: 30 lx · Seuil haut: 35 lx/);
  panel.hass = { ...hass, states: { "sensor.daylight": { state: "100", attributes: {} } } }; await settle(panel);
  assert.match(contents(), /Ce capteur ne fournit pas d’unité/);
  assert.doesNotMatch(contents(), /\(lx\)|30 lx|30 %/);
  const delay = [...panel.shadowRoot!.querySelectorAll("label")].find((label) => label.textContent?.includes("Délai d’absence"))!.querySelector("input")!;
  delay.value = "10"; delay.dispatchEvent(new Event("change", { bubbles: true })); await settle(panel);
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  const saved = (calls.find((call) => call.type === "halo/save")!.config as Snapshot["config"]).rooms.lounge;
  assert.equal(saved.lux_threshold, 30); assert.equal(saved.lux_hysteresis, 5);
});

test("lights distinguish groups and membership and searchable associations keep hidden selections", async () => {
  const snapshot = fixture();
  snapshot.lights[0].is_group = false;
  snapshot.lights[0].member_of = ["light.office"];
  snapshot.lights[1].is_group = false;
  snapshot.lights[1].member_of = [];
  snapshot.lights.push({ entity_id: "light.office", name: "Bureau", area_id: "lounge", available: true,
    supported_color_modes: ["brightness"], supported_features: 0, is_group: true, group_members: ["light.colour"], member_of: [] });
  snapshot.config.profiles.day = newProfile("day", "Journée");
  snapshot.config.rooms.lounge.associations = [{ profile_id: "day", lights: ["light.colour"], brightness_offset: 0 }];
  const { panel, calls } = await mount(true, snapshot);
  await openRoom(panel, "Lumières");
  const list = panel.shadowRoot!.querySelector(".light-list")!;
  assert.match(list.textContent!.replace(/\s+/g, " "), /Lampe individuelle · Membre de: Bureau/);
  assert.match(list.textContent!.replace(/\s+/g, " "), /Lampe individuelle · Aucun groupe connu/);
  assert.match(list.textContent!.replace(/\s+/g, " "), /Groupe de lumières · Membres: Lampe couleur/);
  await selectRoomTab(panel, "Ambiances");
  const filter = panel.shadowRoot!.querySelector<HTMLInputElement>('.association input[type="search"]')!;
  filter.value = "absent"; filter.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  assert.equal(panel.shadowRoot!.querySelectorAll('.association input[type="checkbox"]').length, 0);
  filter.value = "light.colour"; filter.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  assert.equal(panel.shadowRoot!.querySelector<HTMLInputElement>('.association input[type="checkbox"]')!.checked, true);
  const offset = panel.shadowRoot!.querySelector<HTMLInputElement>('.association input[type="number"]')!;
  offset.value = "-20"; offset.dispatchEvent(new Event("change", { bubbles: true })); await settle(panel);
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  assert.deepEqual((calls.find((call) => call.type === "halo/save")!.config as Snapshot["config"]).rooms.lounge.associations[0].lights, ["light.colour"]);
});

test("profile and scene creation work on HTTP LAN without crypto.randomUUID", async () => {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, "crypto")!;
  const original = globalThis.crypto;
  Object.defineProperty(globalThis, "crypto", { configurable: true, value: { getRandomValues: original.getRandomValues.bind(original) } });
  try {
    const { panel, calls } = await mount();
    button(panel, "Profils de lumière naturelle").click(); await settle(panel);
    button(panel, "Nouveau profil").click(); await settle(panel);
    button(panel, "Nouveau profil").click(); await settle(panel);
    assert.equal(panel.shadowRoot!.querySelectorAll(".profile-list .profile-link").length, 2);
    assert.equal(panel.shadowRoot!.querySelectorAll(".profile").length, 1);
    button(panel, "Enregistrer les modifications").click(); await settle(panel);
    const profiles = (calls.find((call) => call.type === "halo/save")!.config as Snapshot["config"]).profiles;
    const ids = Object.keys(profiles);
    assert.equal(ids.length, 2); assert.notEqual(ids[0], ids[1]);
    button(panel, "Pièces").click(); await settle(panel);
    await openRoom(panel);
    button(panel, "Créer une scène").click(); await settle(panel);
    assert.ok(panel.shadowRoot!.querySelector(".editor"));
    const name = panel.shadowRoot!.querySelector<HTMLInputElement>('.editor input[type="text"]')!;
    name.value = "Test HTTP"; name.dispatchEvent(new Event("change", { bubbles: true })); await settle(panel);
    const filter = panel.shadowRoot!.querySelector<HTMLInputElement>('.editor input[type="search"]')!;
    filter.value = "simple"; filter.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
    assert.equal(panel.shadowRoot!.querySelectorAll(".scene-lamp").length, 1);
    button(panel, "Enregistrer la scène").click(); await settle(panel);
    const scene = calls.find((call) => call.type === "halo/edit/end")!.scene as { id: string; lights: Record<string, unknown> };
    assert.match(scene.id, /^[0-9a-f-]{36}$/);
    assert.deepEqual(Object.keys(scene.lights), ["light.colour", "light.simple"]);
  } finally { Object.defineProperty(globalThis, "crypto", descriptor); }
});


test("large entity catalogs stay searchable and outside clicks cancel only the transient query", async () => {
  const snapshot = fixture();
  snapshot.entities.push(...Array.from({ length: 240 }, (_, index) => ({ entity_id: `binary_sensor.device_${index}`, name: `Device ${index}`, state: "off", attributes: {} })));
  snapshot.config.rooms.lounge.presence_entity_id = "binary_sensor.device_239";
  const { panel, hass } = await mount(true, snapshot);
  await openRoom(panel, "Automatisation");
  const control = picker(panel, "Entité de présence");
  const input = await searchEntity(control, "device");
  assert.equal(control.shadowRoot!.querySelectorAll('[role="option"]').length, 100);
  assert.match(control.shadowRoot!.textContent!, /100 premiers résultats/);
  await searchEntity(control, "device_239");
  assert.equal(control.shadowRoot!.querySelectorAll('[role="option"]').length, 1);
  window.document.body.dispatchEvent(new window.Event("pointerdown", { bubbles: true, composed: true }));
  await control.updateComplete;
  assert.equal(input.getAttribute("aria-expanded"), "false");
  assert.equal(control.value, "binary_sensor.device_239");
  panel.hass = { ...hass, locale: { language: "de" } }; await settle(panel);
  await searchEntity(control, "unknown name");
  assert.match(control.shadowRoot!.textContent!, /No matching entities/);
});

function importFixture() {
  const snapshot = fixture();
  snapshot.entities.push({ entity_id: "scene.reading", name: "Lecture existante", state: "unknown", attributes: { id: "reading / 42" } },
    { entity_id: "scene.hue", name: "Ambiance Hue", state: "unknown", attributes: {} });
  return snapshot;
}

const importedScene: Scene = { id: "copied-scene", name: "Lecture existante", can_turn_on: false, conditions: null,
  lights: { "light.colour": { state: "on", brightness: 161, color_mode: "rgbw", rgbw_color: [1, 2, 3, 4], effect: "Candle" } } };

async function openImport(panel: InstanceType<typeof HaloPanel>) {
  await openRoom(panel);
  button(panel, "Importer depuis Home Assistant").click(); await settle(panel);
}

async function chooseScene(panel: InstanceType<typeof HaloPanel>, name = "Lecture existante") {
  const control = picker(panel, "Scène Home Assistant");
  await searchEntity(control, name);
  control.shadowRoot!.querySelector<HTMLElement>('[role="option"]')!.click();
  await settle(panel);
}

test("scene import reads configuration without controlling lights, previews retained lamps and saves an independent draft last", async () => {
  const source = { id: "reading / 42", name: "Lecture existante", entities: { "light.colour": importedScene.lights["light.colour"], "light.extra": "off", "media_player.tv": "off" } };
  const { panel, calls } = await mount(true, importFixture(), { api: async () => source, import: async () => ({ scene: importedScene, ignored_entities: 2 }) });
  await openImport(panel);
  assert.equal(panel.shadowRoot!.activeElement?.id, "import-title");
  const control = picker(panel, "Scène Home Assistant");
  assert.ok(control.entities.every((entity) => entity.entity_id.startsWith("scene.")));
  await chooseScene(panel);
  assert.doesNotMatch(control.shadowRoot!.textContent!, /Indisponible/);
  assert.deepEqual(calls.find((call) => call.type === "api"), { type: "api", method: "GET", path: "config/scene/config/reading%20%2F%2042" });
  assert.deepEqual(calls.find((call) => call.type === "halo/scene/import"), { type: "halo/scene/import", room_id: "lounge", config: source });
  assert.match(panel.shadowRoot!.querySelector(".import-lights")!.textContent!, /Lampe couleur.*light.colour/);
  assert.doesNotMatch(panel.shadowRoot!.querySelector(".import-lights")!.textContent!, /simple|extra|media_player/);
  assert.match(panel.shadowRoot!.textContent!, /Entités ignorées: 2/);
  assert.equal(panel.shadowRoot!.querySelector(".savebar"), null);
  const name = panel.shadowRoot!.querySelector<HTMLInputElement>('.scene-import input[type="text"]')!;
  name.value = "Lecture Halo"; name.dispatchEvent(new Event("input", { bubbles: true }));
  button(panel, "Ajouter au brouillon de la pièce").click(); await settle(panel);
  assert.equal(panel.shadowRoot!.querySelector(".scene-import"), null);
  assert.match(panel.shadowRoot!.querySelector(".savebar")!.textContent!, /non enregistrées/);
  assert.equal(roomTab(panel, "Pilotage").getAttribute("aria-selected"), "true");
  assert.equal((panel.shadowRoot!.activeElement as HTMLElement).dataset.sceneId, "copied-scene");
  assert.deepEqual([...panel.shadowRoot!.querySelectorAll(".scene-row strong")].map((item) => item.textContent), ["Cinéma perso", "Lecture Halo"]);
  const runButtons = () => [...panel.shadowRoot!.querySelectorAll<HTMLButtonElement>(".scene-row button")].filter((item) => item.textContent === "Lancer");
  assert.ok(runButtons().every((item) => item.disabled));
  assert.equal(calls.some((call) => call.type === "halo/save" || String(call.type).startsWith("halo/edit") || call.type === "halo/command"), false);
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  const scenes = (calls.find((call) => call.type === "halo/save")!.config as Snapshot["config"]).rooms.lounge.scenes;
  assert.deepEqual(scenes[1], { ...importedScene, name: "Lecture Halo" });
  assert.ok(runButtons().every((item) => !item.disabled));
  assert.equal(source.name, "Lecture existante");
  assert.equal(importedScene.name, "Lecture existante");
});

test("cancelling and discarding imported scenes leave the original room intact", async () => {
  const { panel, calls } = await mount(true, importFixture(), { api: async () => ({}), import: async () => ({ scene: importedScene, ignored_entities: 0 }) });
  await openImport(panel); await chooseScene(panel);
  button(panel, "Annuler").click(); await settle(panel);
  assert.equal(panel.shadowRoot!.querySelector(".savebar"), null);
  assert.equal(panel.shadowRoot!.querySelectorAll(".scene-row").length, 1);
  assert.equal(panel.shadowRoot!.activeElement?.className, "add-scene");
  button(panel, "Importer depuis Home Assistant").click(); await settle(panel); await chooseScene(panel);
  button(panel, "Ajouter au brouillon de la pièce").click(); await settle(panel);
  button(panel, "Abandonner les modifications").click(); await settle(panel);
  assert.equal(panel.shadowRoot!.querySelectorAll(".scene-row").length, 1);
  assert.equal(calls.some((call) => call.type === "halo/save" || call.type === "halo/command"), false);
});

test("a typed import name survives state refreshes and is confirmed without requiring a blur event", async () => {
  const { panel, emit, calls } = await mount(true, importFixture(), { api: async () => ({}), import: async () => ({ scene: importedScene, ignored_entities: 0 }) });
  await openImport(panel); await chooseScene(panel);
  const name = panel.shadowRoot!.querySelector<HTMLInputElement>('.scene-import input[type="text"]')!;
  name.focus();
  name.value = "Lecture Halo saisie";
  name.dispatchEvent(new Event("input", { bubbles: true }));
  await settle(panel);
  emit({ ...importFixture(), status: { lounge: { reason: "absence", is_on: false, available: true } } });
  await settle(panel);
  assert.equal(name.value, "Lecture Halo saisie");
  assert.equal(panel.shadowRoot!.activeElement, name);
  button(panel, "Ajouter au brouillon de la pièce").click(); await settle(panel);
  assert.deepEqual([...panel.shadowRoot!.querySelectorAll(".scene-row strong")].map((item) => item.textContent), ["Cinéma perso", "Lecture Halo saisie"]);
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  const scenes = (calls.find((call) => call.type === "halo/save")!.config as Snapshot["config"]).rooms.lounge.scenes;
  assert.equal(scenes.at(-1)!.name, "Lecture Halo saisie");
});

test("unreadable scenes, empty intersections and invalid retained settings show explicit errors without a draft", async () => {
  for (const [failure, expected] of [
    [{ status_code: 404 }, /configuration de cette scène n’est pas accessible/],
    [{ code: "no_matching_lights" }, /aucune lampe explicitement sélectionnée/],
    [{ code: "invalid_config", message: "light.colour: invalid brightness" }, /light.colour: invalid brightness/],
    [{ status_code: 403 }, /Seul un administrateur/],
    [new Error("network"), /La scène n’a pas pu être lue/],
  ] as const) {
    const backendError = "code" in failure;
    const { panel, calls } = await mount(true, importFixture(), {
      api: async () => { if (!backendError) throw failure; return {}; },
      import: async () => { throw failure; },
    });
    await openImport(panel);
    await chooseScene(panel, "Ambiance Hue");
    assert.match(panel.shadowRoot!.textContent!, /configuration de cette scène n’est pas accessible/);
    assert.equal(calls.some((call) => call.type === "api"), false);
    await chooseScene(panel);
    assert.match(panel.shadowRoot!.textContent!, expected);
    assert.equal(button(panel, "Ajouter au brouillon de la pièce").disabled, true);
    assert.equal(panel.shadowRoot!.querySelector(".savebar"), null);
    panel.remove();
  }
});

test("an import cannot confirm against a changed room revision or after losing administrator rights", async () => {
  for (const update of [{ revision: 8 }, { is_admin: false }]) {
    const { panel, emit, calls } = await mount(true, importFixture(), { api: async () => ({}), import: async () => ({ scene: importedScene, ignored_entities: 0 }) });
    await openImport(panel); await chooseScene(panel);
    const confirm = button(panel, "Ajouter au brouillon de la pièce");
    emit({ ...importFixture(), ...update }); await settle(panel);
    if (update.revision) {
      assert.equal(confirm.disabled, true);
      assert.match(panel.shadowRoot!.textContent!, /configuration de la pièce a changé/);
    } else assert.equal(panel.shadowRoot!.querySelector(".scene-import"), null);
    confirm.click(); await settle(panel);
    assert.equal(panel.shadowRoot!.querySelector(".savebar"), null);
    assert.equal(calls.some((call) => call.type === "halo/save"), false);
    panel.remove();
  }
});

test("late import results are ignored after cancellation, navigation, replacement selection and disconnection", async () => {
  for (const leave of ["cancel", "navigate", "select", "disconnect"] as const) {
    let release!: (value: unknown) => void;
    const response = new Promise<unknown>((resolve) => { release = resolve; });
    const { panel, calls } = await mount(true, importFixture(), { api: () => response, import: async () => ({ scene: importedScene, ignored_entities: 0 }) });
    await openImport(panel); await chooseScene(panel);
    assert.match(panel.shadowRoot!.textContent!, /Lecture des réglages/);
    if (leave === "cancel") button(panel, "Annuler").click();
    if (leave === "navigate") button(panel, "Pièces").click();
    if (leave === "select") await chooseScene(panel, "Ambiance Hue");
    if (leave === "disconnect") panel.remove();
    await settle(panel); release({}); await settle(panel);
    assert.equal(calls.some((call) => call.type === "halo/scene/import"), false);
    assert.equal(panel.shadowRoot!.querySelector(".savebar"), null);
    if (leave === "select") assert.match(panel.shadowRoot!.textContent!, /configuration de cette scène n’est pas accessible/);
    panel.remove();
  }
});

test("existing partial scenes preview and capture only included lamps while additions and exclusions are explicit", async () => {
  const snapshot = fixture();
  snapshot.config.rooms.lounge.scenes = [structuredClone(importedScene)];
  const { panel, calls } = await mount(true, snapshot);
  const actions: Event[] = [];
  panel.addEventListener("hass-action", (event) => actions.push(event));
  await openRoom(panel);
  button(panel, "Régler").click(); await settle(panel);
  assert.deepEqual(calls.find((call) => call.type === "halo/edit/preview")!.lights, importedScene.lights);
  const checks = [...panel.shadowRoot!.querySelectorAll<HTMLInputElement>(".scene-inclusion input")];
  assert.deepEqual(checks.map((input) => input.checked), [true, false]);
  const lamps = [...panel.shadowRoot!.querySelectorAll<HTMLButtonElement>(".scene-lamp")];
  assert.equal(lamps[1].disabled, true); lamps[1].click(); await settle(panel);
  assert.equal(actions.length, 0);
  checks[1].checked = true; checks[1].dispatchEvent(new Event("change", { bubbles: true })); await settle(panel);
  assert.equal(lamps[1].disabled, false);
  checks[0].checked = false; checks[0].dispatchEvent(new Event("change", { bubbles: true })); await settle(panel);
  assert.equal(lamps[0].disabled, true);
  button(panel, "Enregistrer la scène").click(); await settle(panel);
  const end = calls.find((call) => call.type === "halo/edit/end")!;
  assert.deepEqual(end.capture_entities, ["light.simple"]);
  assert.deepEqual((end.scene as HaloScene).lights, {});
  assert.equal(calls.filter((call) => call.type === "halo/edit/preview").length, 1);
});

test("a normalization response cannot revive an import after its room changes", async () => {
  let release!: (value: { scene: Scene; ignored_entities: number }) => void;
  const response = new Promise<{ scene: Scene; ignored_entities: number }>((resolve) => { release = resolve; });
  const { panel, emit, calls } = await mount(true, importFixture(), { api: async () => ({}), import: () => response });
  await openImport(panel); await chooseScene(panel);
  assert.ok(calls.some((call) => call.type === "halo/scene/import"));
  emit({ ...importFixture(), revision: 8 }); await settle(panel);
  release({ scene: importedScene, ignored_entities: 0 }); await settle(panel);
  assert.equal(button(panel, "Ajouter au brouillon de la pièce").disabled, true);
  assert.equal(panel.shadowRoot!.querySelector(".import-lights"), null);
  assert.match(panel.shadowRoot!.textContent!, /configuration de la pièce a changé/);
  assert.equal(calls.some((call) => call.type === "halo/save" || call.type === "halo/command"), false);
});

test("resaving a partial scene retains remembered settings for its unavailable selected lamp", async () => {
  const snapshot = fixture();
  snapshot.config.rooms.lounge.scenes = [structuredClone(importedScene)];
  snapshot.entities.find((entity) => entity.entity_id === "light.colour")!.state = "unavailable";
  const { panel, calls } = await mount(true, snapshot);
  await openRoom(panel);
  button(panel, "Régler").click(); await settle(panel);
  assert.deepEqual([...panel.shadowRoot!.querySelectorAll<HTMLInputElement>(".scene-inclusion input")].map((input) => input.checked), [true, false]);
  button(panel, "Enregistrer la scène").click(); await settle(panel);
  const end = calls.find((call) => call.type === "halo/edit/end")!;
  assert.deepEqual(end.capture_entities, ["light.colour"]);
  assert.deepEqual((end.scene as HaloScene).lights, importedScene.lights);
});

const linkedScene: HomeAssistantScene = { type: "home_assistant", id: "native-scene", name: "Ambiance liée", scene_entity_id: "scene.reading", conditions: null, can_turn_on: false };
const nativeInspection: SceneInspection = { entity_id: "scene.reading", name: "Lecture existante", available: true, complete: true,
  lights: ["light.colour", "light.extra"], outside_lights: ["light.extra"], missing_lights: ["light.simple"], other_entities: ["media_player.tv"], blocked: false };

async function openLink(panel: InstanceType<typeof HaloPanel>) {
  await openRoom(panel);
  const menu = panel.shadowRoot!.querySelector<HTMLDetailsElement>(".scene-add-menu")!;
  menu.open = true;
  assert.deepEqual([...menu.querySelectorAll("button")].map((item) => item.textContent?.trim()),
    ["Créer une scène", "Utiliser une scène Home Assistant", "Importer depuis Home Assistant"]);
  button(panel, "Utiliser une scène Home Assistant").click();
  await settle(panel);
}

function setText(input: HTMLInputElement, value: string) {
  input.value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

test("linking an HA scene inspects its complete scope and adds a reference last without controlling lights or copying its settings", async () => {
  const snapshot = importFixture();
  snapshot.entities.push({ entity_id: "scene.halo_scene", name: "Scène Halo", state: "unknown", platform: "halo", attributes: {} });
  const { panel, calls } = await mount(true, snapshot, { inspect: async () => structuredClone(nativeInspection) });
  await openLink(panel);
  assert.equal(panel.shadowRoot!.activeElement?.id, "link-title");
  const selector = picker(panel, "Scène Home Assistant");
  assert.ok(selector.entities.every((entity) => entity.entity_id.startsWith("scene.") && entity.entity_id !== "scene.halo_scene"));
  await chooseScene(panel);
  assert.doesNotMatch(selector.shadowRoot!.textContent!, /Indisponible/);
  assert.deepEqual(calls.filter((call) => call.type === "halo/scene/inspect"), [{ type: "halo/scene/inspect", room_id: "lounge", entity_id: "scene.reading" }]);
  const scope = panel.shadowRoot!.querySelector(".scene-scope")!.textContent!;
  assert.match(scope, /Lampes connues hors de cette pièce.*light.extra/s);
  assert.match(scope, /Lampes de la pièce absentes.*light.simple/s);
  assert.match(scope, /Autres équipements connus.*media_player.tv/s);
  assert.doesNotMatch(scope, /comparaison est incomplète/);
  assert.equal(inputByLabel(panel, "Nom de la scène").value, "Lecture existante");
  setText(inputByLabel(panel, "Nom de la scène"), "Ambiance Hue personnalisée");
  button(panel, "Ajouter au brouillon de la pièce").click(); await settle(panel);
  assert.equal(panel.shadowRoot!.querySelector(".scene-link"), null);
  assert.ok(panel.shadowRoot!.querySelector(".savebar"));
  const row = panel.shadowRoot!.querySelector(".scene-row:last-child")!;
  assert.match(row.textContent!, /Ambiance Hue personnalisée.*Home Assistant · scene.reading/s);
  assert.doesNotMatch(row.textContent!, /0 lumières/);
  assert.equal(calls.some((call) => call.type === "api" || call.type === "halo/save" || String(call.type).startsWith("halo/edit") || call.type === "halo/command"), false);
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  const saved = (calls.find((call) => call.type === "halo/save")!.config as Snapshot["config"]).rooms.lounge.scenes;
  assert.equal(saved.length, 2);
  assert.deepEqual(saved[1], { type: "home_assistant", id: saved[1].id, name: "Ambiance Hue personnalisée", scene_entity_id: "scene.reading", conditions: null, can_turn_on: false });
  assert.equal(calls.some((call) => String(call.type).startsWith("halo/edit") || call.type === "halo/command"), false);
});

test("opaque provider scenes can be linked without pretending their unknown scope is exhaustive", async () => {
  const { panel, calls } = await mount(true, importFixture(), { inspect: async () => ({ ...nativeInspection, entity_id: "scene.hue", name: "Ambiance Hue", complete: false, lights: [], outside_lights: [], missing_lights: [], other_entities: [] }) });
  await openLink(panel); await chooseScene(panel, "Ambiance Hue");
  assert.match(panel.shadowRoot!.querySelector(".scene-scope")!.textContent!, /comparaison est incomplète/);
  assert.equal(panel.shadowRoot!.querySelectorAll(".scope-warning").length, 0);
  assert.equal(button(panel, "Ajouter au brouillon de la pièce").disabled, false);
  button(panel, "Ajouter au brouillon de la pièce").click(); await settle(panel);
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  assert.equal(((calls.find((call) => call.type === "halo/save")!.config as Snapshot["config"]).rooms.lounge.scenes[1] as HomeAssistantScene).scene_entity_id, "scene.hue");
});

test("editing a linked scene preserves its ID and priority and changes metadata without a live session", async () => {
  const snapshot = importFixture();
  snapshot.config.rooms.lounge.scenes.unshift(structuredClone(linkedScene));
  const { panel, calls } = await mount(true, snapshot, { inspect: async () => structuredClone(nativeInspection) });
  await openRoom(panel);
  panel.shadowRoot!.querySelector<HTMLButtonElement>('.edit-scene[data-scene-id="native-scene"]')!.click(); await settle(panel);
  assert.equal(inputByLabel(panel, "Nom de la scène").value, "Ambiance liée");
  assert.equal(panel.shadowRoot!.querySelector(".editor"), null);
  setText(inputByLabel(panel, "Nom de la scène"), "Cinéma natif");
  const mayTurnOn = inputByLabel(panel, "Cette scène peut allumer");
  mayTurnOn.checked = true; mayTurnOn.dispatchEvent(new Event("change", { bubbles: true }));
  button(panel, "Ajouter une condition").click(); await settle(panel);
  const condition = picker(panel, "Entité");
  await searchEntity(condition, "media_player.tv");
  condition.shadowRoot!.querySelector<HTMLElement>('[role="option"]')!.click(); await settle(panel);
  button(panel, "Modifier dans le brouillon de la pièce").click(); await settle(panel);
  assert.equal((panel.shadowRoot!.activeElement as HTMLElement).dataset.sceneId, "native-scene");
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  const scenes = (calls.find((call) => call.type === "halo/save")!.config as Snapshot["config"]).rooms.lounge.scenes;
  assert.deepEqual(scenes[0], { ...linkedScene, name: "Cinéma natif", can_turn_on: true, conditions: { type: "state", entity_id: "media_player.tv", state: "on" } });
  assert.equal(scenes[1].id, "cinema");
  assert.equal(calls.some((call) => String(call.type).startsWith("halo/edit") || call.type === "halo/command"), false);
});

test("linked scene drafts are cancelled or discarded without changing saved configuration", async () => {
  const { panel, calls } = await mount(true, importFixture(), { inspect: async () => structuredClone(nativeInspection) });
  await openLink(panel); await chooseScene(panel);
  setText(inputByLabel(panel, "Nom de la scène"), "Brouillon temporaire");
  assert.ok(button(panel, "Réglages globaux").disabled, "Close or confirm the metadata form before leaving it");
  button(panel, "Annuler").click(); await settle(panel);
  assert.equal(panel.shadowRoot!.activeElement?.className, "add-scene");
  assert.equal(panel.shadowRoot!.querySelector(".savebar"), null);
  await openLink(panel); await chooseScene(panel);
  button(panel, "Ajouter au brouillon de la pièce").click(); await settle(panel);
  button(panel, "Abandonner les modifications").click(); await settle(panel);
  assert.equal(panel.shadowRoot!.querySelectorAll(".scene-row").length, 1);
  assert.equal(calls.some((call) => call.type === "halo/save" || call.type === "halo/command"), false);
});

test("linked scene form rejects stale configuration and can reload after cancellation", async () => {
  const snapshot = importFixture();
  const { panel, calls, emit } = await mount(true, snapshot, { inspect: async () => structuredClone(nativeInspection) });
  await openLink(panel); await chooseScene(panel);
  const next = structuredClone(snapshot); next.revision++;
  next.config.rooms.lounge.scenes[0].name = "Modifié ailleurs";
  emit(next); await settle(panel);
  assert.match(panel.shadowRoot!.textContent!, /configuration de la pièce a changé pendant l’édition du lien/);
  assert.ok(button(panel, "Ajouter au brouillon de la pièce").disabled);
  button(panel, "Annuler").click(); await settle(panel);
  assert.match(panel.shadowRoot!.textContent!, /Modifié ailleurs/);
  assert.equal(calls.some((call) => call.type === "halo/save"), false);
  await openLink(panel); await chooseScene(panel);
  assert.equal(button(panel, "Ajouter au brouillon de la pièce").disabled, false);
});

test("known recursive and newly unavailable native sources cannot be linked, but an existing missing reference remains editable", async () => {
  for (const blocked of [true, false]) {
    const { panel } = await mount(true, importFixture(), { inspect: async () => ({ ...nativeInspection, blocked, available: blocked }) });
    await openLink(panel); await chooseScene(panel);
    assert.ok(button(panel, "Ajouter au brouillon de la pièce").disabled);
    assert.match(panel.shadowRoot!.textContent!, blocked ? /commandes récursives/ : /absente ou indisponible/);
    panel.remove();
  }
  const snapshot = fixture();
  snapshot.config.rooms.lounge.scenes = [structuredClone(linkedScene)];
  const { panel, calls } = await mount(true, snapshot, { inspect: async () => ({ ...nativeInspection, available: false, name: "scene.reading" }) });
  await openRoom(panel); button(panel, "Régler").click(); await settle(panel);
  assert.equal(picker(panel, "Scène Home Assistant").value, "scene.reading");
  assert.equal(inputByLabel(panel, "Nom de la scène").value, "Ambiance liée");
  setText(inputByLabel(panel, "Nom de la scène"), "Référence conservée");
  assert.equal(button(panel, "Modifier dans le brouillon de la pièce").disabled, false);
  button(panel, "Modifier dans le brouillon de la pièce").click(); await settle(panel);
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  assert.deepEqual((calls.find((call) => call.type === "halo/save")!.config as Snapshot["config"]).rooms.lounge.scenes[0], { ...linkedScene, name: "Référence conservée" });
});

test("late inspections do not overwrite a new source, a typed alias, cancellation, disconnection or lost administrator rights", async () => {
  for (const action of ["source", "alias", "cancel", "disconnect", "rights"] as const) {
    let release!: (value: SceneInspection) => void;
    const response = new Promise<SceneInspection>((resolve) => { release = resolve; });
    const snapshot = importFixture();
    const { panel, emit, calls } = await mount(true, snapshot, { inspect: (message) => message.entity_id === "scene.reading" ? response : Promise.resolve({ ...nativeInspection, entity_id: "scene.hue", name: "Ambiance Hue", complete: false }) });
    await openLink(panel); await chooseScene(panel);
    assert.ok(button(panel, "Ajouter au brouillon de la pièce").disabled);
    if (action === "source") await chooseScene(panel, "Ambiance Hue");
    if (action === "alias") setText(inputByLabel(panel, "Nom de la scène"), "Mon nom saisi");
    if (action === "cancel") button(panel, "Annuler").click();
    if (action === "disconnect") panel.remove();
    if (action === "rights") emit({ ...snapshot, is_admin: false });
    await settle(panel);
    release(structuredClone(nativeInspection)); await settle(panel);
    if (action === "source") assert.equal(inputByLabel(panel, "Nom de la scène").value, "Ambiance Hue");
    if (action === "alias") assert.equal(inputByLabel(panel, "Nom de la scène").value, "Mon nom saisi");
    if (action === "cancel" || action === "rights") assert.equal(panel.shadowRoot!.querySelector(".scene-link"), null);
    if (action === "rights") assert.equal(button(panel, "Pièces").disabled, false);
    assert.equal(calls.some((call) => call.type === "halo/save" || String(call.type).startsWith("halo/edit") || call.type === "halo/command"), false);
    panel.remove();
  }
});

test("inspection failures can be retried and changing sources preserves an explicit alias", async () => {
  let fail = true;
  const { panel, calls } = await mount(true, importFixture(), { inspect: async (message) => {
    if (fail) { fail = false; throw new Error("Offline"); }
    return { ...nativeInspection, entity_id: String(message.entity_id), name: message.entity_id === "scene.hue" ? "Ambiance Hue" : nativeInspection.name };
  } });
  await openLink(panel); await chooseScene(panel);
  assert.match(panel.shadowRoot!.textContent!, /périmètre de la scène n’a pas pu être vérifié/);
  assert.ok(button(panel, "Ajouter au brouillon de la pièce").disabled);
  button(panel, "Réessayer").click(); await settle(panel);
  assert.equal(button(panel, "Ajouter au brouillon de la pièce").disabled, false);
  setText(inputByLabel(panel, "Nom de la scène"), "Mon nom");
  await chooseScene(panel, "Ambiance Hue");
  assert.equal(inputByLabel(panel, "Nom de la scène").value, "Mon nom");
  assert.equal(calls.filter((call) => call.type === "halo/scene/inspect").length, 3);
  setText(inputByLabel(panel, "Nom de la scène"), "");
  button(panel, "Ajouter au brouillon de la pièce").click(); await settle(panel);
  assert.ok(panel.shadowRoot!.querySelector(".scene-link"));
  assert.equal(panel.shadowRoot!.querySelector(".savebar"), null);
});

test("linked scenes stay runnable for users through the existing room command and show localized automatic failures", async () => {
  const snapshot = importFixture(); snapshot.is_admin = false;
  snapshot.config.rooms.lounge.scenes = [structuredClone(linkedScene)];
  snapshot.status.lounge.scene_errors = { "native-scene": "external_scene_unavailable" };
  const { panel, hass, calls } = await mount(false, snapshot);
  await openRoom(panel);
  assert.equal(panel.shadowRoot!.querySelector(".scene-add-menu"), null);
  assert.equal(panel.shadowRoot!.querySelector(".edit-scene"), null);
  assert.match(panel.shadowRoot!.querySelector('.scenes-section [role="alert"]')!.textContent!, /Ambiance liée.*absente ou indisponible/s);
  button(panel, "Lancer").click(); await settle(panel);
  assert.deepEqual(calls.find((call) => call.type === "halo/command"), { type: "halo/command", room_id: "lounge", command: "scene", scene_id: "native-scene" });
  panel.hass = { ...hass, locale: { language: "de" } }; await settle(panel);
  assert.match(panel.shadowRoot!.querySelector('.scenes-section [role="alert"]')!.textContent!, /Ambiance liée.*missing or unavailable/s);
  assert.match(panel.shadowRoot!.querySelector(".scene-meta")!.textContent!, /Home Assistant · scene.reading/);
});

test("room membership changes prune Halo scene targets but preserve linked scenes and their priority controls", async () => {
  const snapshot = importFixture(); snapshot.config.rooms.lounge.scenes.push(structuredClone(linkedScene));
  const { panel, calls } = await mount(true, snapshot);
  await openRoom(panel, "Lumières");
  const lamp = [...panel.shadowRoot!.querySelectorAll<HTMLLabelElement>(".light-option label")].find((item) => item.textContent?.includes("light.colour"))!.querySelector<HTMLInputElement>("input")!;
  lamp.checked = false; lamp.dispatchEvent(new Event("change", { bubbles: true })); await settle(panel);
  await selectRoomTab(panel, "Pilotage");
  panel.shadowRoot!.querySelector<HTMLButtonElement>('[aria-label="Monter Ambiance liée"]')!.click(); await settle(panel);
  assert.equal(panel.shadowRoot!.querySelector(".scene-row strong")!.textContent, "Ambiance liée");
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  const room = (calls.find((call) => call.type === "halo/save")!.config as Snapshot["config"]).rooms.lounge;
  assert.deepEqual(room.lights, ["light.simple"]);
  assert.deepEqual(room.scenes[0], linkedScene);
  assert.deepEqual((room.scenes[1] as HaloScene).lights, { "light.simple": { state: "off" } });
  panel.shadowRoot!.querySelector<HTMLButtonElement>('[aria-label="Supprimer Ambiance liée"]')!.click(); await settle(panel);
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  assert.equal((calls.filter((call) => call.type === "halo/save").at(-1)!.config as Snapshot["config"]).rooms.lounge.scenes.length, 1);
  assert.equal(calls.some((call) => call.type === "halo/command" || String(call.type).startsWith("halo/edit")), false);
});

test("automation selectors show live raw values and units without changing the draft or commanding entities", async () => {
  const snapshot = fixture();
  Object.assign(snapshot.config.rooms.lounge, { presence_entity_id: "input_select.presence", presence_states: ["occupied_custom"], lux_entity_id: "sensor.daylight", lux_threshold: 30 });
  snapshot.entities.push(
    { entity_id: "input_select.presence", name: "Presence", state: "stale", attributes: {} },
    { entity_id: "sensor.daylight", name: "Daylight", state: "99", attributes: { unit_of_measurement: "lx" } },
  );
  const { panel, hass, calls } = await mount(true, snapshot);
  panel.hass = { ...hass, states: {
    "input_select.presence": { state: "occupied_custom", attributes: {} },
    "sensor.daylight": { state: "0", attributes: { unit_of_measurement: "lx" } },
  } };
  await openRoom(panel, "Automatisation");
  const presence = picker(panel, "Entité de présence");
  const lux = picker(panel, "Capteur de luminosité");
  const value = (control: HaloEntityPicker) => control.shadowRoot!.querySelector("#entity-current-value")?.textContent;
  assert.equal(value(presence), "Valeur actuelle: occupied_custom");
  assert.equal(value(lux), "Valeur actuelle: 0 lx");
  assert.equal(lux.shadowRoot!.querySelector("input")!.getAttribute("aria-describedby"), "entity-current-value");
  const threshold = inputByLabel(panel, "Seuil d’allumage");
  threshold.value = "42"; threshold.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  panel.hass = { ...hass, states: {
    "input_select.presence": { state: "absent_custom", attributes: {} },
    "sensor.daylight": { state: "12.5", attributes: { unit_of_measurement: "%" } },
  } }; await settle(panel);
  assert.equal(value(presence), "Valeur actuelle: absent_custom");
  assert.equal(value(lux), "Valeur actuelle: 12.5 %");
  assert.equal(threshold.value, "42", "Live readings leave the edited threshold intact");
  lux.shadowRoot!.querySelector<HTMLButtonElement>("button")!.click(); await settle(panel);
  assert.equal(value(lux), undefined);
  assert.equal(lux.shadowRoot!.querySelector("input")!.hasAttribute("aria-describedby"), false);
  assert.ok(calls.every((call) => call.type === "halo/get"), "Displaying values never saves or commands entities");
});

test("current sensor values distinguish unknown, unavailable and missing data and follow the panel language", async () => {
  const snapshot = fixture();
  Object.assign(snapshot.config.rooms.lounge, { presence_entity_id: "binary_sensor.presence", lux_entity_id: "sensor.daylight", lux_threshold: 30 });
  snapshot.entities.push(
    { entity_id: "binary_sensor.presence", name: "Presence", state: "on", attributes: {} },
    { entity_id: "sensor.daylight", name: "Daylight", state: "15", attributes: { unit_of_measurement: "lx" } },
  );
  const { panel, hass } = await mount(true, snapshot);
  panel.hass = { ...hass, states: undefined };
  await openRoom(panel, "Automatisation");
  const current = (label: string) => picker(panel, label).shadowRoot!.querySelector("#entity-current-value")?.textContent;
  assert.equal(current("Entité de présence"), "Valeur actuelle: on");
  assert.equal(current("Capteur de luminosité"), "Valeur actuelle: 15 lx");
  panel.hass = { ...hass, states: { "binary_sensor.presence": { state: "unknown", attributes: {} }, "sensor.daylight": { state: "unavailable", attributes: { unit_of_measurement: "lx" } } } }; await settle(panel);
  assert.equal(current("Entité de présence"), "Valeur actuelle: Inconnue");
  assert.equal(current("Capteur de luminosité"), "Valeur actuelle: Indisponible");
  panel.hass = { ...hass, locale: { language: "de" }, states: {} }; await settle(panel);
  assert.equal(current("Presence entity"), "Current value: Unavailable");
  assert.equal(current("Illuminance sensor"), "Current value: Unavailable", "Removed live entities never reuse stale snapshot values");
  panel.hass = { ...hass, states: { "sensor.daylight": { state: "0", attributes: {} } } }; await settle(panel);
  assert.equal(current("Capteur de luminosité"), "Valeur actuelle: 0");
});

function nightlightFixture() {
  const snapshot = fixture();
  snapshot.config.rooms.lounge.presence_entity_id = "binary_sensor.presence";
  snapshot.config.rooms.lounge.nightlight = { enabled: true, lights: { "light.colour": { state: "on", brightness: 30, color_mode: "rgbww", rgbww_color: [1, 2, 3, 4, 5], effect: "Candle" } } };
  return snapshot;
}

test("nightlight stays in Ambiences with five tabs, safe defaults and no live edits when toggling the draft", async () => {
  const snapshot = nightlightFixture();
  snapshot.config.rooms.lounge.nightlight.enabled = false;
  const { panel, calls } = await mount(true, snapshot);
  await openRoom(panel, "Ambiances");
  assert.equal(panel.shadowRoot!.querySelectorAll('[role="tab"]').length, 5);
  const section = panel.shadowRoot!.querySelector(".nightlight-section")!;
  assert.match(section.textContent!, /1 lampe · pendant l’absence/);
  assert.match(section.textContent!, /Sans capteur lumineux/);
  assert.equal(section.querySelector<HTMLDetailsElement>("details")!.open, false);
  const enabled = inputByLabel(panel, "Activer la veilleuse");
  assert.equal(enabled.disabled, false);
  enabled.checked = true; enabled.dispatchEvent(new Event("change", { bubbles: true })); await settle(panel);
  assert.equal(button(panel, "Configurer").disabled, true);
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  assert.equal((calls.find((call) => call.type === "halo/save")!.config as Snapshot["config"]).rooms.lounge.nightlight.enabled, true);
  assert.equal(calls.some((call) => String(call.type).startsWith("halo/edit") || call.type === "halo/command"), false);
  button(panel, "Réglages de présence et de luminosité").click(); await settle(panel);
  assert.equal(roomTab(panel, "Automatisation").getAttribute("aria-selected"), "true");
});

test("nightlight editing previews only stored lamps, preserves native capture and returns focus to Ambiences", async () => {
  const snapshot = nightlightFixture();
  const { panel, calls, hass } = await mount(true, snapshot);
  const actions: CustomEvent[] = [];
  panel.addEventListener("hass-action", (event) => actions.push(event as CustomEvent));
  await openRoom(panel, "Ambiances");
  button(panel, "Configurer").click(); await settle(panel);
  assert.equal(panel.shadowRoot!.querySelector(".scene-automation"), null);
  assert.equal(panel.shadowRoot!.querySelector('.editor input[type="text"]'), null);
  assert.deepEqual(calls.find((call) => call.type === "halo/edit/preview")!.lights, snapshot.config.rooms.lounge.nightlight.lights);
  assert.deepEqual([...panel.shadowRoot!.querySelectorAll<HTMLInputElement>(".scene-inclusion input")].map((input) => input.checked), [true, false]);
  panel.shadowRoot!.querySelector<HTMLButtonElement>(".scene-lamp")!.click(); await settle(panel);
  assert.deepEqual(actions[0].detail, { config: { entity: "light.colour", tap_action: { action: "more-info" } }, action: "tap" });
  panel.hass = { ...hass, states: { "light.colour": { state: "on", attributes: { brightness: 11, color_mode: "rgbww", rgbww_color: [5, 4, 3, 2, 1], effect: "Rainbow" } } } };
  await settle(panel);
  button(panel, "Enregistrer la veilleuse").click(); await settle(panel);
  const end = calls.find((call) => call.type === "halo/edit/end")!;
  assert.equal(end.target, "nightlight");
  assert.equal(end.scene, undefined);
  assert.equal(end.capture, true);
  assert.equal(end.revision, 7);
  assert.deepEqual(end.capture_entities, ["light.colour"]);
  assert.deepEqual(end.nightlight, snapshot.config.rooms.lounge.nightlight, "Stored settings remain the fallback; real native changes are captured by the server");
  assert.equal(calls.filter((call) => call.type === "halo/edit/preview").length, 1);
  assert.equal(roomTab(panel, "Ambiances").getAttribute("aria-selected"), "true");
  assert.equal(panel.shadowRoot!.activeElement, button(panel, "Configurer"));
});

test("new nightlight has explicit empty inclusion and cancellation closes the shared edit session", async () => {
  const { panel, calls } = await mount();
  await openRoom(panel, "Ambiances");
  assert.equal(inputByLabel(panel, "Activer la veilleuse").disabled, true);
  assert.match(panel.shadowRoot!.querySelector(".nightlight-section")!.textContent!, /Choisis une entité de présence/);
  button(panel, "Configurer").click(); await settle(panel);
  assert.deepEqual([...panel.shadowRoot!.querySelectorAll<HTMLInputElement>(".scene-inclusion input")].map((input) => input.checked), [false, false]);
  assert.equal(calls.some((call) => call.type === "halo/edit/preview"), false);
  button(panel, "Annuler").click(); await settle(panel);
  assert.deepEqual(calls.find((call) => call.type === "halo/edit/end"), { type: "halo/edit/end", room_id: "lounge", token: "editor-token", save: false });
  assert.equal(panel.shadowRoot!.querySelector(".editor"), null);
  assert.equal(roomTab(panel, "Ambiances").getAttribute("aria-selected"), "true");
  assert.equal(calls.some((call) => call.type === "halo/save"), false);
});

test("enabled nightlight cannot capture no included light or zero brightness, but keeps unavailable stored settings", async () => {
  const snapshot = nightlightFixture();
  const { panel, calls, hass } = await mount(true, snapshot);
  await openRoom(panel, "Ambiances"); button(panel, "Configurer").click(); await settle(panel);
  const included = panel.shadowRoot!.querySelector<HTMLInputElement>(".scene-inclusion input")!;
  included.checked = false; included.dispatchEvent(new Event("change", { bubbles: true })); await settle(panel);
  button(panel, "Enregistrer la veilleuse").click(); await settle(panel);
  assert.equal(calls.some((call) => call.type === "halo/edit/end"), false);
  assert.match(panel.shadowRoot!.querySelector('[role="alert"]')!.textContent!, /luminosité non nulle/);
  included.checked = true; included.dispatchEvent(new Event("change", { bubbles: true }));
  panel.hass = { ...hass, states: { "light.colour": { state: "on", attributes: { brightness: 0 } } } }; await settle(panel);
  button(panel, "Enregistrer la veilleuse").click(); await settle(panel);
  assert.equal(calls.some((call) => call.type === "halo/edit/end"), false);
  panel.hass = { ...hass, states: { "light.colour": { state: "unavailable", attributes: {} } } }; await settle(panel);
  assert.equal(panel.shadowRoot!.querySelector<HTMLButtonElement>(".scene-lamp")!.disabled, true);
  button(panel, "Enregistrer la veilleuse").click(); await settle(panel);
  assert.deepEqual(calls.find((call) => call.type === "halo/edit/end")!.nightlight, snapshot.config.rooms.lounge.nightlight);
});

test("removing the last usable nightlight prunes settings and disables it without changing scenes", async () => {
  const snapshot = nightlightFixture();
  const { panel, calls } = await mount(true, snapshot);
  await openRoom(panel, "Lumières");
  const selected = [...panel.shadowRoot!.querySelectorAll<HTMLInputElement>('.light-option input')].find((input) => input.parentElement!.textContent!.includes("light.colour"))!;
  selected.checked = false; selected.dispatchEvent(new Event("change", { bubbles: true })); await settle(panel);
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  const room = (calls.find((call) => call.type === "halo/save")!.config as Snapshot["config"]).rooms.lounge;
  assert.deepEqual(room.nightlight, { enabled: false, lights: {} });
  assert.deepEqual(room.lights, ["light.simple"]);
  assert.equal(room.scenes.length, 1);
});

test("nightlight shows shared sensor settings and incomplete groups, with localized status and admin-only controls", async () => {
  const snapshot = nightlightFixture();
  const room = snapshot.config.rooms.lounge;
  room.lux_entity_id = "sensor.illuminance"; room.lux_threshold = 20; room.lux_hysteresis = 5; room.lux_off = false;
  snapshot.entities.push({ entity_id: "sensor.illuminance", name: "Luminosité", state: "15", attributes: { unit_of_measurement: "%" } });
  snapshot.lights[0].is_group = true; snapshot.lights[0].group_members = ["light.child"]; snapshot.lights[0].group_members_complete = false;
  snapshot.status.lounge.reason = "nightlight";
  const { panel, hass } = await mount(true, snapshot);
  panel.hass = { ...hass, states: { "sensor.illuminance": { state: "15", attributes: { unit_of_measurement: "%" } } } };
  await openRoom(panel, "Ambiances");
  const section = panel.shadowRoot!.querySelector(".nightlight-section")!;
  assert.match(section.textContent!, /Seuil bas: 20 % · Seuil haut: 25 %/);
  assert.match(section.textContent!, /Valeur actuelle: 15 %/);
  assert.match(section.textContent!, /Certains membres de groupes sont inconnus/);
  assert.match(panel.shadowRoot!.querySelector('[aria-label="État de la pièce"]')!.textContent!, /Veilleuse/);
  button(panel, "Réglages de présence et de luminosité").click(); await settle(panel);
  assert.equal(inputByLabel(panel, "Délai de confirmation de luminosité").value, "30");
  await selectRoomTab(panel, "Ambiances");
  panel.hass = { ...hass, locale: { language: "de" } }; await settle(panel);
  assert.match(panel.shadowRoot!.querySelector(".nightlight-section")!.textContent!, /Nightlight/);
  panel.remove();
  const viewer = await mount(false, { ...snapshot, is_admin: false }); await openRoom(viewer.panel);
  assert.equal(viewer.panel.shadowRoot!.querySelectorAll('[role="tab"]').length, 1);
  assert.equal(viewer.panel.shadowRoot!.querySelector(".nightlight-section"), null);
  assert.equal(viewer.calls.some((call) => call.type === "halo/edit/begin"), false);
});


test("a slow save never discards newer valid edits and the next save uses its acknowledged revision", async () => {
  let release!: (snapshot: Snapshot) => void;
  const saving = new Promise<Snapshot>((resolve) => { release = resolve; });
  const { panel, calls } = await mount(true, fixture(), { save: () => saving });
  await openRoom(panel, "Automatisation");
  const changeDelay = async (value: string) => {
    const input = inputByLabel(panel, "Délai d’absence");
    input.value = value; input.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  };
  await changeDelay("15");
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  await changeDelay("25");
  const saved = fixture(); saved.revision = 8; saved.config.rooms.lounge.absence_delay = 15;
  release(saved); await settle(panel);
  assert.equal(inputByLabel(panel, "Délai d’absence").value, "25", "Typing during save must not be replaced by the older server response");
  assert.ok(panel.shadowRoot!.querySelector(".savebar"));
  assert.equal(button(panel, "Enregistrer les modifications").disabled, false);
  assert.equal(calls.filter((call) => call.type === "halo/save").length, 1);
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  const second = calls.filter((call) => call.type === "halo/save")[1];
  assert.equal(second.revision, 8);
  assert.equal((second.config as Snapshot["config"]).rooms.lounge.absence_delay, 25);
});

test("losing administrator rights abandons configuration and native editing without issuing more privileged actions", async () => {
  for (const editing of [false, true]) {
    const { panel, calls, emit } = await mount();
    if (editing) { await openRoom(panel); button(panel, "Régler").click(); await settle(panel); }
    else {
      await openRoom(panel, "Automatisation");
      const field = inputByLabel(panel, "Délai d’absence"); field.value = "17";
      field.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
    }
    const before = calls.length;
    emit(fixture(false)); await settle(panel);
    assert.ok(!panel.shadowRoot!.querySelector(".editor"), "The privileged editor must close");
    assert.ok(!panel.shadowRoot!.querySelector(".savebar"), "The privileged draft bar must disappear");
    assert.ok(!panel.shadowRoot!.querySelector(".automation-section"));
    assert.equal(button(panel, "Allumer").disabled, false);
    assert.equal(calls.slice(before).some((call) => ["halo/save", "halo/edit/end", "halo/edit/touch", "halo/edit/preview"].includes(String(call.type))), false);
    panel.remove();
  }
});

test("a new Home Assistant connection drops the old native editor and its lock", async () => {
  const { panel, hass, calls } = await mount();
  await openRoom(panel); button(panel, "Régler").click(); await settle(panel);
  panel.hass = { ...hass, connection: { async subscribeMessage() { return () => undefined; } } };
  await settle(panel);
  assert.ok(!panel.shadowRoot!.querySelector(".editor"), "The privileged editor must close");
  assert.equal(button(panel, "Pièces").disabled, false);
  assert.equal(calls.filter((call) => call.type === "halo/get").length, 2);
});


test("invalid text entered during a slow save remains visible, dirty and unsaved after acknowledgement", async () => {
  let release!: (snapshot: Snapshot) => void;
  const saving = new Promise<Snapshot>((resolve) => { release = resolve; });
  const { panel, calls } = await mount(true, fixture(), { save: () => saving });
  await openRoom(panel, "Automatisation");
  const field = inputByLabel(panel, "Délai d’absence");
  field.value = "15"; field.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  field.value = "-1"; field.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  const saved = fixture(); saved.revision = 8; saved.config.rooms.lounge.absence_delay = 15;
  release(saved); await settle(panel);
  assert.equal(field.value, "-1");
  assert.ok(panel.shadowRoot!.querySelector(".savebar"));
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  assert.equal(calls.filter((call) => call.type === "halo/save").length, 1);
  assert.equal(panel.shadowRoot!.activeElement, field);
  button(panel, "Abandonner les modifications").click(); await settle(panel);
  assert.equal(inputByLabel(panel, "Délai d’absence").value, "15");
});

test("a newer remote revision arriving before save acknowledgement stays authoritative", async () => {
  for (const editAgain of [false, true]) {
    let release!: (snapshot: Snapshot) => void;
    const saving = new Promise<Snapshot>((resolve) => { release = resolve; });
    const { panel, emit } = await mount(true, fixture(), { save: () => saving });
    await openRoom(panel, "Automatisation");
    const field = inputByLabel(panel, "Délai d’absence");
    field.value = "15"; field.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
    button(panel, "Enregistrer les modifications").click(); await settle(panel);
    if (editAgain) { field.value = "25"; field.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel); }
    const remote = fixture(); remote.revision = 9; remote.config.rooms.lounge.absence_delay = 35;
    emit(remote); await settle(panel);
    const saved = fixture(); saved.revision = 8; saved.config.rooms.lounge.absence_delay = 15;
    release(saved); await settle(panel);
    assert.equal(field.value, editAgain ? "25" : "35");
    if (editAgain) {
      assert.equal(button(panel, "Enregistrer les modifications").disabled, true);
      button(panel, "Abandonner les modifications").click(); await settle(panel);
      assert.equal(inputByLabel(panel, "Délai d’absence").value, "35");
    } else assert.ok(!panel.shadowRoot!.querySelector(".savebar"));
    panel.remove();
  }
});

test("a save failure preserves the draft and exposes its error", async () => {
  let reject!: (reason: unknown) => void;
  const saving = new Promise<Snapshot>((_, fail) => { reject = fail; });
  const { panel, calls } = await mount(true, fixture(), { save: () => saving });
  await openRoom(panel, "Automatisation");
  const field = inputByLabel(panel, "Délai d’absence");
  field.value = "15"; field.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  reject({ code: "invalid_config" }); await settle(panel);
  assert.equal(field.value, "15");
  assert.ok(panel.shadowRoot!.querySelector(".savebar"));
  assert.ok(panel.shadowRoot!.querySelector('[role="alert"]'));
  assert.equal(calls.filter((call) => call.type === "halo/save").length, 1);
  panel.remove();
});

test("a changed revision while starting an editor cancels its lock before any stale preview", async () => {
  let release!: () => void;
  const begin = new Promise<void>((resolve) => { release = resolve; });
  const { panel, calls, emit } = await mount(true, fixture(), { begin: () => begin });
  await openRoom(panel); button(panel, "Régler").click(); await settle(panel);
  const remote = fixture(); remote.revision = 8; remote.config.rooms.lounge.scenes[0].name = "Updated elsewhere";
  emit(remote); await settle(panel);
  release(); await settle(panel);
  assert.ok(!panel.shadowRoot!.querySelector(".editor"));
  assert.equal(calls.some((call) => call.type === "halo/edit/preview"), false);
  assert.ok(calls.some((call) => call.type === "halo/edit/end" && call.save === false));
  assert.match(panel.shadowRoot!.textContent!, /configuration a changé ailleurs/);
  assert.match(panel.shadowRoot!.textContent!, /Updated elsewhere/);
});

test("role loss during native lock renewal prevents a late Home Assistant dialog", async () => {
  let release!: () => void;
  const touch = new Promise<void>((resolve) => { release = resolve; });
  const { panel, emit } = await mount(true, fixture(), { touch: () => touch });
  await openRoom(panel); button(panel, "Régler").click(); await settle(panel);
  const actions: Event[] = []; panel.addEventListener("hass-action", (event) => actions.push(event));
  panel.shadowRoot!.querySelector<HTMLButtonElement>(".scene-lamp")!.click(); await settle(panel);
  emit(fixture(false)); await settle(panel);
  release(); await settle(panel);
  assert.equal(actions.length, 0);
  assert.ok(!panel.shadowRoot!.querySelector(".editor"));
});

test("ordinary-user status updates retain keyboard focus instead of remounting the controls", async () => {
  const { panel, emit } = await mount(false);
  await openRoom(panel);
  const control = button(panel, "Allumer"); control.focus();
  emit({ ...fixture(false), status: { lounge: { reason: "base", is_on: true, available: true } } }); await settle(panel);
  assert.equal(panel.shadowRoot!.activeElement, control);
});


test("late save and edit-end responses from a previous connection cannot replace newer configuration", async () => {
  for (const editing of [false, true]) {
    let release!: (snapshot: Snapshot) => void;
    const pending = new Promise<Snapshot>((resolve) => { release = resolve; });
    const { panel, hass, emit } = await mount(true, fixture(), editing ? { end: () => pending } : { save: () => pending });
    await openRoom(panel, editing ? "Pilotage" : "Automatisation");
    if (editing) {
      button(panel, "Régler").click(); await settle(panel);
      button(panel, "Enregistrer la scène").click(); await settle(panel);
    } else {
      const field = inputByLabel(panel, "Délai d’absence");
      field.value = "15"; field.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
      button(panel, "Enregistrer les modifications").click(); await settle(panel);
    }
    const remote = fixture(); remote.revision = 9; remote.config.rooms.lounge.absence_delay = 35;
    emit(remote); await settle(panel);
    panel.hass = { ...hass, connection: { async subscribeMessage() { return () => undefined; } } }; await settle(panel);
    if (!editing) { button(panel, "Abandonner les modifications").click(); await settle(panel); }
    const old = fixture(); old.revision = 8; old.config.rooms.lounge.absence_delay = 15;
    release(old); await settle(panel);
    await selectRoomTab(panel, "Automatisation");
    assert.equal(inputByLabel(panel, "Délai d’absence").value, "35");
    assert.ok(!panel.shadowRoot!.querySelector(".editor"));
    panel.remove();
  }
});


test("single-light and single-room counts use singular labels in French and English", async () => {
  const snapshot = fixture(); const room = snapshot.config.rooms.lounge;
  room.lights = ["light.colour"];
  (room.scenes[0] as HaloScene).lights = { "light.colour": { state: "on" } };
  snapshot.config.profiles.solar = newProfile("solar", "Solaire");
  room.associations = [{ profile_id: "solar", lights: ["light.colour"], brightness_offset: 0 }];
  const { panel, hass } = await mount(true, snapshot);
  for (const [locale, oneLight, oneRoom, tabs] of [
    ["fr-BE", "1 lumière", "1 pièce", ["Ambiances", "Profils de lumière naturelle", "Pièces"]],
    ["en", "1 light", "1 room", ["Ambiences", "Natural light profiles", "Rooms"]],
    ["es-MX", "1 luz", "1 habitación", ["Ambientes", "Perfiles de luz natural", "Habitaciones"]],
  ] as const) {
    panel.hass = { ...hass, locale: { language: locale } }; await settle(panel);
    const link = panel.shadowRoot!.querySelector<HTMLButtonElement>('.room-link[aria-label="Salon personnalisé"]')!;
    link.click(); await settle(panel);
    assert.match(panel.shadowRoot!.querySelector(".room-meta")!.textContent!, new RegExp(`${oneLight} ·`));
    assert.match(panel.shadowRoot!.querySelector(".scene-meta")!.textContent!, new RegExp(`${oneLight} ·`));
    await selectRoomTab(panel, tabs[0]);
    assert.match(panel.shadowRoot!.querySelector(".association summary")!.textContent!, new RegExp(`${oneLight} ·`));
    button(panel, tabs[1]).click(); await settle(panel);
    assert.match(panel.shadowRoot!.querySelector(".profile-link small")!.textContent!, new RegExp(`${oneRoom} ·`));
    button(panel, tabs[2]).click(); await settle(panel);
  }
});


test("transition modes and duration fields identify their category to assistive technology", async () => {
  const { panel } = await mount();
  button(panel, "Réglages globaux").click(); await settle(panel);
  const globalNames = [...panel.shadowRoot!.querySelectorAll<HTMLInputElement>('.transition-grid input[type="number"]')].map((field) => field.getAttribute("aria-label"));
  assert.equal(globalNames.length, 5);
  assert.equal(new Set(globalNames).size, 5);
  for (const name of globalNames) assert.match(name!, / · Secondes$/);
  button(panel, "Pièces").click(); await settle(panel);
  await openRoom(panel, "Réglages");
  const modes = [...panel.shadowRoot!.querySelectorAll<HTMLSelectElement>(".transition-grid select")];
  assert.equal(new Set(modes.map((field) => field.getAttribute("aria-label"))).size, 5);
  for (const [index, mode] of modes.entries()) {
    assert.equal(mode.getAttribute("aria-label"), globalNames[index]!.replace("Secondes", "Transitions des lumières"));
    mode.value = "duration"; mode.dispatchEvent(new Event("change", { bubbles: true })); await settle(panel);
  }
  assert.deepEqual([...panel.shadowRoot!.querySelectorAll<HTMLInputElement>('.transition-grid input[type="number"]')].map((field) => field.getAttribute("aria-label")), globalNames);
});


test("late room command replies cannot restore old revisions, privileged views or previous connections", async () => {
  for (const change of ["revision", "rights", "connection"]) {
    let release!: (snapshot: Snapshot) => void;
    const command = new Promise<Snapshot>((resolve) => { release = resolve; });
    const { panel, hass, emit } = await mount(true, fixture(), { command: () => command });
    await openRoom(panel);
    inputByLabel(panel, "Automatisation").click(); await settle(panel);
    const latest = fixture(change !== "rights"); latest.revision = 9;
    latest.config.rooms.lounge.absence_delay = 35;
    emit(latest); await settle(panel);
    if (change === "connection") {
      panel.hass = { ...hass, connection: { async subscribeMessage() { return () => undefined; } } }; await settle(panel);
    }
    const old = fixture(); old.revision = 8; old.config.rooms.lounge.absence_delay = 15;
    release(old); await settle(panel);
    if (change === "rights") {
      assert.equal(panel.shadowRoot!.querySelectorAll('[role="tab"]').length, 1, "A late privileged reply must not restore configuration actions");
      assert.equal(button(panel, "Allumer").disabled, false);
    } else {
      await selectRoomTab(panel, "Automatisation");
      assert.equal(inputByLabel(panel, "Délai d’absence").value, "35");
    }
    panel.remove();
  }
});


test("base ambience displays native brightness without rewriting it and edits keep a single representation", async () => {
  for (const native of [0, 127, 204]) {
    const snapshot = fixture();
    snapshot.config.rooms.lounge.base["light.colour"] = { state: "on", brightness: native, color_mode: "rgb", rgb_color: [10, 20, 30], effect: "Candle" };
    const { panel, calls } = await mount(true, snapshot);
    await openRoom(panel, "Ambiances");
    const brightness = inputByLabel(panel, "Luminosité (%)");
    assert.equal(Number(brightness.value), native / 255 * 100);
    assert.notEqual(brightness.value, "");
    assert.ok(!panel.shadowRoot!.querySelector(".savebar"), "Displaying native precision must not rewrite the saved configuration");
    brightness.value = "30"; brightness.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
    button(panel, "Enregistrer les modifications").click(); await settle(panel);
    const changed = (calls.filter((call) => call.type === "halo/save").at(-1)!.config as Snapshot["config"]).rooms.lounge.base["light.colour"];
    assert.deepEqual(changed, { state: "on", brightness_pct: 30, color_mode: "rgb", rgb_color: [10, 20, 30], effect: "Candle" });
    const cleared = inputByLabel(panel, "Luminosité (%)");
    cleared.value = ""; cleared.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
    button(panel, "Enregistrer les modifications").click(); await settle(panel);
    const noBrightness = (calls.filter((call) => call.type === "halo/save").at(-1)!.config as Snapshot["config"]).rooms.lounge.base["light.colour"];
    assert.equal(noBrightness.brightness, undefined);
    assert.equal(noBrightness.brightness_pct, undefined);
    assert.equal(noBrightness.effect, "Candle");
    panel.remove();
  }
});

function fallbackMode(panel: InstanceType<typeof HaloPanel>): HTMLSelectElement {
  const select = panel.shadowRoot!.querySelector<HTMLSelectElement>(".lighting-fallback select");
  assert.ok(select, "The fallback mode selector should exist without a lux sensor");
  return select;
}
async function chooseFallback(panel: InstanceType<typeof HaloPanel>, mode: string) {
  const select = fallbackMode(panel); select.value = mode; select.dispatchEvent(new Event("change", { bubbles: true })); await settle(panel);
}
async function fill(panel: InstanceType<typeof HaloPanel>, label: string, value: string) {
  const field = inputByLabel(panel, label); field.value = value; field.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel); return field;
}

test("lighting fallback defaults are detached, legacy-safe and hidden whenever a lux sensor is configured", async () => {
  const first = newRoom("one"), second = newRoom("two"); first.lighting_fallback.start = "22:00";
  assert.equal(second.lighting_fallback.start, "18:00");
  const snapshot = fixture(); delete (snapshot.config.rooms.lounge as Partial<typeof first>).lighting_fallback;
  const { panel, calls, emit } = await mount(true, snapshot); await openRoom(panel, "Automatisation");
  assert.equal(fallbackMode(panel).value, "always");
  assert.equal(panel.shadowRoot!.querySelectorAll('[role="tab"]').length, 5);
  assert.ok(!panel.shadowRoot!.querySelector(".savebar"), "Reading an old configuration must not create a draft");
  assert.ok(!("lighting_fallback" in snapshot.config.rooms.lounge), "The source snapshot remains unchanged");
  const withLux = fixture(); withLux.config.rooms.lounge.lux_entity_id = "sensor.missing"; withLux.config.rooms.lounge.lux_threshold = 20;
  withLux.config.rooms.lounge.lighting_fallback.mode = "time";
  emit(withLux); await settle(panel);
  assert.ok(!panel.shadowRoot!.querySelector(".lighting-fallback"), "Unavailable configured lux is not absence of configuration");
  assert.equal(calls.filter((call) => call.type !== "halo/get").length, 0);
});

test("lighting fallback mode changes preserve inactive hours, solar thresholds and normal shutoff in the saved draft", async () => {
  const { panel, calls } = await mount(); await openRoom(panel, "Automatisation");
  await chooseFallback(panel, "time"); await fill(panel, "Heure de début", "23:15"); await fill(panel, "Heure de fin", "00:00");
  const turnOff = inputByLabel(panel, "Éteindre aussi l’éclairage normal"); turnOff.checked = true; turnOff.dispatchEvent(new Event("change", { bubbles: true })); await settle(panel);
  await chooseFallback(panel, "sun");
  await fill(panel, "Autoriser sous cette hauteur", "-6.25");
  const linked = inputByLabel(panel, "Lier le matin et le soir"); linked.checked = false; linked.dispatchEvent(new Event("change", { bubbles: true })); await settle(panel);
  await fill(panel, "Soleil descendant : autoriser sous", "4.5");
  linked.checked = true; linked.dispatchEvent(new Event("change", { bubbles: true })); await settle(panel);
  await chooseFallback(panel, "always"); await selectRoomTab(panel, "Ambiances"); await selectRoomTab(panel, "Automatisation");
  await chooseFallback(panel, "time");
  assert.equal(inputByLabel(panel, "Heure de début").value, "23:15"); assert.equal(inputByLabel(panel, "Heure de fin").value, "00:00");
  assert.equal(inputByLabel(panel, "Éteindre aussi l’éclairage normal").checked, true);
  await chooseFallback(panel, "sun");
  assert.equal(inputByLabel(panel, "Autoriser sous cette hauteur").value, "-6.25");
  const unlink = inputByLabel(panel, "Lier le matin et le soir"); unlink.checked = false; unlink.dispatchEvent(new Event("change", { bubbles: true })); await settle(panel);
  assert.equal(inputByLabel(panel, "Soleil descendant : autoriser sous").value, "4.5");
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  const saved = calls.find((call) => call.type === "halo/save")!.config as Snapshot["config"];
  assert.deepEqual(saved.rooms.lounge.lighting_fallback, { mode: "sun", start: "23:15", end: "00:00", linked: false, morning_below: -6.25, evening_below: 4.5, turn_off: true });
  assert.equal(calls.some((call) => call.type === "halo/command" || String(call.type).startsWith("halo/edit")), false);
});

test("fallback time range rejects equal or empty times before save, navigation or hiding the fields", async () => {
  const { panel, calls } = await mount(); await openRoom(panel, "Automatisation"); await chooseFallback(panel, "time");
  await fill(panel, "Heure de début", "00:00"); const end = await fill(panel, "Heure de fin", "00:00");
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  assert.equal(calls.some((call) => call.type === "halo/save"), false); assert.equal(panel.shadowRoot!.activeElement, end);
  await selectRoomTab(panel, "Ambiances"); assert.equal(roomTab(panel, "Automatisation").getAttribute("aria-selected"), "true");
  await chooseFallback(panel, "always"); assert.equal(fallbackMode(panel).value, "time");
  const lux = picker(panel, "Capteur de luminosité"); lux.value = "sensor.any"; lux.dispatchEvent(new CustomEvent("entity-changed", { detail: { value: "sensor.any" } })); await settle(panel);
  assert.equal(lux.value, null); assert.ok(panel.shadowRoot!.querySelector(".fallback-time"));
  await fill(panel, "Heure de fin", "08:00"); await fill(panel, "Heure de début", "18:00:30");
  button(panel, "Enregistrer les modifications").click(); await settle(panel); assert.equal(calls.some((call) => call.type === "halo/save"), false);
  await fill(panel, "Heure de début", "");
  button(panel, "Enregistrer les modifications").click(); await settle(panel); assert.equal(calls.some((call) => call.type === "halo/save"), false);
  button(panel, "Abandonner les modifications").click(); await settle(panel); assert.equal(fallbackMode(panel).value, "always");
});

test("fallback solar fields validate bounds, preserve invalid input and expose confirmation for nightlights independently of normal shutoff", async () => {
  const snapshot = nightlightFixture(); snapshot.config.rooms.lounge.lighting_fallback.mode = "sun";
  const { panel, calls } = await mount(true, snapshot); await openRoom(panel, "Automatisation");
  assert.equal(inputByLabel(panel, "Éteindre aussi l’éclairage normal").checked, false);
  assert.equal(inputByLabel(panel, "Délai de confirmation solaire").value, "30");
  for (const value of ["-91", "91", ""]) {
    const input = await fill(panel, "Autoriser sous cette hauteur", value);
    button(panel, "Enregistrer les modifications").click(); await settle(panel);
    assert.equal(calls.some((call) => call.type === "halo/save"), false); assert.equal(panel.shadowRoot!.activeElement, input);
    await chooseFallback(panel, "always"); assert.equal(fallbackMode(panel).value, "sun"); assert.equal(input.value, value);
  }
  await fill(panel, "Autoriser sous cette hauteur", "-90"); await fill(panel, "Délai de confirmation solaire", "0");
  button(panel, "Enregistrer les modifications").click(); await settle(panel);
  const saved = calls.find((call) => call.type === "halo/save")!.config as Snapshot["config"];
  assert.equal(saved.rooms.lounge.lighting_fallback.morning_below, -90); assert.equal(saved.rooms.lounge.lux_off_delay, 0);
  await chooseFallback(panel, "time"); assert.ok(!panel.shadowRoot!.querySelector('.lighting-fallback input[type="number"]'));
});

test("fallback sun elevation follows the global live entity without invented zero or stale readings and keeps drafts untouched", async () => {
  const snapshot = fixture(); snapshot.config.rooms.lounge.lighting_fallback.mode = "sun";
  const { panel, calls, hass } = await mount(true, snapshot); panel.hass = { ...hass, states: undefined }; await openRoom(panel, "Automatisation");
  const current = () => panel.shadowRoot!.querySelector(".current-sun-elevation")!.textContent;
  assert.equal(current(), "Hauteur solaire actuelle: 15°");
  await fill(panel, "Autoriser sous cette hauteur", "-7.5");
  for (const [state, elevation, expected] of [["above_horizon", 0, "0°"], ["below_horizon", "-6.25", "-6,25°"], ["above_horizon", "", "Indisponible"], ["above_horizon", true, "Indisponible"], ["above_horizon", 91, "Indisponible"], ["unavailable", 12, "Indisponible"], ["unknown", 0, "Indisponible"], ["above_horizon", Infinity, "Indisponible"], ["above_horizon", null, "Indisponible"]] as const) {
    panel.hass = { ...hass, states: { "sun.sun": { state, attributes: { elevation } } } }; await settle(panel);
    assert.equal(current(), `Hauteur solaire actuelle: ${expected}`); assert.equal(inputByLabel(panel, "Autoriser sous cette hauteur").value, "-7.5");
  }
  panel.hass = { ...hass, states: {} }; await settle(panel); assert.equal(current(), "Hauteur solaire actuelle: Indisponible");
  assert.equal(calls.some((call) => call.type === "halo/save" || call.type === "halo/command"), false);
});

test("lighting authorization and solar deadline are localized from engine status without implying a lux reading", async () => {
  const snapshot = fixture(false); snapshot.status.lounge = { reason: "outside_schedule", is_on: false, available: true, lighting_source: "time", lighting_allowed: false, lighting_off_deadline: "2026-10-10T12:00:00Z" };
  const { panel, hass, emit } = await mount(false, snapshot); await openRoom(panel);
  assert.match(panel.shadowRoot!.textContent!, /Hors plage horaire/);
  assert.equal(panel.shadowRoot!.querySelector(".lighting-authorization")!.textContent, "Autorisation d’éclairage: Non autorisé · Plage horaire");
  assert.doesNotMatch(panel.shadowRoot!.textContent!, /Extinction après confirmation solaire/, "A time range closes immediately without a solar confirmation countdown");
  assert.equal(panel.shadowRoot!.querySelectorAll('[role="tab"]').length, 1); assert.ok(!panel.shadowRoot!.querySelector(".lighting-fallback"));
  emit({ ...snapshot, status: { lounge: { reason: "sun_above_threshold", lighting_source: "sun", lighting_allowed: null, lighting_off_deadline: "2026-10-10T12:00:00Z", is_on: true, available: true } } }); await settle(panel);
  assert.match(panel.shadowRoot!.textContent!, /Soleil au-dessus du seuil/); assert.match(panel.shadowRoot!.textContent!, /Extinction après confirmation solaire/);
  assert.match(panel.shadowRoot!.querySelector(".lighting-authorization")!.textContent!, /Indisponible · Hauteur du soleil/);
  panel.hass = { ...hass, locale: { language: "en" } }; await settle(panel);
  assert.match(panel.shadowRoot!.textContent!, /Sun above the threshold/); assert.match(panel.shadowRoot!.textContent!, /Lighting authorization: Unavailable · Sun elevation/);
  assert.doesNotMatch(panel.shadowRoot!.querySelector(".lighting-authorization")!.textContent!, /\blx\b|lux/);
});

test("fallback configuration and nightlight guidance follow locale while retaining private drafts and shared settings", async () => {
  const snapshot = nightlightFixture(); snapshot.config.rooms.lounge.lighting_fallback.mode = "time";
  const { panel, hass, calls } = await mount(true, snapshot); await openRoom(panel, "Ambiances");
  assert.match(panel.shadowRoot!.querySelector(".nightlight-section")!.textContent!, /plage autorisée/);
  button(panel, "Réglages de présence et de luminosité").click(); await settle(panel);
  await fill(panel, "Heure de début", "20:45"); panel.hass = { ...hass, locale: { language: "en-US" } }; await settle(panel);
  assert.equal(inputByLabel(panel, "Start time").value, "20:45"); assert.equal(fallbackMode(panel).value, "time");
  await chooseFallback(panel, "sun"); assert.equal(inputByLabel(panel, "Allow below this sun elevation").value, "0");
  await selectRoomTab(panel, "Ambiences"); assert.match(panel.shadowRoot!.querySelector(".nightlight-section")!.textContent!, /selected solar thresholds/);
  assert.equal(calls.some((call) => call.type === "halo/save"), false);
});

test("separate fallback solar thresholds report a missing direction without hiding a valid elevation", async () => {
  const snapshot = fixture(); Object.assign(snapshot.config.rooms.lounge.lighting_fallback, { mode: "sun", linked: false });
  const { panel, hass, calls } = await mount(true, snapshot);
  panel.hass = { ...hass, states: { "sun.sun": { state: "below_horizon", attributes: { elevation: "-2.5" } } } }; await openRoom(panel, "Automatisation");
  assert.match(panel.shadowRoot!.querySelector(".current-sun-elevation")!.textContent!, /-2,5°/);
  assert.equal(panel.shadowRoot!.querySelector(".current-sun-direction")!.textContent, "Sens actuel du soleil: Indisponible");
  assert.match(panel.shadowRoot!.querySelector(".lighting-fallback")!.textContent!, /suspendue quand ce sens est indisponible/);
  for (const [rising, label] of [["false", "Indisponible"], [false, "Soleil descendant"], [true, "Soleil montant"]] as const) {
    panel.hass = { ...hass, states: { "sun.sun": { state: "below_horizon", attributes: { elevation: -2.5, rising } } } }; await settle(panel);
    assert.equal(panel.shadowRoot!.querySelector(".current-sun-direction")!.textContent, `Sens actuel du soleil: ${label}`);
  }
  assert.ok(!panel.shadowRoot!.querySelector(".savebar")); assert.equal(calls.some((call) => call.type !== "halo/get"), false);
});
