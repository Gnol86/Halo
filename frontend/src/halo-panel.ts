import { LitElement, html, nothing, svg, type PropertyValues, type TemplateResult } from "lit";
import { live } from "lit/directives/live.js";
import { keyed } from "lit/directives/keyed.js";
import { categories, createId, colorMode, dimmable, curveInterpolation, interpolate, moveItem, newCondition, newProfile, newRoom, optionalNumber } from "./model";
import { en, language, translate, type TranslationKey } from "./translations";
import { styles } from "./styles";
import { HaloEntityPicker, matchesEntity } from "./entity-picker";
import type { Condition, Config, Curve, CurveInterpolation, Hass, LampState, Light, Profile, Room, Scene, Snapshot, Transition, Transitions } from "./types";

type Editor = { roomId: string; token: string; scene: Scene; included: Set<string>; revision: number; ready: boolean };
type SceneImport = { roomId: string; revision: number; entityId: string | null; loading: boolean; request: number; error: string; scene?: Scene; ignored?: number };
type RoomSection = "control" | "lights" | "automation" | "ambiences" | "settings";
type FieldOptions = { min?: number; max?: number; step?: number | "any"; required?: boolean; type?: string; unit?: string };

export class HaloPanel extends LitElement {
  static properties = { hass: { attribute: false }, narrow: { type: Boolean }, snapshot: { state: true },
    draft: { state: true }, page: { state: true }, dirty: { state: true }, busy: { state: true },
    error: { state: true }, notice: { state: true }, editor: { state: true }, importer: { state: true }, search: { state: true }, roomSearch: { state: true }, roomSection: { state: true }, selectedProfile: { state: true } };
  static styles = styles;
  declare hass: Hass;
  narrow = false;
  private snapshot?: Snapshot;
  private draft?: Config;
  private revision = 0;
  private viewGeneration = 0;
  private page = "rooms";
  private dirty = false;
  private busy = false;
  private error = "";
  private notice = "";
  private search = "";
  private roomSearch = "";
  private roomSection: RoomSection = "control";
  private selectedProfile = "";
  private lightSearches = new Map<string, string>();
  private editor?: Editor;
  private importer?: SceneImport;
  private unsubscribe?: () => void;
  private connection?: Hass["connection"];
  private connectionGeneration = 0;
  private heartbeat?: ReturnType<typeof setInterval>;
  private previewQueue: Promise<void> = Promise.resolve();
  private dragIndex?: number;
  private removeConfirmation?: string;
  private durationModes = new Set<string>();

  private get locale() { return this.hass?.locale?.language ?? this.hass?.language; }
  private t(key: TranslationKey) { return translate(key, this.locale); }
  private get admin() { return this.snapshot?.is_admin === true; }
  private get room() { return this.draft?.rooms[this.page]; }
  private get hasConflict() { return this.dirty && this.snapshot?.revision !== this.revision; }
  private get editing() { return Boolean(this.editor); }

  protected updated(changed: PropertyValues) {
    if (changed.has("hass")) {
      const dark = this.hass?.themes?.darkMode;
      if (typeof dark === "boolean") this.style.colorScheme = dark ? "dark" : "light";
      else this.style.removeProperty("color-scheme");
    }
    // Options are rendered after the select's property binding on first insertion.
    for (const select of this.renderRoot.querySelectorAll<HTMLSelectElement>("select[data-selected]")) {
      if (select.value !== select.dataset.selected) select.value = select.dataset.selected ?? "";
    }
    if (changed.has("hass") && this.hass?.connection !== this.connection) void this.connect();
  }

  connectedCallback() {
    super.connectedCallback();
    if (this.hass && !this.connection) void this.connect();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this.connectionGeneration++;
    this.unsubscribe?.();
    this.unsubscribe = undefined;
    this.connection = undefined;
    this.clearEditorTimers();
    this.editor = undefined;
    this.importer = undefined;
  }

  private async connect() {
    const generation = ++this.connectionGeneration;
    this.importer = undefined;
    this.unsubscribe?.();
    this.unsubscribe = undefined;
    this.connection = this.hass.connection;
    try {
      const snapshot = await this.hass.callWS<Snapshot>({ type: "halo/get" });
      if (generation !== this.connectionGeneration || !this.isConnected) return;
      this.receive(snapshot);
      const unsubscribe = await this.connection.subscribeMessage<Snapshot>((next) => {
        if (generation === this.connectionGeneration) this.receive(next);
      }, { type: "halo/subscribe" });
      if (generation !== this.connectionGeneration || !this.isConnected) unsubscribe();
      else this.unsubscribe = unsubscribe;
    } catch (error) { if (generation === this.connectionGeneration) this.showError(error); }
  }

  private receive(snapshot: Snapshot) {
    this.snapshot = snapshot;
    if (!this.dirty && !this.editor) {
      this.draft = structuredClone(snapshot.config);
      this.revision = snapshot.revision;
    }
  }

  private showError(error: unknown) {
    const code = typeof error === "object" && error !== null && "code" in error ? String(error.code) : "unknown_error";
    this.error = this.t(code in en ? code as TranslationKey : "unknown_error");
    if (code === "invalid_edit" && this.editor) {
      this.clearEditorTimers();
      this.editor = undefined;
      if (this.snapshot) this.receive(this.snapshot);
    }
  }

  private modify(callback: (config: Config) => void) {
    if (!this.admin || !this.draft || this.editor) return;
    callback(this.draft);
    this.dirty = true;
    this.notice = "";
    this.requestUpdate();
  }

  private modifyRoom(callback: (room: Room) => void) {
    this.modify((config) => { const room = config.rooms[this.page]; if (room) callback(room); });
  }

  private validateFields() {
    const fields = this.renderRoot.querySelectorAll<HTMLInputElement | HTMLSelectElement>("input,select");
    for (const field of fields) {
      if (!field.disabled && !field.checkValidity()) {
        this.revealField(field);
        field.reportValidity();
        field.focus();
        this.error = this.t("validation");
        return false;
      }
    }
    const badCurve = this.renderRoot.querySelector<HTMLElement>(".curve-editor[data-invalid]");
    if (badCurve) {
      const field = badCurve.querySelectorAll<HTMLInputElement>('input[type="number"]')[1];
      if (field) { this.revealField(field); field.focus(); }
      this.error = this.t("badCurve");
      return false;
    }
    for (const picker of this.renderRoot.querySelectorAll<HaloEntityPicker>("halo-entity-picker")) {
      if (picker.required && !picker.value) this.revealField(picker);
      if (!picker.reportValidity()) { this.error = this.t("validation"); return false; }
    }
    return true;
  }

  private revealField(field: Element) {
    for (let parent = field.parentElement; parent; parent = parent.parentElement) {
      if (parent.tagName === "DETAILS") (parent as HTMLDetailsElement).open = true;
    }
  }

  private markFieldDirty() {
    if (!this.admin || this.editor) return;
    this.dirty = true;
    this.notice = "";
  }

  private async save() {
    if (!this.draft || !this.validateFields() || this.busy || this.hasConflict) return;
    this.busy = true;
    this.error = "";
    try {
      const result = await this.hass.callWS<Snapshot>({ type: "halo/save", config: this.draft, revision: this.revision });
      this.dirty = false;
      this.receive(result);
      this.notice = this.t("saved");
    } catch (error) { this.showError(error); }
    finally { this.busy = false; }
  }

  private discard() {
    if (!this.snapshot) return;
    this.dirty = false;
    this.error = "";
    this.notice = "";
    this.durationModes.clear();
    this.viewGeneration++;
    this.receive(this.snapshot);
  }

  private async command(roomId: string, command: string, params: Record<string, unknown> = {}) {
    this.busy = true;
    this.error = "";
    try {
      const result = await this.hass.callWS<Snapshot | undefined>({ type: "halo/command", room_id: roomId, command, ...params });
      if (result?.config) this.receive(result);
    } catch (error) { this.showError(error); }
    finally { this.busy = false; }
  }

  private navigate(page: string) {
    if (this.editing || this.busy || (!this.importer && this.dirty && !this.validateFields())) return false;
    this.importer = undefined;
    this.page = page;
    this.roomSection = "control";
    this.search = "";
    this.lightSearches.clear();
    this.removeConfirmation = undefined;
    this.focusView();
    return true;
  }

  private focusView() {
    void this.updateComplete.then(() => this.renderRoot.querySelector<HTMLElement>(this.page === "rooms" ? ".rail-heading h2" : ".view-title")?.focus());
  }

  private selectRoomSection(section: RoomSection) {
    if (this.editing || this.busy || !this.admin && section !== "control" || this.dirty && !this.validateFields()) return false;
    this.roomSection = section;
    this.error = "";
    return true;
  }

  private roomTabKey(event: KeyboardEvent, section: RoomSection) {
    const sections: RoomSection[] = this.admin ? ["control", "lights", "automation", "ambiences", "settings"] : ["control"];
    const index = sections.indexOf(section);
    const next = event.key === "Home" ? 0 : event.key === "End" ? sections.length - 1
      : event.key === "ArrowRight" ? (index + 1) % sections.length : event.key === "ArrowLeft" ? (index + sections.length - 1) % sections.length : -1;
    if (next < 0) return;
    event.preventDefault();
    if (this.selectRoomSection(sections[next])) void this.updateComplete.then(() => this.renderRoot.querySelector<HTMLElement>(`#room-tab-${sections[next]}`)?.focus());
  }
  private areaName(id: string) { return this.snapshot?.areas.find((area) => area.id === id)?.name ?? id; }
  private light(id: string): Light {
    return this.snapshot?.lights.find((light) => light.entity_id === id) ?? {
      entity_id: id, name: id, area_id: null, available: false, supported_color_modes: [], supported_features: 0,
    };
  }

  private textField(label: TranslationKey, value: string, change: (value: string) => void, options: FieldOptions = {}) {
    return html`<label>${this.t(label)}<input type=${options.type ?? "text"} .value=${value} ?required=${options.required ?? false}
      @input=${(event: Event) => change((event.target as HTMLInputElement).value)}
      @change=${(event: Event) => change((event.target as HTMLInputElement).value)}></label>`;
  }

  private numberField(label: TranslationKey, value: number | null | undefined, change: (value: number | null) => void, options: FieldOptions = {}) {
    return html`<label>${this.t(label)}${options.unit ? ` (${options.unit})` : ""}<input type="number" .value=${value == null ? "" : String(value)}
      min=${options.min ?? nothing} max=${options.max ?? nothing} step=${options.step ?? "any"} ?required=${options.required ?? false}
      @input=${(event: Event) => {
        const field = event.target as HTMLInputElement;
        if (field.validity.valid) change(optionalNumber(field.value));
        else this.markFieldDirty();
      }}
      @change=${(event: Event) => {
        const field = event.target as HTMLInputElement;
        if (field.validity.valid) change(optionalNumber(field.value));
      }}></label>`;
  }

  private check(label: TranslationKey, checked: boolean, change: (value: boolean) => void, disabled = false) {
    return html`<label class="check"><input type="checkbox" .checked=${live(checked)} ?disabled=${disabled}
      @change=${(event: Event) => change((event.target as HTMLInputElement).checked)}>${this.t(label)}</label>`;
  }

  private entityField(label: TranslationKey, value: string | null, change: (value: string | null) => void, domain?: string, required = false) {
    const entities = (this.snapshot?.entities ?? []).filter((entity) => !domain || entity.entity_id.startsWith(`${domain}.`)).map((entity) =>
      // A scene reports "unknown" until its first activation; its configuration can still be read.
      domain === "scene" && entity.state === "unknown" ? { ...entity, state: undefined } : entity);
    return html`<halo-entity-picker .label=${this.t(label)} .locale=${this.locale} .entities=${entities} .value=${value} .required=${required}
      @entity-changed=${(event: CustomEvent<{ value: string | null }>) => change(event.detail.value)}></halo-entity-picker>`;
  }

  private lightSearch(key: string) {
    return html`<label>${this.t("search")}<input type="search" .value=${this.lightSearches.get(key) ?? ""} @input=${(event: Event) => {
      this.lightSearches.set(key, (event.target as HTMLInputElement).value); this.requestUpdate();
    }}></label>`;
  }

  private filteredLights(ids: string[], key: string) {
    return ids.filter((id) => matchesEntity(this.light(id), this.lightSearches.get(key) ?? ""));
  }

  private groupDetails(light: Light) {
    const names = (ids: string[]) => ids.map((id) => this.snapshot?.entities.find((entity) => entity.entity_id === id)?.name ?? this.light(id).name).join(", ");
    return html`<small class="group-info">${this.t(light.is_group == null ? "groupUnknown" : light.is_group ? "lightGroup" : "individualLight")}
      ${light.is_group && light.group_members?.length ? html` · ${this.t("groupMembers")}: ${names(light.group_members)}` : nothing}
      ${light.member_of?.length ? html` · ${this.t("memberOf")}: ${names(light.member_of)}` : light.is_group === false ? html` · ${this.t("noKnownGroup")}` : nothing}</small>`;
  }

  private help(text: TranslationKey, title: TranslationKey = "howItWorks") {
    return html`<details class="help-details"><summary><ha-icon icon="mdi:information-outline"></ha-icon>${this.t(title)}</summary><p class="help">${this.t(text)}</p></details>`;
  }

  protected render() {
    const roomPage = this.page !== "global" && this.page !== "profiles";
    return html`<header class="app-header"><div class="brand"><ha-icon icon="mdi:spa"></ha-icon><h1>Halo</h1></div>
      <nav class="top-nav" aria-label="Halo"><button aria-current=${roomPage ? "page" : nothing} ?disabled=${this.editing || this.busy} @click=${() => this.navigate("rooms")}>${this.t("rooms")}</button>
        ${this.admin ? html`<button aria-current=${this.page === "profiles" ? "page" : nothing} ?disabled=${this.editing || this.busy} @click=${() => this.navigate("profiles")}>${this.t("profiles")}</button>
          <button aria-current=${this.page === "global" ? "page" : nothing} ?disabled=${this.editing || this.busy} @click=${() => this.navigate("global")}>${this.t("global")}</button>` : nothing}</nav>
    </header>
      <div class="content"><main lang=${language(this.locale)}>
        ${this.error ? html`<div class="notice error" role="alert"><ha-icon icon="mdi:alert-circle-outline"></ha-icon><span class="grow">${this.error}</span><button ?disabled=${this.editing} @click=${() => this.connect()}>${this.t("retry")}</button></div>` : nothing}
        ${this.notice ? html`<div class="notice" role="status"><ha-icon icon="mdi:check-circle-outline"></ha-icon>${this.notice}</div>` : nothing}
        ${!this.snapshot || !this.draft ? html`<p role="status">${this.t("loading")}</p><button @click=${() => this.connect()}>${this.t("retry")}</button>`
          : keyed(this.viewGeneration, this.page === "profiles" && this.admin ? this.renderProfiles()
          : this.page === "global" && this.admin ? this.renderGlobal() : this.renderWorkspace())}
      </main></div>
      ${this.dirty ? html`<div class="savebar" role="status"><span class="grow">${this.hasConflict ? this.t("conflict") : this.t("unsaved")}</span>
        <button ?disabled=${this.busy} @click=${this.discard}>${this.t("discard")}</button><button class="primary" ?disabled=${this.busy || this.hasConflict} @click=${this.save}>${this.t("save")}</button></div>` : nothing}`;
  }

  private renderWorkspace() {
    const selected = this.page !== "rooms" && this.page !== "global" && this.page !== "profiles";
    return html`<div class="workspace ${selected ? "has-room" : ""}">
      ${this.renderRooms()}
      <div class="room-detail">${this.editor ? this.renderEditor(this.editor) : this.importer && this.admin ? this.renderImport(this.importer)
        : selected ? this.renderRoom() : html`<div class="empty-state welcome"><ha-icon icon="mdi:lightbulb-group-outline"></ha-icon><h2 class="view-title" tabindex="-1">${this.t("chooseRoom")}</h2><p>${this.t("chooseRoomHelp")}</p>${!this.admin ? html`<p class="help">${this.t("adminOnly")}</p>` : nothing}</div>`}</div>
    </div>`;
  }

  private status(roomId: string) {
    const status = this.snapshot?.status[roomId];
    if (!status) return html`<span class="badge">${this.t("idle")}</span>`;
    const reason = status.reason ?? "idle";
    const key = reason in en ? reason as TranslationKey : "idle";
    const scene = this.draft?.rooms[roomId]?.scenes.find((item) => item.id === status.scene_id);
    return html`<div aria-label=${this.t("status")}><span class="badge">${this.t(key)}${scene ? ` · ${scene.name}` : ""}</span>
      <span class="badge">${this.t(status.available === false ? "unavailable" : status.is_on ? "on" : "off")}</span>
      ${([["pause_until", "pauseUntil"], ["absence_deadline", "absenceDeadline"], ["lux_off_deadline", "luxDeadline"]] as const).map(([field, label]) => {
        const value = status[field];
        if (!value) return nothing;
        const date = new Date(typeof value === "number" ? value * 1000 : String(value));
        return Number.isNaN(date.getTime()) ? nothing : html`<p class="help status-line">${this.t(label)} ${date.toLocaleTimeString(language(this.locale), { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</p>`;
      })}</div>`;
  }

  private controls(room: Room) {
    const actual = this.snapshot?.config.rooms[room.id] ?? room;
    const disabled = this.busy || this.editing || !this.snapshot?.config.rooms[room.id];
    return html`<div class="room-toolbar"><div class="actions"><button ?disabled=${disabled} @click=${() => this.command(room.id, "turn_on")}><ha-icon icon="mdi:lightbulb-on-outline"></ha-icon>${this.t("turnOn")}</button>
      <button ?disabled=${disabled} @click=${() => this.command(room.id, "turn_off")}><ha-icon icon="mdi:lightbulb-off-outline"></ha-icon>${this.t("turnOff")}</button>
      <button ?disabled=${disabled || this.dirty} @click=${() => this.command(room.id, "resume")}><ha-icon icon="mdi:play-circle-outline"></ha-icon>${this.t("resumeShort")}</button></div>
      <div class="room-modes">${this.check("automationShort", actual.automation_enabled, (enabled) => { void this.command(room.id, "automation", { enabled }); }, disabled || this.dirty)}
        ${this.check("natural", actual.natural_enabled, (enabled) => { void this.command(room.id, "natural", { enabled }); }, disabled || this.dirty)}</div></div>
      ${this.dirty ? html`<p class="help compact-help">${this.t(this.snapshot?.config.rooms[room.id] ? "saveModesFirst" : "saveFirst")}</p>` : nothing}`;
  }

  private renderRooms() {
    const areas = [...this.snapshot!.areas];
    for (const roomId of Object.keys(this.draft!.rooms)) if (!areas.some((area) => area.id === roomId)) areas.push({ id: roomId, name: roomId });
    areas.sort((left, right) => Number(Boolean(this.draft!.rooms[right.id])) - Number(Boolean(this.draft!.rooms[left.id])));
    const filtered = areas.filter((area) => matchesEntity({ entity_id: area.id, name: area.name }, this.roomSearch));
    return html`<aside class="room-rail" aria-label=${this.t("rooms")}><div class="rail-heading"><h2 tabindex="-1">${this.t("rooms")}</h2><span class="count">${areas.length}</span></div>
      <label class="rail-search"><span>${this.t("searchRooms")}</span><input type="search" .value=${this.roomSearch} @input=${(event: Event) => { this.roomSearch = (event.target as HTMLInputElement).value; }}></label>
      ${areas.length === 0 ? html`<p class="empty">${this.t("noRooms")}</p>` : nothing}
      <div class="room-list">${filtered.map((area) => {
        const room = this.draft!.rooms[area.id];
        const state = this.snapshot?.status[area.id];
        const reason = state?.reason ?? "idle";
        const key = reason in en ? reason as TranslationKey : "idle";
        const on = state?.is_on === true;
        return html`<div class="room-item" ?data-active=${this.page === area.id} data-state=${state?.available === false ? "unavailable" : on ? "on" : "off"}>
          <button class="room-link" aria-label=${area.name} aria-current=${this.page === area.id ? "page" : nothing} ?disabled=${this.editing || this.busy} @click=${() => this.navigate(area.id)}>
            <ha-icon icon=${room ? on ? "mdi:lightbulb-on-outline" : "mdi:lightbulb-outline" : "mdi:plus-circle-outline"}></ha-icon><span><strong>${area.name}</strong>
              <small class="room-meta">${room ? `${room.lights.length} ${this.t("lightsCount")} · ${this.t(state?.available === false ? "unavailable" : key)}` : this.t("unconfigured")}</small></span>
          </button>
          ${room ? html`<button class="icon-button quick-toggle" aria-pressed=${String(on)} aria-label=${`${this.t(on ? "turnOff" : "turnOn")} · ${area.name}`} title=${this.t(on ? "turnOff" : "turnOn")} ?disabled=${this.busy || this.editing || !this.snapshot?.config.rooms[room.id] || state?.available === false}
            @click=${() => this.command(room.id, on ? "turn_off" : "turn_on")}><ha-icon icon="mdi:power"></ha-icon></button>` : nothing}
        </div>`;
      })}</div>${areas.length && !filtered.length ? html`<p class="empty">${this.t("noRoomsMatch")}</p>` : nothing}</aside>`;
  }

  private renderRoom() {
    const room = this.room;
    const heading = html`<div class="room-heading"><button class="icon-button room-back back-button" aria-label=${this.t("back")} @click=${() => this.navigate("rooms")}><ha-icon icon="mdi:arrow-left"></ha-icon></button>
      <h2 class="view-title grow" tabindex="-1">${this.areaName(this.page)}</h2></div>`;
    if (!room) return html`${heading}<div class="empty-state"><ha-icon icon="mdi:lightbulb-group-outline"></ha-icon><h3>${this.t("roomNotConfigured")}</h3><p>${this.t("configureRoomHelp")}</p>
      ${this.admin ? html`<button class="primary" @click=${() => { this.modify((config) => { config.rooms[this.page] = newRoom(this.page); }); this.roomSection = "lights"; }}>${this.t("configure")}</button>` : html`<p class="help">${this.t("adminOnly")}</p>`}</div>`;
    const sections: [RoomSection, TranslationKey][] = [["control", "controlTab"], ["lights", "lights"], ["automation", "automationShort"], ["ambiences", "ambiencesTab"], ["settings", "settingsTab"]];
    const activeSection = this.admin ? this.roomSection : "control";
    return html`${heading}<div class="room-summary">${this.status(room.id)}${this.controls(room)}</div>
      <nav class="room-tabs" role="tablist" aria-label=${this.t("roomSections")}>${sections.filter(([key]) => this.admin || key === "control").map(([key, label]) => html`<button role="tab" id=${`room-tab-${key}`} aria-controls="room-panel" aria-selected=${String(activeSection === key)} tabindex=${activeSection === key ? "0" : "-1"}
        @keydown=${(event: KeyboardEvent) => this.roomTabKey(event, key)} @click=${() => this.selectRoomSection(key)}>${this.t(label)}</button>`)}</nav>
      <div id="room-panel" class="room-panel" role="tabpanel" aria-labelledby=${`room-tab-${activeSection}`}>
        ${activeSection === "control" ? this.renderScenes(room) : activeSection === "lights" ? this.renderLightSelection(room)
          : activeSection === "automation" ? this.renderAutomation(room) : activeSection === "ambiences" ? html`${this.renderAssociations(room)}<section class="base-section"><div class="section-heading"><h3>${this.t("base")}</h3>${this.help("baseHelp")}</div>
              ${this.lightSearch("base")}${this.filteredLights(room.lights, "base").map((id) => this.lampEditor(id, room.base[id], (value) => this.modifyRoom((current) => { if (value) current.base[id] = value; else delete current.base[id]; }), true))}</section>`
          : html`<section><div class="section-heading"><h3>${this.t("transitions")}</h3></div>${this.renderTransitions(room.transitions, (category, value) => this.modifyRoom((current) => { current.transitions[category] = value; }), room.id)}</section>
            <details class="danger-zone"><summary>${this.t("removeRoom")}</summary><p class="help">${this.t("removeRoomHelp")}</p><button class="danger" @click=${() => {
              if (this.removeConfirmation === room.id) { this.modify((config) => { delete config.rooms[room.id]; }); this.removeConfirmation = undefined; }
              else { this.removeConfirmation = room.id; this.requestUpdate(); }
            }}>${this.t(this.removeConfirmation === room.id ? "confirmRemove" : "removeRoom")}</button></details>`}
      </div>`;
  }

  private renderLightSelection(room: Room) {
    const assigned = new Set(Object.values(this.draft!.rooms).filter((other) => other.id !== room.id).flatMap((other) => other.lights));
    const lights = [...this.snapshot!.lights];
    for (const id of room.lights) if (!lights.some((light) => light.entity_id === id)) lights.push(this.light(id));
    const filtered = lights.filter((light) => matchesEntity(light, this.search));
    return html`<section class="light-selection"><div class="section-heading"><h3>${this.t("lights")} <span class="count">${room.lights.length}</span></h3>${this.help("lightsHelp")}</div>
      <label>${this.t("search")}<input type="search" .value=${this.search} @input=${(event: Event) => { this.search = (event.target as HTMLInputElement).value; }}></label>
      <div class="light-list">${[true, false].map((own) => html`<h3>${this.t(own ? "ownArea" : "otherAreas")}</h3>
        ${filtered.filter((light) => (light.area_id === room.id) === own).map((light) => html`<div class="light-option"><label class="check">
          <input type="checkbox" .checked=${live(room.lights.includes(light.entity_id))} ?disabled=${assigned.has(light.entity_id)} @change=${(event: Event) => this.modifyRoom((current) => {
            if ((event.target as HTMLInputElement).checked) current.lights.push(light.entity_id);
            else { current.lights = current.lights.filter((id) => id !== light.entity_id); delete current.base[light.entity_id];
              for (const scene of current.scenes) delete scene.lights[light.entity_id];
              for (const association of current.associations) association.lights = association.lights.filter((id) => id !== light.entity_id); }
          })}><span>${light.name}<small>${light.entity_id}${assigned.has(light.entity_id) ? ` · ${this.t("assigned")}` : ""}${!light.available ? ` · ${this.t("unavailable")}` : ""}</small>${this.groupDetails(light)}</span></label></div>`)}`)}${filtered.length === 0 ? html`<p role="status">${this.t("noResults")}</p>` : nothing}</div></section>`;
  }

  private renderAutomation(room: Room) {
    const attributes = room.lux_entity_id ? (this.hass.states?.[room.lux_entity_id] ?? this.snapshot?.entities.find((entity) => entity.entity_id === room.lux_entity_id))?.attributes : undefined;
    const unit = typeof attributes?.unit_of_measurement === "string" ? attributes.unit_of_measurement.trim() : "";
    const suffix = unit ? ` ${unit}` : "";
    return html`<section class="automation-section"><div class="settings-group"><h3>${this.t("presence")}</h3><div class="field-grid">
      ${this.entityField("presenceEntity", room.presence_entity_id, (value) => this.modifyRoom((current) => { current.presence_entity_id = value; }))}
      ${this.textField("presentStates", room.presence_states.join(", "), (value) => this.modifyRoom((current) => { current.presence_states = value.split(",").map((state) => state.trim()).filter(Boolean); }), { required: Boolean(room.presence_entity_id) })}
      ${this.numberField("absenceDelay", room.absence_delay, (value) => this.modifyRoom((current) => { current.absence_delay = value ?? 0; }), { min: 0, required: true })}</div></div>
      <div class="settings-group"><h3>${this.t("lux")}</h3>${this.entityField("luxEntity", room.lux_entity_id, (value) => this.modifyRoom((current) => { current.lux_entity_id = value; }), "sensor")}
      ${room.lux_entity_id ? html`<div class="field-grid">${this.numberField("luxThreshold", room.lux_threshold, (value) => this.modifyRoom((current) => { current.lux_threshold = value; }), { min: 0, required: true, unit })}
        ${this.numberField("hysteresis", room.lux_hysteresis, (value) => this.modifyRoom((current) => { current.lux_hysteresis = value ?? 0; }), { min: 0, required: true, unit })}</div>
        <p>${this.t("effectiveLow")}: ${room.lux_threshold ?? "—"}${suffix} · ${this.t("effectiveHigh")}: ${room.lux_threshold == null ? "—" : room.lux_threshold + room.lux_hysteresis}${suffix}</p>
        ${!unit ? html`<p class="help">${this.t("unknownUnit")}</p>` : nothing}
        ${this.check("luxOff", room.lux_off, (value) => this.modifyRoom((current) => { current.lux_off = value; }))}
        ${room.lux_off ? this.numberField("luxDelay", room.lux_off_delay, (value) => this.modifyRoom((current) => { current.lux_off_delay = value ?? 30; }), { min: 0, required: true }) : nothing}
        ${this.help("luxHelp")}` : nothing}</div>
      <div class="settings-group"><div class="section-heading"><h3>${this.t("manual")}</h3>${this.help("pauseHelp")}</div>${this.numberField("pauseDuration", room.manual_pause / 60, (value) => this.modifyRoom((current) => { current.manual_pause = (value ?? 120) * 60; }), { min: 0, required: true })}
      ${this.check("allowOff", room.allow_off_during_pause, (value) => this.modifyRoom((current) => { current.allow_off_during_pause = value; }))}</div></section>`;
  }

  private renderAssociations(room: Room) {
    const profiles = Object.values(this.draft!.profiles);
    return html`<section class="associations-section"><div class="section-heading"><h3>${this.t("associations")}</h3>${this.help("associationHelp")}</div>
      ${room.associations.map((association, index) => html`<details class="association" ?open=${room.associations.length === 1}><summary><span>${profiles.find((profile) => profile.id === association.profile_id)?.name ?? this.t("noProfile")}</span><small>${association.lights.length} ${this.t("lightsCount")} · ${association.brightness_offset > 0 ? "+" : ""}${association.brightness_offset} %</small></summary><div class="row"><label class="grow">${this.t("profile")}<select required data-selected=${association.profile_id} .value=${live(association.profile_id)} @change=${(event: Event) => this.modifyRoom((current) => { current.associations[index].profile_id = (event.target as HTMLSelectElement).value; })}>
        <option value="" ?selected=${!association.profile_id}>${this.t("noProfile")}</option>${profiles.map((profile) => html`<option value=${profile.id} ?selected=${profile.id === association.profile_id}>${profile.name}</option>`)}</select></label>
        <button @click=${() => this.modifyRoom((current) => { current.associations.splice(index, 1); })}>${this.t("remove")}</button></div>
        ${this.numberField("offset", association.brightness_offset, (value) => this.modifyRoom((current) => { current.associations[index].brightness_offset = value ?? 0; }), { min: -100, max: 1000, required: true })}${this.help("offsetHelp")}
        ${this.lightSearch(`association-${index}`)}
        ${this.filteredLights(room.lights, `association-${index}`).filter((id) => dimmable(this.light(id))).map((id) => {
          const used = room.associations.some((other, otherIndex) => otherIndex !== index && other.lights.includes(id));
          return html`<label class="check"><input type="checkbox" .checked=${live(association.lights.includes(id))} ?disabled=${used} @change=${(event: Event) => this.modifyRoom((current) => {
            const target = current.associations[index]; target.lights = (event.target as HTMLInputElement).checked ? [...target.lights, id] : target.lights.filter((light) => light !== id);
          })}><span>${this.light(id).name}<small>${id}</small>${this.groupDetails(this.light(id))}</span></label>`;
        })}</details>`)}
      ${profiles.length ? html`<button @click=${() => this.modifyRoom((current) => { current.associations.push({ profile_id: profiles[0].id, lights: [], brightness_offset: 0 }); })}>${this.t("addAssociation")}</button>` : html`<p>${this.t("noProfiles")}</p><button @click=${() => this.navigate("profiles")}>${this.t("profiles")}</button>`}</section>`;
  }

  private lampEditor(id: string, value: LampState | undefined, change: (value?: LampState) => void, optional: boolean) {
    const light = this.light(id);
    const selectedMode = value?.color_temp_kelvin != null ? "temperature" : value?.rgb_color ? "rgb_color" : value?.hs_color ? "hs_color" : value?.xy_color ? "xy_color" : "";
    const mode = colorMode(light);
    const update = (patch: Partial<LampState>) => change({ state: "on", ...value, ...patch });
    const modes: [string, TranslationKey][] = [["", "keepColor"]];
    if (light.supported_color_modes.includes("color_temp")) modes.push(["temperature", "nativeWhite"]);
    if (mode) modes.push([mode, mode === "rgb_color" ? "rgb" : mode === "hs_color" ? "hs" : "xy"]);
    return html`<details class="lamp"><summary><span>${light.name}</span><small>${!light.available ? this.t("unavailable") : value ? this.t(value.state) : this.t("defaultSetting")}</small></summary><small>${id}</small>${this.groupDetails(light)}
      ${optional ? this.check("include", Boolean(value), (checked) => change(checked ? { state: "on" } : undefined)) : nothing}
      ${value ? html`<label>${this.t("state")}<select data-selected=${value.state} .value=${live(value.state)} @change=${(event: Event) => update({ state: (event.target as HTMLSelectElement).value as "on" | "off" })}>
        <option value="on" ?selected=${value.state === "on"}>${this.t("on")}</option><option value="off" ?selected=${value.state === "off"}>${this.t("off")}</option></select></label>
        ${value.state === "on" ? html`<div class="field-grid">
          ${dimmable(light) ? this.numberField("brightness", value.brightness_pct, (brightness) => { const next = { ...value }; if (brightness == null) delete next.brightness_pct; else next.brightness_pct = brightness; change(next); }, { min: 0, max: 100 }) : nothing}
          ${modes.length > 1 ? html`<label>${this.t("colorMode")}<select data-selected=${selectedMode} .value=${live(selectedMode)} @change=${(event: Event) => {
            const selected = (event.target as HTMLSelectElement).value; const next = { ...value }; delete next.color_temp_kelvin; delete next.rgb_color; delete next.hs_color; delete next.xy_color;
            if (selected === "temperature") next.color_temp_kelvin = Math.max(light.min_color_temp_kelvin ?? 2000, Math.min(3000, light.max_color_temp_kelvin ?? 6500));
            if (selected === "rgb_color") next.rgb_color = [255, 255, 255]; if (selected === "hs_color") next.hs_color = [0, 0]; if (selected === "xy_color") next.xy_color = [.323, .329]; change(next);
          }}>${modes.map(([key, label]) => html`<option value=${key} ?selected=${key === selectedMode}>${this.t(label)}</option>`)}</select></label>` : nothing}
          ${selectedMode === "temperature" ? this.numberField("temperature", value.color_temp_kelvin, (temperature) => update({ color_temp_kelvin: temperature ?? light.min_color_temp_kelvin ?? 2000 }), { min: light.min_color_temp_kelvin ?? 1000, max: light.max_color_temp_kelvin ?? 40000, required: true }) : nothing}
          ${selectedMode === "rgb_color" ? html`<label>${this.t("color")}<input type="color" .value=${live(`#${value.rgb_color!.map((channel) => Math.round(channel).toString(16).padStart(2, "0")).join("")}`)} @input=${(event: Event) => { const hex = (event.target as HTMLInputElement).value; update({ rgb_color: [1, 3, 5].map((index) => Number.parseInt(hex.slice(index, index + 2), 16)) }); }}></label>` : nothing}
          ${selectedMode === "hs_color" || selectedMode === "xy_color" ? ([0, 1] as const).map((index) => {
            const prop = selectedMode as "hs_color" | "xy_color";
            return this.numberField(prop === "hs_color" ? index === 0 ? "hue" : "saturation" : index === 0 ? "x" : "y", value[prop]![index], (component) => { const channels = [...value[prop]!]; channels[index] = component ?? 0; update({ [prop]: channels }); }, { min: 0, max: prop === "hs_color" ? index === 0 ? 360 : 100 : 1, required: true });
          }) : nothing}
        </div>` : nothing}` : html`<p class="help">${this.t("defaultSetting")}</p>`}</details>`;
  }

  private renderScenes(room: Room) {
    return html`<section class="scenes-section"><div class="section-heading"><div><h3>${this.t("scenes")}</h3><p class="help compact-help">${this.t("scenesBrief")}</p></div>
      ${this.admin ? html`<div class="section-actions"><button class="primary create-scene" ?disabled=${this.busy || this.dirty || room.lights.length === 0} @click=${() => this.startEditor(room)}><ha-icon icon="mdi:plus"></ha-icon>${this.t("createScene")}</button>
        <button class="import-scene" ?disabled=${this.busy || this.dirty || room.lights.length === 0 || !this.snapshot?.config.rooms[room.id]} @click=${() => this.startImport(room)}><ha-icon icon="mdi:import"></ha-icon>${this.t("importScene")}</button></div>` : nothing}</div>
      ${room.scenes.length === 0 ? html`<div class="empty-state"><ha-icon icon="mdi:palette-outline"></ha-icon><p>${this.t("noScenes")}</p>${this.admin ? html`<p class="help">${this.t("noScenesHelp")}</p>` : nothing}</div>` : nothing}
      <div class="scenes-list">${room.scenes.map((scene, index) => html`<div class="scene-row" data-scene-id=${scene.id} tabindex="-1" draggable=${this.admin && !this.busy ? "true" : "false"}
        @dragstart=${(event: DragEvent) => { this.dragIndex = index; event.dataTransfer?.setData("text/plain", scene.id); }}
        @dragover=${(event: DragEvent) => { if (this.admin) event.preventDefault(); }}
        @drop=${(event: DragEvent) => { event.preventDefault(); if (this.admin && this.dragIndex != null) this.modifyRoom((current) => { current.scenes = moveItem(current.scenes, this.dragIndex!, index); }); this.dragIndex = undefined; }}>
        <span class="scene-order" aria-label=${`${this.t("priority")} ${index + 1}`}>${index + 1}</span><div class="grow"><strong>${scene.name}</strong><small class="scene-meta">${Object.keys(scene.lights).length} ${this.t("lightsCount")} · ${this.t(scene.conditions ? "conditionalScene" : "manualScene")}${scene.can_turn_on ? ` · ${this.t("sceneMayTurnOn")}` : ""}</small></div>
        <div class="actions"><button ?disabled=${this.busy || this.dirty} @click=${() => this.command(room.id, "scene", { scene_id: scene.id })}><ha-icon icon="mdi:play"></ha-icon>${this.t("run")}</button>
          ${this.admin ? html`<button class="edit-scene" data-scene-id=${scene.id} ?disabled=${this.busy || this.dirty} @click=${() => this.startEditor(room, scene)}>${this.t("editSceneShort")}</button>
            <details class="row-menu"><summary class="icon-button" aria-label=${`${this.t("sceneActions")} · ${scene.name}`} title=${this.t("sceneActions")}><ha-icon icon="mdi:dots-vertical"></ha-icon></summary><div class="menu-actions">
              <button aria-label=${`${this.t("up")} ${scene.name}`} ?disabled=${index === 0 || this.busy} @click=${() => this.modifyRoom((current) => { current.scenes = moveItem(current.scenes, index, index - 1); })}><ha-icon icon="mdi:arrow-up"></ha-icon>${this.t("up")}</button>
              <button aria-label=${`${this.t("down")} ${scene.name}`} ?disabled=${index === room.scenes.length - 1 || this.busy} @click=${() => this.modifyRoom((current) => { current.scenes = moveItem(current.scenes, index, index + 1); })}><ha-icon icon="mdi:arrow-down"></ha-icon>${this.t("down")}</button>
              <button class="danger" aria-label=${`${this.t("remove")} ${scene.name}`} ?disabled=${this.busy} @click=${() => this.modifyRoom((current) => { current.scenes.splice(index, 1); })}><ha-icon icon="mdi:delete-outline"></ha-icon>${this.t("remove")}</button>
            </div></details>` : nothing}</div></div>`)}</div>
      ${this.help("scenesHelp", "scenePriorityHelp")}
      ${this.admin && this.dirty ? html`<p class="help">${this.t("editFirstSave")}</p>` : nothing}</section>`;
  }

  private startImport(room: Room) {
    if (!this.admin || this.busy || this.dirty || this.editor || !this.snapshot?.config.rooms[room.id] || !room.lights.length) return;
    this.error = "";
    this.notice = "";
    this.importer = { roomId: room.id, revision: this.revision, entityId: null, loading: false, request: 0, error: "" };
    void this.updateComplete.then(() => this.renderRoot.querySelector<HTMLElement>("#import-title")?.focus());
  }

  private closeImport(focusSceneId?: string) {
    this.importer = undefined;
    this.roomSection = "control";
    void this.updateComplete.then(() => {
      const row = focusSceneId ? [...this.renderRoot.querySelectorAll<HTMLElement>(".scene-row")].find((element) => element.dataset.sceneId === focusSceneId) : undefined;
      (row ?? this.renderRoot.querySelector<HTMLButtonElement>(".import-scene"))?.focus();
    });
  }

  private importChanged(importer: SceneImport) {
    return !this.admin || this.dirty || importer.revision !== this.snapshot?.revision || !this.draft?.rooms[importer.roomId];
  }

  private async loadImport(importer: SceneImport, entityId: string | null) {
    if (this.importer !== importer || !this.admin) return;
    importer.entityId = entityId;
    importer.scene = undefined;
    importer.ignored = undefined;
    importer.error = "";
    importer.loading = false;
    const request = ++importer.request;
    const generation = this.connectionGeneration;
    const current = () => this.importer === importer && request === importer.request && generation === this.connectionGeneration && this.isConnected;
    if (!entityId) { this.requestUpdate(); return; }
    const entity = this.hass.states?.[entityId] ?? this.snapshot?.entities.find((item) => item.entity_id === entityId);
    const id = entity?.attributes.id;
    if (!entityId.startsWith("scene.") || typeof id !== "string" || !id.trim()) {
      importer.error = this.t("importUnavailable"); this.requestUpdate(); return;
    }
    if (this.importChanged(importer)) { this.requestUpdate(); return; }
    importer.loading = true;
    this.requestUpdate();
    try {
      const config = await this.hass.callApi<unknown>("GET", `config/scene/config/${encodeURIComponent(id)}`);
      if (!current() || this.importChanged(importer)) return;
      const result = await this.hass.callWS<{ scene: Scene; ignored_entities: number }>({ type: "halo/scene/import", room_id: importer.roomId, config });
      if (!current() || this.importChanged(importer)) return;
      importer.scene = structuredClone(result.scene);
      importer.ignored = result.ignored_entities;
    } catch (error) {
      if (current()) {
        const code = typeof error === "object" && error !== null && "code" in error ? String(error.code) : "";
        const status = typeof error === "object" && error !== null && "status_code" in error ? error.status_code : undefined;
        const detail = typeof error === "object" && error !== null && "message" in error && typeof error.message === "string" ? error.message : "";
        importer.error = code === "invalid_config" ? `${this.t("importInvalid")}${detail ? ` ${detail}` : ""}`
          : this.t(code in en ? code as TranslationKey : status === 401 || status === 403 ? "unauthorized" : status === 404 ? "importUnavailable" : "importFailed");
      }
    } finally {
      if (current()) { importer.loading = false; this.requestUpdate(); }
    }
  }

  private confirmImport(importer: SceneImport) {
    if (this.importer !== importer || importer.loading || !importer.scene || this.importChanged(importer) || !this.validateFields()) return;
    const scene = structuredClone(importer.scene);
    scene.name = scene.name.trim();
    if (!scene.name) { importer.error = this.t("validation"); this.requestUpdate(); return; }
    this.modify((config) => { config.rooms[importer.roomId].scenes.push(scene); });
    this.closeImport(scene.id);
  }

  private renderImport(importer: SceneImport) {
    const conflict = this.importChanged(importer);
    return html`<section class="scene-import" aria-labelledby="import-title"><div class="section-heading"><h2 id="import-title" class="view-title" tabindex="-1">${this.t("importScene")} <small>${this.areaName(importer.roomId)}</small></h2></div>
      <p class="help">${this.t("importIntro")}</p>${this.help("importHelp", "importCompatibility")}
      ${this.entityField("sourceScene", importer.entityId, (value) => { void this.loadImport(importer, value); }, "scene", true)}
      ${importer.loading ? html`<p role="status">${this.t("importLoading")}</p>` : nothing}
      ${conflict ? html`<p class="notice error" role="alert">${this.t("importConflict")}</p>` : nothing}
      ${importer.error ? html`<p class="notice error" role="alert">${importer.error}</p>` : nothing}
      ${importer.scene ? html`<label>${this.t("sceneName")}<input type="text" required .value=${importer.scene.name}
          @input=${(event: Event) => {
            if (importer.scene) importer.scene.name = (event.target as HTMLInputElement).value;
            this.requestUpdate();
          }}></label>
        <h3>${this.t("importRetained")}</h3><ul class="import-lights">${Object.keys(importer.scene.lights).map((id) => html`<li>${this.light(id).name}<small>${id}</small></li>`)}</ul>
        <p role="status">${this.t("importIgnored")}: ${importer.ignored}</p>${this.help("importPartial", "importCopyHelp")}` : nothing}
      <div class="actions"><button @click=${() => this.closeImport()}>${this.t("cancel")}</button>
        <button class="primary" ?disabled=${conflict || importer.loading || !importer.scene} @click=${() => this.confirmImport(importer)}>${this.t("confirmImport")}</button></div>
    </section>`;
  }

  private liveLamp(id: string) {
    return this.hass.states?.[id] ?? this.snapshot?.entities.find((item) => item.entity_id === id);
  }

  private actualLampState(id: string): LampState | undefined {
    const entity = this.liveLamp(id);
    if (!entity || !["on", "off"].includes(entity.state)) return undefined;
    const attributes = entity?.attributes ?? {};
    const state: LampState = { state: entity.state as "on" | "off" };
    if (typeof attributes.brightness === "number") state.brightness = attributes.brightness;
    if (typeof attributes.effect === "string") state.effect = attributes.effect;
    if (typeof attributes.color_mode === "string" && ["onoff", "brightness", "color_temp", "hs", "rgb", "rgbw", "rgbww", "xy", "white"].includes(attributes.color_mode)) state.color_mode = attributes.color_mode;
    if (state.color_mode === "color_temp" && typeof attributes.color_temp_kelvin === "number") state.color_temp_kelvin = attributes.color_temp_kelvin;
    const mode = `${state.color_mode}_color`;
    if (["rgb_color", "rgbw_color", "rgbww_color", "hs_color", "xy_color"].includes(mode) && Array.isArray(attributes[mode])) {
      state[mode as "rgb_color" | "rgbw_color" | "rgbww_color" | "hs_color" | "xy_color"] = [...attributes[mode] as number[]];
    }
    if (state.color_mode === "white" && typeof attributes.brightness === "number") state.white = attributes.brightness;
    return state;
  }

  private async startEditor(room: Room, existing?: Scene) {
    if (this.dirty || this.busy || !this.admin) return;
    const generation = this.connectionGeneration;
    this.busy = true;
    this.error = "";
    try {
      const { token } = await this.hass.callWS<{ token: string }>({ type: "halo/edit/begin", room_id: room.id });
      if (!this.isConnected || generation !== this.connectionGeneration) return;
      const scene = existing ? structuredClone(existing) : { id: createId(), name: "", can_turn_on: false, conditions: null, lights: {} };
      for (const id of existing ? [] : room.lights) {
        const actual = this.actualLampState(id);
        if (actual) scene.lights[id] ??= actual;
      }
      this.lightSearches.delete("scene");
      const editor = { token, roomId: room.id, scene, included: new Set(existing ? Object.keys(existing.lights) : room.lights), revision: this.snapshot!.revision, ready: !existing };
      this.editor = editor;
      this.focusView();
      this.heartbeat = setInterval(() => {
        const editor = this.editor;
        if (editor) void this.hass.callWS({ type: "halo/edit/touch", room_id: editor.roomId, token: editor.token }).catch((error) => this.showError(error));
      }, 20_000);
      // Apply the stored scene once before handing control to Home Assistant.
      // No later preview may overwrite changes made in the native dialog.
      this.previewQueue = existing
        ? this.hass.callWS<void>({ type: "halo/edit/preview", room_id: room.id, token, lights: structuredClone(scene.lights) })
        : Promise.resolve();
      await this.previewQueue;
      if (this.editor === editor) editor.ready = true;
    } catch (error) { this.showError(error); }
    finally { this.busy = false; }
  }

  private clearEditorTimers() { clearInterval(this.heartbeat); this.heartbeat = undefined; }
  private updateEditor(callback: (scene: Scene) => void) {
    if (!this.editor) return;
    callback(this.editor.scene);
    this.requestUpdate();
  }

  private async openNativeLight(id: string) {
    const editor = this.editor;
    if (!editor?.ready || !editor.included.has(id) || this.busy || !this.admin || !this.actualLampState(id)) return;
    this.busy = true;
    this.error = "";
    try {
      await this.previewQueue;
      await this.hass.callWS({ type: "halo/edit/touch", room_id: editor.roomId, token: editor.token });
      if (this.editor !== editor || !this.isConnected || !this.actualLampState(id)) return;
      // Public frontend action API; Home Assistant owns and loads its dialog.
      this.dispatchEvent(new CustomEvent("hass-action", {
        bubbles: true, composed: true,
        detail: { config: { entity: id, tap_action: { action: "more-info" } }, action: "tap" },
      }));
    } catch (error) { this.showError(error); }
    finally { this.busy = false; }
  }

  private async endEditor(save: boolean) {
    const editor = this.editor;
    if (!editor || this.busy || (save && (!editor.ready || !this.validateFields()))) return;
    this.busy = true;
    this.error = "";
    try {
      // Cancellation must still release a session whose initial preview failed.
      await this.previewQueue.catch(() => undefined);
      const result = await this.hass.callWS<Snapshot | undefined>({ type: "halo/edit/end", room_id: editor.roomId, token: editor.token, save,
        ...(save ? { scene: { ...editor.scene, lights: Object.fromEntries(Object.entries(editor.scene.lights).filter(([id]) => editor.included.has(id))) }, revision: editor.revision, capture: true, capture_entities: [...editor.included] } : {}) });
      this.clearEditorTimers();
      this.editor = undefined;
      this.roomSection = "control";
      this.receive(result?.config ? result : await this.hass.callWS<Snapshot>({ type: "halo/get" }));
      void this.updateComplete.then(() => {
        const button = [...this.renderRoot.querySelectorAll<HTMLButtonElement>(".edit-scene")].find((element) => element.dataset.sceneId === editor.scene.id);
        (button ?? this.renderRoot.querySelector<HTMLButtonElement>(".create-scene"))?.focus();
      });
    } catch (error) {
      this.showError(error);
      if (typeof error === "object" && error !== null && "code" in error && error.code === "invalid_edit") {
        this.clearEditorTimers(); this.editor = undefined;
        if (this.snapshot) this.receive(this.snapshot);
      }
    } finally { this.busy = false; }
  }

  private renderEditor(editor: Editor) {
    const scene = editor.scene;
    const lights = this.draft?.rooms[editor.roomId]?.lights ?? Object.keys(scene.lights);
    return html`<section class="editor"><div class="editor-toolbar"><h2 class="view-title" tabindex="-1">${this.t("editSceneShort")} <small>${this.areaName(editor.roomId)}</small></h2><span class="badge">${this.t("editing")}</span></div><p class="notice">${this.t("liveBrief")}</p>${this.help("liveHelp", "liveSessionHelp")}
      ${this.textField("sceneName", scene.name, (value) => this.updateEditor((current) => { current.name = value; }), { required: true })}
      <details class="scene-automation"><summary>${this.t("conditions")}<small>${this.t(scene.conditions ? "conditionalScene" : "manualScene")}</small></summary>
        ${this.check("canTurnOn", scene.can_turn_on, (value) => this.updateEditor((current) => { current.can_turn_on = value; }))}${this.help("canTurnOnHelp")}
        ${this.renderCondition(scene.conditions, (condition) => this.updateEditor((current) => { current.conditions = condition; }))}</details>
      <div class="section-heading"><h3>${this.t("lights")}</h3>${this.help("nativeSceneHelp", "nativeControlHelp")}</div><p class="help compact-help">${this.t("sceneIncludedHelp")}</p>
      ${!editor.ready && this.busy ? html`<p role="status">${this.t("previewPending")}</p>` : nothing}
      ${this.lightSearch("scene")}<ul class="scene-lights">${this.filteredLights(lights, "scene").map((id) => this.renderNativeLight(id, editor))}</ul>
      <div class="actions editor-actions"><button ?disabled=${this.busy} @click=${() => this.endEditor(false)}>${this.t("cancel")}</button><button class="primary" ?disabled=${this.busy || !editor.ready} @click=${() => this.endEditor(true)}>${this.t("saveScene")}</button></div>
    </section>`;
  }

  private renderNativeLight(id: string, editor: Editor) {
    const entity = this.liveLamp(id);
    const available = entity?.state === "on" || entity?.state === "off";
    const attributes = entity?.attributes ?? {};
    const brightness = available && entity.state === "on" && typeof attributes.brightness === "number"
      ? `${Math.round(attributes.brightness / 255 * 100)} %` : undefined;
    const effect = available && typeof attributes.effect === "string" ? attributes.effect : undefined;
    return html`<li><label class="check scene-inclusion"><input type="checkbox" aria-label=${`${this.t("sceneInclude")}: ${this.light(id).name}`} .checked=${live(editor.included.has(id))} ?disabled=${this.busy || !editor.ready}
      @change=${(event: Event) => {
        if ((event.target as HTMLInputElement).checked) editor.included.add(id);
        else editor.included.delete(id);
        this.requestUpdate();
      }}><span>${this.t("sceneInclude")}: ${this.light(id).name}</span></label><button class="scene-lamp" ?disabled=${this.busy || !editor.ready || !available || !editor.included.has(id)}
      @click=${() => this.openNativeLight(id)} aria-label=${`${this.t("nativeLightControl")}: ${this.light(id).name}`}>
      <span class="grow"><strong>${this.light(id).name}</strong><small>${id}</small>
        <span>${available ? this.t(entity.state as "on" | "off") : this.t("unavailable")}${brightness ? ` · ${brightness}` : ""}${effect ? ` · ${this.t("effect")}: ${effect}` : ""}</span>
      </span><ha-icon icon="mdi:chevron-right" aria-hidden="true"></ha-icon></button></li>`;
  }

  private renderCondition(condition: Condition | null, change: (condition: Condition | null) => void, nested = false): TemplateResult {
    if (!condition) return html`<p class="help">${this.t("noConditions")}</p><button @click=${() => change(newCondition("state"))}>${this.t("addCondition")}</button>`;
    const update = (patch: Record<string, unknown>) => change({ ...condition, ...patch } as Condition);
    return html`<div class="condition"><div class="row"><label class="grow">${this.t("conditionType")}<select data-selected=${condition.type} .value=${live(condition.type)} @change=${(event: Event) => change(newCondition((event.target as HTMLSelectElement).value as Condition["type"]))}>
      ${(["state", "numeric", "time", "sun", "and", "or", "not"] as const).map((type) => html`<option value=${type} ?selected=${type === condition.type}>${this.t(type)}</option>`)}</select></label>
      ${!nested ? html`<button @click=${() => change(null)}>${this.t("remove")}</button>` : nothing}</div>
      ${condition.type === "and" || condition.type === "or" ? html`${condition.conditions.map((child, index) => html`<div class="row"><div class="grow">${this.renderCondition(child, (value) => {
        const children = [...condition.conditions]; if (value) children[index] = value; else children.splice(index, 1); change({ ...condition, conditions: children });
      }, true)}</div><button aria-label=${this.t("remove")} @click=${() => { const children = [...condition.conditions]; children.splice(index, 1); change({ ...condition, conditions: children }); }}>${this.t("remove")}</button></div>`)}
        <button @click=${() => change({ ...condition, conditions: [...condition.conditions, newCondition("state")] })}>${this.t("addCondition")}</button>` : nothing}
      ${condition.type === "not" ? this.renderCondition(condition.condition, (value) => { if (value) change({ ...condition, condition: value }); }, true) : nothing}
      ${condition.type === "state" || condition.type === "numeric" ? this.entityField("entity", condition.entity_id, (value) => update({ entity_id: value ?? "" }), undefined, true) : nothing}
      ${condition.type === "state" ? this.textField("expectedState", condition.state, (value) => update({ state: value }), { required: true }) : nothing}
      ${condition.type === "numeric" ? this.textField("attribute", condition.attribute ?? "", (value) => { const next = { ...condition }; if (value) next.attribute = value; else delete next.attribute; change(next); }) : nothing}
      ${condition.type === "numeric" || condition.type === "sun" ? html`<div class="field-grid">${(["above", "below"] as const).map((bound) => this.numberField(bound, condition[bound], (value) => { const next = { ...condition }; if (value == null) delete next[bound]; else next[bound] = value; change(next); }))}</div>` : nothing}
      ${condition.type === "time" ? html`<div class="field-grid">${(["after", "before"] as const).map((bound) => this.textField(bound, condition[bound] ?? "", (value) => { const next = { ...condition }; if (value) next[bound] = value; else delete next[bound]; change(next); }, { type: "time", required: true }))}</div>` : nothing}
    </div>`;
  }

  private renderTransitions(values: Transitions, change: (category: Transition, value: number | null | "inherit") => void, roomId?: string) {
    const label: Record<Transition, TranslationKey> = { turn_on: "turn_on", lux_on: "lux_on", natural: "naturalTransition", scene: "sceneTransition", turn_off: "turn_off" };
    return html`${this.help("transitionHelp")}<div class="field-grid transition-grid">${categories.map((category) => {
      const value = values[category];
      const key = `${roomId ?? "global"}:${category}`;
      const mode = value === "inherit" ? "inherit" : value !== null || this.durationModes.has(key) ? "duration" : "none";
      return html`<div class="transition-field"><h4>${this.t(label[category])}</h4>${roomId ? html`<label>${this.t("transitions")}<select data-selected=${mode} .value=${live(mode)} @change=${(event: Event) => {
        const selected = (event.target as HTMLSelectElement).value; if (selected === "duration") this.durationModes.add(key); else this.durationModes.delete(key);
        change(category, selected === "inherit" ? "inherit" : selected === "duration" ? typeof value === "number" ? value : null : null);
      }}><option value="inherit" ?selected=${mode === "inherit"}>${this.t("inherit")}</option><option value="duration" ?selected=${mode === "duration"}>${this.t("duration")}</option><option value="none" ?selected=${mode === "none"}>${this.t("noTransition")}</option></select></label>` : nothing}
      ${!roomId || mode === "duration" ? this.numberField("seconds", typeof value === "number" ? value : null, (number) => change(category, number), { min: 0, max: 86400 }) : nothing}
      ${roomId && mode === "inherit" ? html`<p class="help">${this.t("globalValue")}: ${this.draft!.transitions[category] ?? this.t("noTransition")}</p>` : nothing}</div>`;
    })}</div>`;
  }

  private renderGlobal() {
    const config = this.draft!;
    const sun = this.snapshot!.entities.find((entity) => entity.entity_id === config.sun_entity_id);
    return html`<div class="global-settings"><h2 class="view-title" tabindex="-1">${this.t("global")}</h2><section class="settings-group"><h3>${this.t("sun")}</h3>${this.entityField("sunEntity", config.sun_entity_id, (value) => this.modify((draft) => { draft.sun_entity_id = value; }), "sun")}
      ${config.sun_entity_id && (!sun || typeof sun.attributes.elevation !== "number" || ["unknown", "unavailable"].includes(sun.state)) ? html`<div class="notice">${this.t("noSun")}</div>` : nothing}</section>
      <section class="settings-group"><h3>${this.t("transitions")}</h3>${this.renderTransitions(config.transitions, (category, value) => this.modify((draft) => { draft.transitions[category] = value; }))}</section></div>`;
  }

  private selectProfile(id: string) {
    if (this.busy || this.dirty && !this.validateFields()) return;
    this.selectedProfile = id;
  }

  private addProfile() {
    if (this.dirty && !this.validateFields()) return;
    const id = createId();
    this.modify((draft) => { draft.profiles[id] = newProfile(id, this.t("newProfile")); });
    this.selectedProfile = id;
    void this.updateComplete.then(() => this.renderRoot.querySelector<HTMLInputElement>(".profile input[type=text]")?.focus());
  }

  private renderProfiles() {
    const profiles = Object.values(this.draft!.profiles);
    const selected = this.draft!.profiles[this.selectedProfile] ?? profiles[0];
    return html`<div class="profiles-page"><div class="section-heading"><h2 class="view-title" tabindex="-1">${this.t("profiles")}</h2><button class="primary" @click=${() => this.addProfile()}><ha-icon icon="mdi:plus"></ha-icon>${this.t("newProfile")}</button></div>
      ${this.help("profilesHelp")}
      ${profiles.length ? html`<div class="profiles-workspace"><nav class="profile-list" aria-label=${this.t("profiles")}>${profiles.map((profile) => {
        const count = Object.values(this.draft!.rooms).filter((room) => room.associations.some((association) => association.profile_id === profile.id)).length;
        return html`<button class="profile-link" aria-current=${profile.id === selected?.id ? "page" : nothing} @click=${() => this.selectProfile(profile.id)}><ha-icon icon="mdi:white-balance-sunny"></ha-icon><span><strong>${profile.name}</strong><small>${count} ${this.t("roomsCount")} · ${this.t(profile.linked ? "linkedBrief" : "separateBrief")}</small></span></button>`;
      })}</nav><div class="profile-detail">${selected ? this.renderProfile(selected) : nothing}</div></div>`
        : html`<div class="empty-state"><ha-icon icon="mdi:white-balance-sunny"></ha-icon><h3>${this.t("noProfilesTitle")}</h3><p>${this.t("profilesHelp")}</p></div>`}</div>`;
  }

  private renderProfile(profile: Profile) {
    const inUse = Object.values(this.draft!.rooms).some((room) => room.associations.some((association) => association.profile_id === profile.id));
    return html`<div class="profile">${this.textField("name", profile.name, (value) => this.modify((config) => { config.profiles[profile.id].name = value; }), { required: true })}
      ${this.check("linked", profile.linked, (value) => this.modify((config) => { const current = config.profiles[profile.id]; if (!value && current.linked) current.evening = structuredClone(current.morning); current.linked = value; }))}
      ${(profile.linked ? ["morning"] as const : ["morning", "evening"] as const).map((period) => html`<h3>${this.t(period)}</h3><div class="grid">
        ${(["brightness", "temperature"] as const).map((kind) => {
          const curve = profile[period][kind];
          const interpolation = curveInterpolation(curve);
          const helpId = `curve-help-${profile.id}-${period}-${kind}`;
          const update = (key: Exclude<keyof Curve, "interpolation">, value: number | null) => this.modify((config) => { config.profiles[profile.id][period][kind][key] = value ?? 0; });
          return html`<div class="curve-editor" ?data-invalid=${curve.low_elevation >= curve.high_elevation}><h4>${this.t(kind === "brightness" ? "brightnessCurve" : "temperatureCurve")}</h4>
            <label>${this.t("curveType")}<select aria-describedby=${helpId} data-selected=${interpolation} .value=${live(interpolation)} @change=${(event: Event) => this.modify((config) => {
              config.profiles[profile.id][period][kind].interpolation = (event.target as HTMLSelectElement).value as CurveInterpolation;
            })}><option value="linear" ?selected=${interpolation === "linear"}>${this.t("linearCurve")}</option><option value="ease_in_out" ?selected=${interpolation === "ease_in_out"}>${this.t("easeInOutCurve")}</option></select></label>
            <div class="field-grid">
            ${this.numberField("lowElevation", curve.low_elevation, (value) => update("low_elevation", value), { min: -90, max: 90, required: true })}
            ${this.numberField("highElevation", curve.high_elevation, (value) => update("high_elevation", value), { min: -90, max: 90, required: true })}
            ${this.numberField("lowValue", curve.low, (value) => update("low", value), { min: kind === "brightness" ? 0 : 1000, max: kind === "brightness" ? 100 : 40000, required: true, unit: kind === "brightness" ? "%" : "K" })}
            ${this.numberField("highValue", curve.high, (value) => update("high", value), { min: kind === "brightness" ? 0 : 1000, max: kind === "brightness" ? 100 : 40000, required: true, unit: kind === "brightness" ? "%" : "K" })}
          </div>${curve.low_elevation >= curve.high_elevation ? html`<p class="danger" role="alert">${this.t("badCurve")}</p>` : this.curveGraph(curve, kind === "brightness" ? "%" : "K")}
          <details class="help-details"><summary>${this.t("curveHelp")}</summary><p class="help" id=${helpId}>${this.t(interpolation === "ease_in_out" ? "easeInOutCurveHelp" : "linearCurveHelp")}</p></details></div>`;
        })}</div>`)}
      <button class="danger" ?disabled=${inUse} @click=${() => this.modify((config) => { delete config.profiles[profile.id]; })}>${this.t("remove")}</button>
      ${inUse ? html`<p class="help">${this.t("profileInUse")}</p>` : nothing}</div>`;
  }

  private curveGraph(curve: Curve, unit: string) {
    const margin = Math.min(10, (curve.high_elevation - curve.low_elevation) / 4);
    const xMin = Math.max(-90, curve.low_elevation - margin), xMax = Math.min(90, curve.high_elevation + margin);
    const min = Math.min(curve.low, curve.high), max = Math.max(curve.low, curve.high), span = max - min || 1;
    const xPosition = (elevation: number) => 42 + (elevation - xMin) / (xMax - xMin) * 256;
    const elevations = curveInterpolation(curve) === "ease_in_out"
      ? [xMin, ...Array.from({ length: 33 }, (_, index) => index === 32 ? curve.high_elevation : curve.low_elevation + (curve.high_elevation - curve.low_elevation) * index / 32), xMax]
      : [xMin, curve.low_elevation, curve.high_elevation, xMax];
    const points = elevations.map((elevation) => `${xPosition(elevation)},${155 - (interpolate(curve, elevation) - min) / span * 115}`).join(" ");
    return svg`<svg viewBox="0 0 330 190" role="img" aria-label="${this.t("curve")}: ${this.t(curveInterpolation(curve) === "ease_in_out" ? "easeInOutCurve" : "linearCurve")}, ${curve.low}–${curve.high} ${unit}, ${curve.low_elevation}–${curve.high_elevation}°">
      <path d="M42 20 V155 H305" fill="none" stroke="currentColor" opacity=".4"></path><polyline points=${points} fill="none" stroke="currentColor" stroke-width="3"></polyline>
      ${max !== min ? svg`<text x="2" y="42">${max}${unit}</text>` : nothing}<text x="2" y="155">${min}${unit}</text>
      ${[curve.low_elevation, curve.high_elevation].map((elevation) => svg`<line x1=${xPosition(elevation)} x2=${xPosition(elevation)} y1="155" y2="160" stroke="currentColor"></line><text x=${xPosition(elevation)} y="178" text-anchor="middle">${elevation}°</text>`)}</svg>`;
  }
}

if (!customElements.get("halo-panel")) customElements.define("halo-panel", HaloPanel);
