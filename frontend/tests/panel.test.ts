import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { Window } from "happy-dom";
import { newProfile, newRoom } from "../src/model";
import type { HaloEntityPicker } from "../src/entity-picker";
import type { Hass, Snapshot } from "../src/types";

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
      { entity_id: "media_player.tv", name: "TV", state: "off", attributes: {} }] };
}

async function settle(panel: InstanceType<typeof HaloPanel>) {
  await new Promise((resolve) => setTimeout(resolve, 10));
  await panel.updateComplete;
}

async function mount(admin = true, initial = fixture(admin)) {
  let snapshot = initial;
  const calls: Record<string, unknown>[] = [];
  let callback: ((snapshot: Snapshot) => void) | undefined;
  let unsubscribed = 0;
  const hass: Hass = { locale: { language: "fr-BE" }, language: "en", states: {},
    async callWS<T>(message: Record<string, unknown>) {
      calls.push(structuredClone(message));
      if (message.type === "halo/get") return structuredClone(snapshot) as T;
      if (message.type === "halo/save") {
        snapshot = { ...snapshot, config: structuredClone(message.config) as Snapshot["config"], revision: snapshot.revision + 1 };
        return structuredClone(snapshot) as T;
      }
      if (message.type === "halo/edit/begin") return { token: "editor-token" } as T;
      if (message.type === "halo/edit/end") return structuredClone(snapshot) as T;
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

afterEach(() => { window.document.body.replaceChildren(); });

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

test("non-admins can control and run scenes but see no configuration actions", async () => {
  const { panel, calls } = await mount(false);
  assert.equal([...panel.shadowRoot!.querySelectorAll("button")].some((item) => item.textContent?.includes("Réglages globaux")), false);
  button(panel, "Allumer").click();
  await settle(panel);
  assert.deepEqual(calls.find((call) => call.type === "halo/command"), { type: "halo/command", room_id: "lounge", command: "turn_on" });
  button(panel, "Lumières · 2").click();
  await settle(panel);
  assert.equal(panel.shadowRoot!.querySelectorAll("details").length, 0);
  button(panel, "Lancer").click();
  await settle(panel);
  assert.ok(calls.some((call) => call.type === "halo/command" && call.scene_id === "cinema"));
  assert.equal([...panel.shadowRoot!.querySelectorAll("button")].some((item) => item.textContent?.includes("Créer une scène")), false);
});

test("configuring a room is explicit, preserves safe defaults and sends the draft revision", async () => {
  const { panel, calls } = await mount();
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
  button(panel, "Configurer la pièce").click();
  await settle(panel);
  emit({ ...fixture(), revision: 8 });
  await settle(panel);
  assert.equal(button(panel, "Enregistrer les modifications").disabled, true);
  assert.match(panel.shadowRoot!.textContent!, /configuration a changé ailleurs/);
  assert.equal(calls.some((call) => call.type === "halo/save"), false);
  button(panel, "Abandonner les modifications").click();
  await settle(panel);
  assert.match(panel.shadowRoot!.textContent!, /n’existe plus/);
});

test("scene editing takes a server lock, previews compatible controls and cancels with its token", async () => {
  const { panel, calls } = await mount();
  button(panel, "Lumières · 2").click();
  await settle(panel);
  button(panel, "Régler dans la pièce").click();
  await settle(panel);
  assert.ok(calls.some((call) => call.type === "halo/edit/begin" && call.room_id === "lounge"));
  assert.match(panel.shadowRoot!.textContent!, /Tu modifies les lampes réelles/);
  assert.equal(panel.shadowRoot!.querySelector<HaloEntityPicker>(".condition halo-entity-picker")!.value, "media_player.tv");
  const lamps = [...panel.shadowRoot!.querySelectorAll(".lamp")];
  assert.equal(lamps.length, 2);
  assert.ok(lamps[0].textContent?.includes("Luminosité (%)"));
  assert.equal(lamps[1].textContent?.includes("Luminosité (%)"), false);
  const brightness = lamps[0].querySelector<HTMLInputElement>('input[type="number"]')!;
  brightness.value = "42";
  brightness.dispatchEvent(new Event("change", { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 160));
  const preview = [...calls].reverse().find((call) => call.type === "halo/edit/preview")!;
  assert.equal(preview.token, "editor-token");
  assert.equal((preview.lights as Record<string, { brightness_pct: number }>)["light.colour"].brightness_pct, 42);
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

test("saving immediately after a lamp change flushes the final preview before ending the session", async () => {
  const { panel, calls } = await mount();
  button(panel, "Lumières · 2").click(); await settle(panel);
  button(panel, "Régler dans la pièce").click(); await settle(panel);
  const brightness = panel.shadowRoot!.querySelector<HTMLInputElement>('.lamp input[type="number"]')!;
  brightness.value = "63";
  brightness.dispatchEvent(new Event("change", { bubbles: true }));
  await panel.updateComplete;
  button(panel, "Enregistrer la scène").click();
  await settle(panel);
  const previewIndex = calls.findIndex((call) => call.type === "halo/edit/preview");
  const endIndex = calls.findIndex((call) => call.type === "halo/edit/end");
  assert.ok(previewIndex >= 0 && endIndex > previewIndex);
  const saved = calls[endIndex].scene as { lights: Record<string, { brightness_pct: number }> };
  assert.equal(saved.lights["light.colour"].brightness_pct, 63);
  assert.equal(calls[endIndex].revision, 7);
});

test("cancelling clears pending preview work and does not send delayed lamp commands", async () => {
  const { panel, calls } = await mount();
  button(panel, "Lumières · 2").click(); await settle(panel);
  button(panel, "Régler dans la pièce").click(); await settle(panel);
  button(panel, "Annuler").click(); await settle(panel);
  const endIndex = calls.findIndex((call) => call.type === "halo/edit/end");
  await new Promise((resolve) => setTimeout(resolve, 180));
  assert.equal(calls.slice(endIndex + 1).some((call) => call.type === "halo/edit/preview"), false);
});

test("reattaching a panel opens a fresh subscription and abandons its old editor heartbeat", async () => {
  const context = await mount();
  button(context.panel, "Lumières · 2").click(); await settle(context.panel);
  button(context.panel, "Régler dans la pièce").click(); await settle(context.panel);
  context.panel.remove();
  window.document.body.appendChild(context.panel as never);
  await settle(context.panel);
  assert.equal(context.unsubscribed, 1);
  assert.equal(context.calls.filter((call) => call.type === "halo/get").length, 2);
  assert.equal(context.panel.shadowRoot!.querySelector(".editor"), null);
});

test("live state snapshots do not erase text while the user is still typing", async () => {
  const { panel, emit } = await mount();
  button(panel, "Lumières · 2").click(); await settle(panel);
  button(panel, "Régler dans la pièce").click(); await settle(panel);
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
  button(panel, "Lumières · 2").click(); await settle(panel);
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
  button(panel, "Lumières · 2").click(); await settle(panel);
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
  button(panel, "Lumières · 2").click(); await settle(panel);
  button(panel, "Régler dans la pièce").click(); await settle(panel);
  const control = picker(panel, "Entité");
  control.shadowRoot!.querySelector<HTMLButtonElement>("button")!.click(); await settle(panel);
  await searchEntity(control, "media_player.typo");
  button(panel, "Enregistrer la scène").click(); await settle(panel);
  assert.equal(calls.some((call) => call.type === "halo/edit/end"), false);
  assert.match(panel.shadowRoot!.textContent!, /Vérifie les champs/);
  button(panel, "Annuler").click(); await settle(panel);
});

test("brightness uses live sensor units without converting configured values", async () => {
  const snapshot = fixture();
  Object.assign(snapshot.config.rooms.lounge, { lux_entity_id: "sensor.daylight", lux_threshold: 30, lux_hysteresis: 5 });
  snapshot.entities.push({ entity_id: "sensor.daylight", name: "Daylight", state: "50", attributes: { unit_of_measurement: "%" } });
  const { panel, hass, calls } = await mount(true, snapshot);
  button(panel, "Lumières · 2").click(); await settle(panel);
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
  button(panel, "Lumières · 2").click(); await settle(panel);
  const list = panel.shadowRoot!.querySelector(".light-list")!;
  assert.match(list.textContent!.replace(/\s+/g, " "), /Lampe individuelle · Membre de: Bureau/);
  assert.match(list.textContent!.replace(/\s+/g, " "), /Lampe individuelle · Aucun groupe connu/);
  assert.match(list.textContent!.replace(/\s+/g, " "), /Groupe de lumières · Membres: Lampe couleur/);
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
    button(panel, "Réglages globaux").click(); await settle(panel);
    button(panel, "Nouveau profil").click(); await settle(panel);
    button(panel, "Nouveau profil").click(); await settle(panel);
    assert.equal(panel.shadowRoot!.querySelectorAll(".profile").length, 2);
    button(panel, "Enregistrer les modifications").click(); await settle(panel);
    const profiles = (calls.find((call) => call.type === "halo/save")!.config as Snapshot["config"]).profiles;
    const ids = Object.keys(profiles);
    assert.equal(ids.length, 2); assert.notEqual(ids[0], ids[1]);
    button(panel, "Pièces").click(); await settle(panel);
    button(panel, "Lumières · 2").click(); await settle(panel);
    button(panel, "Créer une scène").click(); await settle(panel);
    assert.ok(panel.shadowRoot!.querySelector(".editor"));
    const name = panel.shadowRoot!.querySelector<HTMLInputElement>('.editor input[type="text"]')!;
    name.value = "Test HTTP"; name.dispatchEvent(new Event("change", { bubbles: true })); await settle(panel);
    const filter = panel.shadowRoot!.querySelector<HTMLInputElement>('.editor input[type="search"]')!;
    filter.value = "simple"; filter.dispatchEvent(new Event("input", { bubbles: true })); await settle(panel);
    assert.equal(panel.shadowRoot!.querySelectorAll(".lamp").length, 1);
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
  button(panel, "Lumières · 2").click(); await settle(panel);
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
