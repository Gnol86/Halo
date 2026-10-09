import { LitElement, html, nothing, svg, type PropertyValues, type TemplateResult } from "lit";
import { live } from "lit/directives/live.js";
import { categories, createId, colorMode, dimmable, interpolate, moveItem, newCondition, newProfile, newRoom, optionalNumber } from "./model";
import { en, language, translate, type TranslationKey } from "./translations";
import { styles } from "./styles";
import { HaloEntityPicker, matchesEntity } from "./entity-picker";
import type { Condition, Config, Curve, CurveInterpolation, Hass, LampState, Light, Profile, Room, Scene, Snapshot, Transition, Transitions } from "./types";

type Editor = { roomId: string; token: string; scene: Scene; revision: number };
type FieldOptions = { min?: number; max?: number; step?: number | "any"; required?: boolean; type?: string; unit?: string };

export class HaloPanel extends LitElement {
  static properties = { hass: { attribute: false }, narrow: { type: Boolean }, snapshot: { state: true },
    draft: { state: true }, page: { state: true }, dirty: { state: true }, busy: { state: true },
    error: { state: true }, notice: { state: true }, editor: { state: true }, search: { state: true } };
  static styles = styles;
  declare hass: Hass;
  narrow = false;
  private snapshot?: Snapshot;
  private draft?: Config;
  private revision = 0;
  private page = "rooms";
  private dirty = false;
  private busy = false;
  private error = "";
  private notice = "";
  private search = "";
  private lightSearches = new Map<string, string>();
  private editor?: Editor;
  private unsubscribe?: () => void;
  private connection?: Hass["connection"];
  private connectionGeneration = 0;
  private heartbeat?: ReturnType<typeof setInterval>;
  private previewTimer?: ReturnType<typeof setTimeout>;
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
  }

  private async connect() {
    const generation = ++this.connectionGeneration;
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
      if (!field.disabled && !field.reportValidity()) { this.error = this.t("validation"); return false; }
    }
    for (const picker of this.renderRoot.querySelectorAll<HaloEntityPicker>("halo-entity-picker")) {
      if (!picker.reportValidity()) { this.error = this.t("validation"); return false; }
    }
    return true;
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

  private navigate(page: string) { this.page = page; this.search = ""; this.lightSearches.clear(); this.removeConfirmation = undefined; }
  private areaName(id: string) { return this.snapshot?.areas.find((area) => area.id === id)?.name ?? id; }
  private light(id: string): Light {
    return this.snapshot?.lights.find((light) => light.entity_id === id) ?? {
      entity_id: id, name: id, area_id: null, available: false, supported_color_modes: [], supported_features: 0,
    };
  }

  private textField(label: TranslationKey, value: string, change: (value: string) => void, options: FieldOptions = {}) {
    return html`<label>${this.t(label)}<input type=${options.type ?? "text"} .value=${value} ?required=${options.required ?? false}
      @change=${(event: Event) => change((event.target as HTMLInputElement).value)}></label>`;
  }

  private numberField(label: TranslationKey, value: number | null | undefined, change: (value: number | null) => void, options: FieldOptions = {}) {
    return html`<label>${this.t(label)}${options.unit ? ` (${options.unit})` : ""}<input type="number" .value=${value == null ? "" : String(value)}
      min=${options.min ?? nothing} max=${options.max ?? nothing} step=${options.step ?? "any"} ?required=${options.required ?? false}
      @change=${(event: Event) => change(optionalNumber((event.target as HTMLInputElement).value))}></label>`;
  }

  private check(label: TranslationKey, checked: boolean, change: (value: boolean) => void, disabled = false) {
    return html`<label class="check"><input type="checkbox" .checked=${live(checked)} ?disabled=${disabled}
      @change=${(event: Event) => change((event.target as HTMLInputElement).checked)}>${this.t(label)}</label>`;
  }

  private entityField(label: TranslationKey, value: string | null, change: (value: string | null) => void, domain?: string, required = false) {
    const entities = (this.snapshot?.entities ?? []).filter((entity) => !domain || entity.entity_id.startsWith(`${domain}.`));
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

  protected render() {
    return html`<header>
      <ha-icon icon="mdi:spa"></ha-icon><h1>Halo</h1><small>${this.t("title")}</small></header>
      <div class="content"><main lang=${language(this.locale)}>
        ${this.error ? html`<div class="notice error" role="alert">${this.error} <button ?disabled=${this.editing} @click=${() => this.connect()}>${this.t("retry")}</button></div>` : nothing}
        ${this.notice ? html`<div class="notice" role="status">${this.notice}</div>` : nothing}
        ${!this.snapshot || !this.draft ? html`<p role="status">${this.t("loading")}</p><button @click=${() => this.connect()}>${this.t("retry")}</button>` : html`
          <nav aria-label="Halo"><button aria-current=${this.page === "rooms" ? "page" : nothing} ?disabled=${this.editing} @click=${() => this.navigate("rooms")}>${this.t("rooms")}</button>
            ${this.admin ? html`<button aria-current=${this.page === "global" ? "page" : nothing} ?disabled=${this.editing} @click=${() => this.navigate("global")}>${this.t("global")}</button>` : nothing}
          </nav>
          ${!this.admin ? html`<p class="help">${this.t("adminOnly")}</p>` : nothing}
          ${this.editor ? this.renderEditor(this.editor) : this.page === "global" && this.admin ? this.renderGlobal() : this.page === "rooms" ? this.renderRooms() : this.renderRoom()}
        `}
      </main></div>
      ${this.dirty ? html`<div class="savebar" role="status"><span class="grow">${this.hasConflict ? this.t("conflict") : this.t("unsaved")}</span>
        <button ?disabled=${this.busy} @click=${this.discard}>${this.t("discard")}</button><button class="primary" ?disabled=${this.busy || this.hasConflict} @click=${this.save}>${this.t("save")}</button></div>` : nothing}`;
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
    return html`<div class="actions"><button ?disabled=${disabled} @click=${() => this.command(room.id, "turn_on")}>${this.t("turnOn")}</button>
      <button ?disabled=${disabled} @click=${() => this.command(room.id, "turn_off")}>${this.t("turnOff")}</button>
      <button ?disabled=${disabled || this.dirty} @click=${() => this.command(room.id, "resume")}>${this.t("resume")}</button></div>
      <div class="row">${this.check("automation", actual.automation_enabled, (enabled) => { void this.command(room.id, "automation", { enabled }); }, disabled || this.dirty)}
        ${this.check("natural", actual.natural_enabled, (enabled) => { void this.command(room.id, "natural", { enabled }); }, disabled || this.dirty)}</div>
      ${this.dirty ? html`<p class="help">${this.t("saveFirst")}</p>` : nothing}`;
  }

  private renderRooms() {
    const areas = [...this.snapshot!.areas];
    for (const roomId of Object.keys(this.draft!.rooms)) if (!areas.some((area) => area.id === roomId)) areas.push({ id: roomId, name: roomId });
    return html`<h2>${this.t("rooms")}</h2>${areas.length === 0 ? html`<p class="empty">${this.t("noRooms")}</p>` : nothing}
      <div class="grid">${areas.map((area) => {
        const room = this.draft!.rooms[area.id];
        return html`<article class="card"><h2>${area.name}</h2><p class="help">${this.t(room ? "configured" : "unconfigured")}</p>
          ${room ? html`${this.status(area.id)}${this.controls(room)}<button @click=${() => this.navigate(area.id)}>${this.t("lights")} · ${room.lights.length}</button>`
            : this.admin ? html`<button @click=${() => { this.modify((config) => { config.rooms[area.id] = newRoom(area.id); }); this.navigate(area.id); }}>${this.t("configure")}</button>` : nothing}
        </article>`;
      })}</div>`;
  }

  private renderRoom() {
    const room = this.room;
    if (!room) return html`<p>${this.t("not_found")}</p><button @click=${() => this.navigate("rooms")}>${this.t("back")}</button>`;
    return html`<div class="row"><h2 class="grow">${this.areaName(room.id)}</h2><button @click=${() => this.navigate("rooms")}>${this.t("back")}</button></div>
      <section>${this.status(room.id)}${this.controls(room)}</section>
      ${this.admin ? html`${this.renderLightSelection(room)}${this.renderAutomation(room)}${this.renderAssociations(room)}
        <details><summary>${this.t("base")}</summary><p class="help">${this.t("baseHelp")}</p>
          ${this.lightSearch("base")}
          ${this.filteredLights(room.lights, "base").map((id) => this.lampEditor(id, room.base[id], (value) => this.modifyRoom((current) => { if (value) current.base[id] = value; else delete current.base[id]; }), true))}
        </details>` : nothing}
      ${this.renderScenes(room)}
      ${this.admin ? html`<details><summary>${this.t("transitions")}</summary>${this.renderTransitions(room.transitions, (category, value) => this.modifyRoom((current) => { current.transitions[category] = value; }), room.id)}</details>
        <details><summary>${this.t("removeRoom")}</summary><p class="help">${this.t("removeRoomHelp")}</p>
          <button class="danger" @click=${() => { if (this.removeConfirmation === room.id) { this.modify((config) => { delete config.rooms[room.id]; }); this.navigate("rooms"); }
            else { this.removeConfirmation = room.id; this.requestUpdate(); } }}>${this.t(this.removeConfirmation === room.id ? "confirmRemove" : "removeRoom")}</button></details>` : nothing}`;
  }

  private renderLightSelection(room: Room) {
    const assigned = new Set(Object.values(this.draft!.rooms).filter((other) => other.id !== room.id).flatMap((other) => other.lights));
    const lights = [...this.snapshot!.lights];
    for (const id of room.lights) if (!lights.some((light) => light.entity_id === id)) lights.push(this.light(id));
    const filtered = lights.filter((light) => matchesEntity(light, this.search));
    return html`<details open><summary>${this.t("lights")} · ${room.lights.length}</summary><p class="help">${this.t("lightsHelp")}</p>
      <label>${this.t("search")}<input type="search" .value=${this.search} @input=${(event: Event) => { this.search = (event.target as HTMLInputElement).value; }}></label>
      <div class="light-list">${[true, false].map((own) => html`<h3>${this.t(own ? "ownArea" : "otherAreas")}</h3>
        ${filtered.filter((light) => (light.area_id === room.id) === own).map((light) => html`<div class="light-option"><label class="check">
          <input type="checkbox" .checked=${live(room.lights.includes(light.entity_id))} ?disabled=${assigned.has(light.entity_id)} @change=${(event: Event) => this.modifyRoom((current) => {
            if ((event.target as HTMLInputElement).checked) current.lights.push(light.entity_id);
            else { current.lights = current.lights.filter((id) => id !== light.entity_id); delete current.base[light.entity_id];
              for (const scene of current.scenes) delete scene.lights[light.entity_id];
              for (const association of current.associations) association.lights = association.lights.filter((id) => id !== light.entity_id); }
          })}><span>${light.name}<small>${light.entity_id}${assigned.has(light.entity_id) ? ` · ${this.t("assigned")}` : ""}${!light.available ? ` · ${this.t("unavailable")}` : ""}</small>${this.groupDetails(light)}</span></label></div>`)}`)}${filtered.length === 0 ? html`<p role="status">${this.t("noResults")}</p>` : nothing}</div></details>`;
  }

  private renderAutomation(room: Room) {
    const attributes = room.lux_entity_id ? (this.hass.states?.[room.lux_entity_id] ?? this.snapshot?.entities.find((entity) => entity.entity_id === room.lux_entity_id))?.attributes : undefined;
    const unit = typeof attributes?.unit_of_measurement === "string" ? attributes.unit_of_measurement.trim() : "";
    const suffix = unit ? ` ${unit}` : "";
    return html`<details><summary>${this.t("automation")}</summary><h3>${this.t("presence")}</h3><div class="field-grid">
      ${this.entityField("presenceEntity", room.presence_entity_id, (value) => this.modifyRoom((current) => { current.presence_entity_id = value; }))}
      ${this.textField("presentStates", room.presence_states.join(", "), (value) => this.modifyRoom((current) => { current.presence_states = value.split(",").map((state) => state.trim()).filter(Boolean); }), { required: Boolean(room.presence_entity_id) })}
      ${this.numberField("absenceDelay", room.absence_delay, (value) => this.modifyRoom((current) => { current.absence_delay = value ?? 0; }), { min: 0, required: true })}</div>
      <h3>${this.t("lux")}</h3>${this.entityField("luxEntity", room.lux_entity_id, (value) => this.modifyRoom((current) => { current.lux_entity_id = value; }), "sensor")}
      ${room.lux_entity_id ? html`<div class="field-grid">${this.numberField("luxThreshold", room.lux_threshold, (value) => this.modifyRoom((current) => { current.lux_threshold = value; }), { min: 0, required: true, unit })}
        ${this.numberField("hysteresis", room.lux_hysteresis, (value) => this.modifyRoom((current) => { current.lux_hysteresis = value ?? 0; }), { min: 0, required: true, unit })}</div>
        <p>${this.t("effectiveLow")}: ${room.lux_threshold ?? "—"}${suffix} · ${this.t("effectiveHigh")}: ${room.lux_threshold == null ? "—" : room.lux_threshold + room.lux_hysteresis}${suffix}</p>
        ${!unit ? html`<p class="help">${this.t("unknownUnit")}</p>` : nothing}
        ${this.check("luxOff", room.lux_off, (value) => this.modifyRoom((current) => { current.lux_off = value; }))}
        ${room.lux_off ? this.numberField("luxDelay", room.lux_off_delay, (value) => this.modifyRoom((current) => { current.lux_off_delay = value ?? 30; }), { min: 0, required: true }) : nothing}
        <p class="help">${this.t("luxHelp")}</p>` : nothing}
      <h3>${this.t("manual")}</h3>${this.numberField("pauseDuration", room.manual_pause / 60, (value) => this.modifyRoom((current) => { current.manual_pause = (value ?? 120) * 60; }), { min: 0, required: true })}
      ${this.check("allowOff", room.allow_off_during_pause, (value) => this.modifyRoom((current) => { current.allow_off_during_pause = value; }))}<p class="help">${this.t("pauseHelp")}</p></details>`;
  }

  private renderAssociations(room: Room) {
    const profiles = Object.values(this.draft!.profiles);
    return html`<details><summary>${this.t("associations")}</summary><p class="help">${this.t("associationHelp")}</p>
      ${room.associations.map((association, index) => html`<div class="association"><div class="row"><label class="grow">${this.t("profile")}<select required data-selected=${association.profile_id} .value=${live(association.profile_id)} @change=${(event: Event) => this.modifyRoom((current) => { current.associations[index].profile_id = (event.target as HTMLSelectElement).value; })}>
        <option value="" ?selected=${!association.profile_id}>${this.t("noProfile")}</option>${profiles.map((profile) => html`<option value=${profile.id} ?selected=${profile.id === association.profile_id}>${profile.name}</option>`)}</select></label>
        <button @click=${() => this.modifyRoom((current) => { current.associations.splice(index, 1); })}>${this.t("remove")}</button></div>
        ${this.numberField("offset", association.brightness_offset, (value) => this.modifyRoom((current) => { current.associations[index].brightness_offset = value ?? 0; }), { min: -100, max: 1000, required: true })}<p class="help">${this.t("offsetHelp")}</p>
        ${this.lightSearch(`association-${index}`)}
        ${this.filteredLights(room.lights, `association-${index}`).filter((id) => dimmable(this.light(id))).map((id) => {
          const used = room.associations.some((other, otherIndex) => otherIndex !== index && other.lights.includes(id));
          return html`<label class="check"><input type="checkbox" .checked=${live(association.lights.includes(id))} ?disabled=${used} @change=${(event: Event) => this.modifyRoom((current) => {
            const target = current.associations[index]; target.lights = (event.target as HTMLInputElement).checked ? [...target.lights, id] : target.lights.filter((light) => light !== id);
          })}><span>${this.light(id).name}<small>${id}</small>${this.groupDetails(this.light(id))}</span></label>`;
        })}</div>`)}
      ${profiles.length ? html`<button @click=${() => this.modifyRoom((current) => { current.associations.push({ profile_id: profiles[0].id, lights: [], brightness_offset: 0 }); })}>${this.t("addAssociation")}</button>` : html`<p>${this.t("noProfiles")}</p>`}</details>`;
  }

  private lampEditor(id: string, value: LampState | undefined, change: (value?: LampState) => void, optional: boolean) {
    const light = this.light(id);
    const selectedMode = value?.color_temp_kelvin != null ? "temperature" : value?.rgb_color ? "rgb_color" : value?.hs_color ? "hs_color" : value?.xy_color ? "xy_color" : "";
    const mode = colorMode(light);
    const update = (patch: Partial<LampState>) => change({ state: "on", ...value, ...patch });
    const modes: [string, TranslationKey][] = [["", "keepColor"]];
    if (light.supported_color_modes.includes("color_temp")) modes.push(["temperature", "nativeWhite"]);
    if (mode) modes.push([mode, mode === "rgb_color" ? "rgb" : mode === "hs_color" ? "hs" : "xy"]);
    return html`<div class="lamp"><h4>${light.name} ${!light.available ? html`<span class="badge">${this.t("unavailable")}</span>` : nothing}</h4><small>${id}</small>${this.groupDetails(light)}
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
        </div>` : nothing}` : html`<p class="help">${this.t("defaultSetting")}</p>`}</div>`;
  }

  private renderScenes(room: Room) {
    return html`<section><h2>${this.t("scenes")}</h2><p class="help">${this.t("scenesHelp")}</p>
      ${room.scenes.length === 0 ? html`<p class="empty">${this.t("noScenes")}</p>` : nothing}
      ${room.scenes.map((scene, index) => html`<div class="scene-row" draggable=${this.admin ? "true" : "false"}
        @dragstart=${(event: DragEvent) => { this.dragIndex = index; event.dataTransfer?.setData("text/plain", scene.id); }}
        @dragover=${(event: DragEvent) => { if (this.admin) event.preventDefault(); }}
        @drop=${(event: DragEvent) => { event.preventDefault(); if (this.admin && this.dragIndex != null) this.modifyRoom((current) => { current.scenes = moveItem(current.scenes, this.dragIndex!, index); }); this.dragIndex = undefined; }}>
        <span class="badge" aria-label=${this.t("priority")}>${index + 1}</span><strong class="grow">${scene.name}</strong><div class="actions">
          <button ?disabled=${this.busy} @click=${() => this.command(room.id, "scene", { scene_id: scene.id })}>${this.t("run")}</button>
          ${this.admin ? html`<button ?disabled=${this.busy || this.dirty} @click=${() => this.startEditor(room, scene)}>${this.t("editScene")}</button>
            <button aria-label=${`${this.t("up")} ${scene.name}`} ?disabled=${index === 0} @click=${() => this.modifyRoom((current) => { current.scenes = moveItem(current.scenes, index, index - 1); })}>↑</button>
            <button aria-label=${`${this.t("down")} ${scene.name}`} ?disabled=${index === room.scenes.length - 1} @click=${() => this.modifyRoom((current) => { current.scenes = moveItem(current.scenes, index, index + 1); })}>↓</button>
            <button aria-label=${`${this.t("remove")} ${scene.name}`} @click=${() => this.modifyRoom((current) => { current.scenes.splice(index, 1); })}>${this.t("remove")}</button>` : nothing}
        </div></div>`)}
      ${this.admin ? html`<button ?disabled=${this.busy || this.dirty || room.lights.length === 0} @click=${() => this.startEditor(room)}>${this.t("createScene")}</button>
        ${this.dirty ? html`<p class="help">${this.t("editFirstSave")}</p>` : nothing}` : nothing}</section>`;
  }

  private actualLampState(id: string): LampState {
    const entity = this.hass.states?.[id] ?? this.snapshot?.entities.find((item) => item.entity_id === id);
    const attributes = entity?.attributes ?? {};
    const state: LampState = { state: entity?.state === "on" ? "on" : "off" };
    const light = this.light(id);
    if (typeof attributes.brightness === "number" && dimmable(light)) state.brightness_pct = Math.max(1, Math.round(attributes.brightness / 255 * 100));
    if (attributes.color_mode === "color_temp" && typeof attributes.color_temp_kelvin === "number") state.color_temp_kelvin = attributes.color_temp_kelvin;
    else { const mode = colorMode(light); if (mode && Array.isArray(attributes[mode])) state[mode] = [...attributes[mode] as number[]]; }
    return state;
  }

  private async startEditor(room: Room, existing?: Scene) {
    if (this.dirty || this.busy || !this.admin) return;
    this.busy = true;
    this.error = "";
    try {
      const { token } = await this.hass.callWS<{ token: string }>({ type: "halo/edit/begin", room_id: room.id });
      const scene = existing ? structuredClone(existing) : { id: createId(), name: "", can_turn_on: false, conditions: null, lights: {} };
      for (const id of room.lights) scene.lights[id] ??= this.actualLampState(id);
      this.lightSearches.delete("scene");
      this.editor = { token, roomId: room.id, scene, revision: this.snapshot!.revision };
      this.heartbeat = setInterval(() => {
        const editor = this.editor;
        if (editor) void this.hass.callWS({ type: "halo/edit/touch", room_id: editor.roomId, token: editor.token }).catch((error) => this.showError(error));
      }, 20_000);
      if (existing) this.queuePreview();
    } catch (error) { this.showError(error); }
    finally { this.busy = false; }
  }

  private clearEditorTimers() { clearInterval(this.heartbeat); clearTimeout(this.previewTimer); this.heartbeat = undefined; this.previewTimer = undefined; }
  private updateEditor(callback: (scene: Scene) => void, preview = false) {
    if (!this.editor) return;
    callback(this.editor.scene);
    this.requestUpdate();
    if (preview) this.queuePreview();
  }

  private queuePreview() {
    clearTimeout(this.previewTimer);
    this.previewTimer = setTimeout(() => { this.previewTimer = undefined; this.flushPreview(); }, 120);
  }

  private flushPreview() {
    const editor = this.editor;
    if (!editor) return;
    const lights = structuredClone(editor.scene.lights);
    this.previewQueue = this.previewQueue.then(async () => {
      if (this.editor?.token !== editor.token) return;
      await this.hass.callWS({ type: "halo/edit/preview", room_id: editor.roomId, token: editor.token, lights });
    }).catch((error) => this.showError(error));
  }

  private async endEditor(save: boolean) {
    const editor = this.editor;
    if (!editor || this.busy || (save && !this.validateFields())) return;
    this.busy = true;
    this.error = "";
    clearTimeout(this.previewTimer);
    if (save && this.previewTimer) this.flushPreview();
    this.previewTimer = undefined;
    try {
      await this.previewQueue;
      const result = await this.hass.callWS<Snapshot | undefined>({ type: "halo/edit/end", room_id: editor.roomId, token: editor.token, save,
        ...(save ? { scene: editor.scene, revision: editor.revision } : {}) });
      this.clearEditorTimers();
      this.editor = undefined;
      this.receive(result?.config ? result : await this.hass.callWS<Snapshot>({ type: "halo/get" }));
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
    return html`<section class="editor"><h2>${this.areaName(editor.roomId)} · ${this.t("preview")}</h2><div class="notice">${this.t("liveHelp")}</div>
      ${this.textField("sceneName", scene.name, (value) => this.updateEditor((current) => { current.name = value; }), { required: true })}
      ${this.check("canTurnOn", scene.can_turn_on, (value) => this.updateEditor((current) => { current.can_turn_on = value; }))}<p class="help">${this.t("canTurnOnHelp")}</p>
      <h3>${this.t("conditions")}</h3>${this.renderCondition(scene.conditions, (condition) => this.updateEditor((current) => { current.conditions = condition; }))}
      <h3>${this.t("lights")}</h3>${this.lightSearch("scene")}${this.filteredLights(Object.keys(scene.lights), "scene").map((id) => this.lampEditor(id, scene.lights[id], (value) => this.updateEditor((current) => { if (value) current.lights[id] = value; }, true), false))}
      <div class="actions"><button ?disabled=${this.busy} @click=${() => this.endEditor(false)}>${this.t("cancel")}</button><button class="primary" ?disabled=${this.busy} @click=${() => this.endEditor(true)}>${this.t("saveScene")}</button></div>
    </section>`;
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
    return html`<p class="help">${this.t("transitionHelp")}</p><div class="field-grid transition-grid">${categories.map((category) => {
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
    return html`<h2>${this.t("global")}</h2><section>${this.entityField("sunEntity", config.sun_entity_id, (value) => this.modify((draft) => { draft.sun_entity_id = value; }), "sun")}
      ${config.sun_entity_id && (!sun || typeof sun.attributes.elevation !== "number" || ["unknown", "unavailable"].includes(sun.state)) ? html`<div class="notice">${this.t("noSun")}</div>` : nothing}</section>
      <section><h2>${this.t("profiles")}</h2><p class="help">${this.t("profilesHelp")}</p>${Object.values(config.profiles).map((profile) => this.renderProfile(profile))}
        <button @click=${() => this.modify((draft) => { const id = createId(); draft.profiles[id] = newProfile(id, this.t("newProfile")); })}>${this.t("newProfile")}</button></section>
      <section><h2>${this.t("transitions")}</h2>${this.renderTransitions(config.transitions, (category, value) => this.modify((draft) => { draft.transitions[category] = value; }))}</section>`;
  }

  private renderProfile(profile: Profile) {
    const inUse = Object.values(this.draft!.rooms).some((room) => room.associations.some((association) => association.profile_id === profile.id));
    return html`<div class="profile">${this.textField("name", profile.name, (value) => this.modify((config) => { config.profiles[profile.id].name = value; }), { required: true })}
      ${this.check("linked", profile.linked, (value) => this.modify((config) => { const current = config.profiles[profile.id]; if (!value && current.linked) current.evening = structuredClone(current.morning); current.linked = value; }))}
      ${(profile.linked ? ["morning"] as const : ["morning", "evening"] as const).map((period) => html`<h3>${this.t(period)}</h3><div class="grid">
        ${(["brightness", "temperature"] as const).map((kind) => {
          const curve = profile[period][kind];
          const interpolation = curve.interpolation ?? "linear";
          const helpId = `curve-help-${profile.id}-${period}-${kind}`;
          const update = (key: Exclude<keyof Curve, "interpolation">, value: number | null) => this.modify((config) => { config.profiles[profile.id][period][kind][key] = value ?? 0; });
          return html`<div><h4>${this.t(kind === "brightness" ? "brightnessCurve" : "temperatureCurve")}</h4>
            <label>${this.t("curveType")}<select aria-describedby=${helpId} data-selected=${interpolation} .value=${live(interpolation)} @change=${(event: Event) => this.modify((config) => {
              config.profiles[profile.id][period][kind].interpolation = (event.target as HTMLSelectElement).value as CurveInterpolation;
            })}><option value="linear" ?selected=${interpolation === "linear"}>${this.t("linearCurve")}</option><option value="ease_in" ?selected=${interpolation === "ease_in"}>${this.t("easeInCurve")}</option></select></label>
            <div class="field-grid">
            ${this.numberField("lowElevation", curve.low_elevation, (value) => update("low_elevation", value), { min: -90, max: 90, required: true })}
            ${this.numberField("highElevation", curve.high_elevation, (value) => update("high_elevation", value), { min: -90, max: 90, required: true })}
            ${this.numberField("lowValue", curve.low, (value) => update("low", value), { min: kind === "brightness" ? 0 : 1000, max: kind === "brightness" ? 100 : 40000, required: true, unit: kind === "brightness" ? "%" : "K" })}
            ${this.numberField("highValue", curve.high, (value) => update("high", value), { min: kind === "brightness" ? 0 : 1000, max: kind === "brightness" ? 100 : 40000, required: true, unit: kind === "brightness" ? "%" : "K" })}
          </div>${curve.low_elevation >= curve.high_elevation ? html`<p class="danger" role="alert">${this.t("badCurve")}</p>` : this.curveGraph(curve, kind === "brightness" ? "%" : "K")}
          <p class="help" id=${helpId}>${this.t(interpolation === "ease_in" ? "easeInCurveHelp" : "linearCurveHelp")}</p></div>`;
        })}</div>`)}
      <button class="danger" ?disabled=${inUse} @click=${() => this.modify((config) => { delete config.profiles[profile.id]; })}>${this.t("remove")}</button>
      ${inUse ? html`<p class="help">${this.t("profileInUse")}</p>` : nothing}</div>`;
  }

  private curveGraph(curve: Curve, unit: string) {
    const margin = Math.min(10, (curve.high_elevation - curve.low_elevation) / 4);
    const xMin = Math.max(-90, curve.low_elevation - margin), xMax = Math.min(90, curve.high_elevation + margin);
    const min = Math.min(curve.low, curve.high), max = Math.max(curve.low, curve.high), span = max - min || 1;
    const xPosition = (elevation: number) => 42 + (elevation - xMin) / (xMax - xMin) * 256;
    const elevations = curve.interpolation === "ease_in"
      ? [xMin, ...Array.from({ length: 33 }, (_, index) => index === 32 ? curve.high_elevation : curve.low_elevation + (curve.high_elevation - curve.low_elevation) * index / 32), xMax]
      : [xMin, curve.low_elevation, curve.high_elevation, xMax];
    const points = elevations.map((elevation) => `${xPosition(elevation)},${155 - (interpolate(curve, elevation) - min) / span * 115}`).join(" ");
    return svg`<svg viewBox="0 0 330 190" role="img" aria-label="${this.t("curve")}: ${this.t(curve.interpolation === "ease_in" ? "easeInCurve" : "linearCurve")}, ${curve.low}–${curve.high} ${unit}, ${curve.low_elevation}–${curve.high_elevation}°">
      <path d="M42 20 V155 H305" fill="none" stroke="currentColor" opacity=".4"></path><polyline points=${points} fill="none" stroke="currentColor" stroke-width="3"></polyline>
      ${max !== min ? svg`<text x="2" y="42">${max}${unit}</text>` : nothing}<text x="2" y="155">${min}${unit}</text>
      ${[curve.low_elevation, curve.high_elevation].map((elevation) => svg`<line x1=${xPosition(elevation)} x2=${xPosition(elevation)} y1="155" y2="160" stroke="currentColor"></line><text x=${xPosition(elevation)} y="178" text-anchor="middle">${elevation}°</text>`)}</svg>`;
  }
}

if (!customElements.get("halo-panel")) customElements.define("halo-panel", HaloPanel);
