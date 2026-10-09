import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { Window } from "happy-dom";
import { newProfile, newRoom } from "../src/model";
import type { HaloEntityPicker } from "../src/entity-picker";
import type { Curve, Hass, Scene, Snapshot } from "../src/types";

const window = new Window({ url: "http://192.168.1.4:8123" });
for (const key of ["window", "document", "customElements", "HTMLElement", "Element", "Node", "Document", "ShadowRoot", "CSSStyleSheet", "Event", "CustomEvent", "KeyboardEvent", "FocusEvent"] as const) {
  Object.defineProperty(globalThis, key, { configurable: true, value: key === "window" ? window : window[key] });
}
const { HaloPanel } = await import("../src/halo-panel");

function fixture(admin = true): Snapshot {
  const room = newRoom("lounge");
  room.lights = ["light.colour", "light.simple"];
  room.scenes = [{ id: "cinema", name: "Cinéma perso", conditions: { type: "state", entity_id: "media_player.tv", state: "on" }, can_turn_on: false,
    lights: { "light.colour": { state: "on", brightness_pct: 20 }, "light.simple": { state: "off" } } }];
  return { revision: 7, is_admin: admin, areas: [{ id: "lounge", name: "Salon personnalisé" }, { id: "kitchen", name: "Cuisine" }],
    config: { sun_entity_id: "sun.sun", profiles: {}, rooms: { lounge: room }, transitions: { turn_on: null, lux_on: null, natural: null, scene: null, turn_off: null } },
    status: { lounge: { reason: "manual_pause", is_on: true, available: true, pause_until: "2026-10-09T22:00:00Z" } },
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

async function mount(admin = true, initial = fixture(admin), pending: { begin?: () => Promise<void>; preview?: () => Promise<void>; touch?: () => Promise<void>; api?: () => Promise<unknown>; import?: () => Promise<{ scene: Scene; ignored_entities: number }> } = {}) {
  let snapshot = initial;
  const calls: Record<string, unknown>[] = [];
  let callback: ((snapshot: Snapshot) => void) | undefined;
  let unsubscribed = 0;
  const hass: Hass = { locale: { language: "fr-BE" }, language: "en", states: {},
    async callApi<T>(method: "GET", path: string) { calls.push({ type: "api", method, path }); return await pending.api?.() as T; },
    async callWS<T>(message: Record<string, unknown>) {
      calls.push(structuredClone(message));
      if (message.type === "halo/get") return structuredClone(snapshot) as T;
      if (message.type === "halo/save") {
        snapshot = { ...snapshot, config: structuredClone(message.config) as Snapshot["config"], revision: snapshot.revision + 1 };
        return structuredClone(snapshot) as T;
      }
      if (message.type === "halo/edit/begin") { await pending.begin?.(); return { token: "editor-token" } as T; }
      if (message.type === "halo/edit/preview") await pending.preview?.();
      if (message.type === "halo/edit/touch") await pending.touch?.();
      if (message.type === "halo/edit/end") return structuredClone(snapshot) as T;
      if (message.type === "halo/scene/import") return await pending.import?.() as T;
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

test("natural graphs place entered elevations at the exact curve thresholds, including close and boundary values", async () => {
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
  const { panel } = await mount(true, snapshot);
  button(panel, "Profils de lumière naturelle").click();
  await settle(panel);
  const graphs = [...panel.shadowRoot!.querySelectorAll<SVGSVGElement>('svg[role="img"]')];
  assert.equal(graphs.length, curves.length);
  graphs.forEach((graph, index) => {
    const curve = curves[index];
    const labels = [...graph.querySelectorAll<SVGTextElement>('text[y="178"]')];
    assert.deepEqual(labels.map((label) => label.textContent), [`${curve.low_elevation}°`, `${curve.high_elevation}°`]);
    const points = graph.querySelector("polyline")!.getAttribute("points")!.split(" ").map((point) => point.split(",").map(Number));
    assert.equal(points.length, 4);
    assert.deepEqual(labels.map((label) => Number(label.getAttribute("x"))), [points[1][0], points[2][0]]);
    assert.ok(points[2][0] - points[1][0] > 100, "Close thresholds remain readable without changing their values");
    assert.equal(points[0][1], points[1][1], "The lower plateau reaches the first threshold exactly");
    assert.equal(points[2][1], points[3][1], "The upper plateau starts at the second threshold exactly");
    assert.ok(points.flat().every(Number.isFinite));
    assert.equal(Math.sign(points[1][1] - points[2][1]), Math.sign(curve.high - curve.low));
    if (curve.low === curve.high) assert.equal(graph.querySelectorAll('text[x="2"]').length, 1);
  });
});

test("S-curve previews its actual values and keeps plateau thresholds and accessible labels", async () => {
  const snapshot = fixture();
  const profile = newProfile("solar", "Natural");
  profile.morning.brightness = { low_elevation: -6.125, high_elevation: -6.12, low: 20, high: 100, interpolation: "ease_in_out" };
  profile.morning.temperature = { low_elevation: -90, high_elevation: 90, low: 6500, high: 2200, interpolation: "ease_in_out" };
  profile.morning.brightness.interpolation = "ease_in";
  snapshot.config.profiles.solar = profile;
  const { panel } = await mount(true, snapshot);
  button(panel, "Profils de lumière naturelle").click();
  await settle(panel);
  assert.deepEqual([...panel.shadowRoot!.querySelectorAll<HTMLSelectElement>('.profile select[aria-describedby]')].map((select) => select.value), ["ease_in_out", "ease_in_out"]);
  [...panel.shadowRoot!.querySelectorAll<SVGSVGElement>('svg[role="img"]')].forEach((graph, index) => {
    const points = graph.querySelector("polyline")!.getAttribute("points")!.split(" ").map((point) => point.split(",").map(Number));
    assert.ok(points.flat().every(Number.isFinite));
    const labels = [...graph.querySelectorAll<SVGTextElement>('text[y="178"]')];
    assert.deepEqual(labels.map((label) => Number(label.getAttribute("x"))), [points[1][0], points.at(-2)![0]]);
    assert.equal(points[0][1], points[1][1]);
    assert.equal(points.at(-2)![1], points.at(-1)![1]);
    const midpoint = points[Math.floor(points.length / 2)];
    assert.ok(Math.abs(midpoint[1] - 97.5) < 1e-8, "The midpoint is halfway through the value change");
    const firstQuarter = points[9][1], lastQuarter = points[25][1];
    const [startY, endY] = [points[1][1], points.at(-2)![1]];
    assert.ok(Math.abs(firstQuarter - (startY + (endY - startY) * .15625)) < 1e-8);
    assert.ok(Math.abs(lastQuarter - (startY + (endY - startY) * .84375)) < 1e-8);
    assert.match(graph.getAttribute("aria-label")!, /Accélération et décélération/);
  });
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
  assert.match(panel.shadowRoot!.textContent!, /Pause manuelle/);
  panel.hass = { ...hass, locale: { language: "de" } };
  await settle(panel);
  assert.match(panel.shadowRoot!.textContent!, /Rooms/);
  assert.match(panel.shadowRoot!.textContent!, /Salon personnalisé/);
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
  const high = inputByLabel(panel, "Hauteur solaire haute");
  high.value = "-10"; high.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
  for (const target of [profileLinks()[1], button(panel, "Nouveau profil"), button(panel, "Pièces"), button(panel, "Enregistrer les modifications")]) {
    target.click(); await settle(panel);
    assert.equal(inputByLabel(panel, "Nom").value, "Chaud personnalisé");
    assert.equal(panel.shadowRoot!.activeElement, high);
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
    assert.equal(panel.shadowRoot!.activeElement, button(panel, action));
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
  assert.equal(room.allow_off_during_pause, true);
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
  assert.match(presence.shadowRoot!.textContent!, /binary_sensor.removed.*Indisponible/);
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
  assert.equal(panel.shadowRoot!.activeElement?.className, "import-scene");
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
  emit({ ...importFixture(), status: { lounge: { reason: "manual_pause", is_on: false, available: true } } });
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
  assert.deepEqual((end.scene as Scene).lights, {});
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
  assert.deepEqual((end.scene as Scene).lights, importedScene.lights);
});
