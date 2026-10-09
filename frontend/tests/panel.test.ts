import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { Window } from "happy-dom";
import { newRoom } from "../src/model";
import type { Hass, Snapshot } from "../src/types";

const window = new Window({ url: "http://localhost" });
for (const key of ["window", "document", "customElements", "HTMLElement", "Element", "Node", "Document", "ShadowRoot", "CSSStyleSheet", "Event", "CustomEvent"] as const) {
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

async function mount(admin = true) {
  let snapshot = fixture(admin);
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
  assert.equal(panel.shadowRoot!.querySelectorAll<HTMLSelectElement>(".condition select")[1].value, "media_player.tv");
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
