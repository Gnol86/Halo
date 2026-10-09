import { LitElement, css, html, nothing } from "lit";
import { translate, type TranslationKey } from "./translations";

export interface EntityOption { entity_id: string; name: string; state?: string }

export function matchesEntity(entity: EntityOption, query: string): boolean {
  const normalize = (value: string) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase();
  const text = normalize(`${entity.name} ${entity.entity_id}`);
  return normalize(query).trim().split(/\s+/).every((part) => text.includes(part));
}

/** Search is transient; only choosing a result changes the configured entity. */
export class HaloEntityPicker extends LitElement {
  static properties = {
    entities: { attribute: false }, value: { attribute: false }, label: {}, locale: {}, required: { type: Boolean },
    open: { state: true }, query: { state: true }, active: { state: true },
  };
  static styles = css`
    :host {
      display: block; min-width: 0; color-scheme: inherit;
      font: inherit; font-size: var(--ha-font-size-m,14px);
      --picker-text: var(--primary-text-color,CanvasText);
      --picker-secondary: var(--secondary-text-color,var(--picker-text));
      --picker-surface: var(--ha-card-background,var(--card-background-color,Canvas));
      --picker-line: var(--divider-color,GrayText);
      --picker-accent: var(--primary-color,Highlight);
      --picker-radius: var(--ha-border-radius-md,8px);
    }
    * { box-sizing: border-box; }
    label { display: block; margin: 8px 0 6px; color: var(--input-label-ink-color,var(--picker-text)); }
    input,button { font: inherit; color: inherit; }
    input {
      min-width: 0; width: 100%; min-height: 38px; padding: 7px 10px;
      border: 1px solid var(--input-outlined-idle-border-color,var(--picker-line));
      border-radius: var(--picker-radius); background: var(--input-fill-color,var(--picker-surface));
      color: var(--input-ink-color,var(--picker-text)); caret-color: var(--picker-accent); text-overflow: ellipsis;
    }
    input::placeholder { color: var(--input-label-ink-color,var(--picker-secondary)); opacity: 1; }
    input:hover { border-color: var(--input-outlined-hover-border-color,var(--picker-secondary)); }
    input:invalid { border-color: var(--error-color,var(--picker-text)); }
    :focus-visible { outline: 2px solid var(--picker-accent); outline-offset: 2px; }
    ::selection { background: var(--picker-accent); color: var(--text-primary-color,HighlightText); }
    .field { display: flex; gap: 6px; align-items: center; }
    button {
      flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center;
      min-width: 36px; min-height: 36px; padding: 6px; border: 1px solid transparent;
      border-radius: var(--picker-radius); background: transparent; color: var(--picker-secondary); cursor: pointer;
    }
    button:hover { background: var(--secondary-background-color,var(--picker-surface)); color: var(--picker-text); }
    .results {
      max-height: 260px; overflow: auto; border: 1px solid var(--picker-line); border-radius: var(--picker-radius);
      background: var(--picker-surface); margin: 4px 0 8px;
    }
    [role="option"] { padding: 9px 12px; cursor: pointer; overflow-wrap: anywhere; }
    [role="option"][data-active], [role="option"]:hover {
      background: color-mix(in srgb,var(--picker-accent) 10%,var(--picker-surface));
      outline: 2px solid var(--picker-accent); outline-offset: -2px;
    }
    [aria-selected="true"] { font-weight: var(--ha-font-weight-medium,500); }
    small { display: block; font-size: var(--ha-font-size-s,12px); color: var(--picker-secondary); line-height: 1.5; overflow-wrap: anywhere; }
    .help { color: var(--picker-secondary); margin: 4px 0 8px; line-height: 1.5; }
    .clear-icon { width: 18px; height: 18px; fill: currentColor; }
    @media (pointer:coarse) { input,button,[role="option"] { min-height: 44px; } button { min-width: 44px; } }
  `;
  entities: EntityOption[] = [];
  value: string | null = null;
  label = "";
  locale?: string;
  required = false;
  private open = false;
  private query = "";
  private active = -1;
  private closeOutside = (event: Event) => { if (this.open && !event.composedPath().includes(this)) this.close(); };

  connectedCallback() {
    super.connectedCallback();
    // Outside pointer/focus events also work on touch browsers that blur the
    // input without identifying the tapped option as relatedTarget.
    this.ownerDocument.addEventListener("pointerdown", this.closeOutside, true);
    this.ownerDocument.addEventListener("focusin", this.closeOutside, true);
  }

  disconnectedCallback() {
    this.ownerDocument.removeEventListener("pointerdown", this.closeOutside, true);
    this.ownerDocument.removeEventListener("focusin", this.closeOutside, true);
    super.disconnectedCallback();
  }

  private t(key: TranslationKey) { return translate(key, this.locale); }
  private get selected() { return this.entities.find((entity) => entity.entity_id === this.value); }
  private get results() { return this.entities.filter((entity) => matchesEntity(entity, this.query)).slice(0, 100); }
  private get selectionText() { return this.value ? `${this.selected?.name ?? this.value} (${this.value})` : ""; }

  reportValidity() {
    const input = this.renderRoot.querySelector<HTMLInputElement>("input")!;
    const valid = !this.required || Boolean(this.value);
    input.setCustomValidity(valid ? "" : this.t("chooseEntity"));
    if (!valid) { this.open = true; input.focus(); }
    return input.reportValidity();
  }

  private startSearch() { if (!this.open) { this.open = true; this.query = ""; this.active = -1; } }
  private close() { this.open = false; this.query = ""; this.active = -1; }
  private choose(value: string | null) {
    this.value = value;
    this.renderRoot.querySelector<HTMLInputElement>("input")?.focus();
    this.close();
    this.renderRoot.querySelector<HTMLInputElement>("input")?.setCustomValidity("");
    this.dispatchEvent(new CustomEvent("entity-changed", { detail: { value }, bubbles: true, composed: true }));
  }

  private onKey(event: KeyboardEvent) {
    if (event.key === "Escape") { event.preventDefault(); this.close(); return; }
    if (event.key === "Tab") { this.close(); return; }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      this.startSearch();
      const count = this.results.length;
      this.active = count ? (this.active + (event.key === "ArrowDown" ? 1 : this.active < 0 ? 0 : -1) + count) % count : -1;
      void this.updateComplete.then(() => this.renderRoot.querySelector<HTMLElement>("[data-active]")?.scrollIntoView?.({ block: "nearest" }));
    } else if (event.key === "Enter" && this.open) {
      event.preventDefault();
      if (this.active >= 0 && this.results[this.active]) this.choose(this.results[this.active].entity_id);
    }
  }

  protected render() {
    const results = this.open ? this.results : [];
    return html`<label for="entity-input">${this.label}</label>
      <div class="field"><input id="entity-input" role="combobox" aria-autocomplete="list" aria-expanded=${String(this.open)}
        aria-controls="entity-results" aria-required=${String(this.required)} aria-describedby="entity-help"
        aria-activedescendant=${this.open && this.active >= 0 && results[this.active] ? `entity-option-${this.active}` : nothing}
        autocomplete="off" spellcheck="false" placeholder=${this.t("searchEntities")} .value=${this.open ? this.query : this.selectionText}
        @focus=${this.startSearch} @click=${this.startSearch} @keydown=${this.onKey}
        @input=${(event: Event) => { this.query = (event.target as HTMLInputElement).value; this.open = true; this.active = -1; }}>
        ${this.value ? html`<button type="button" aria-label=${`${this.t("clearEntity")}: ${this.label}`} @click=${() => this.choose(null)}><svg class="clear-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z"></path></svg></button>` : nothing}</div>
      <small id="entity-help" class="help">${this.value ? `${this.t("selected")}: ${this.selected?.name ?? this.value} · ${this.value}${!this.selected || ["unknown", "unavailable"].includes(this.selected.state ?? "") ? ` · ${this.t("unavailable")}` : ""}` : this.t("noEntity")}</small>
      ${this.open ? html`<div class="results" id="entity-results" role="listbox" aria-label=${this.label}>
        ${results.map((entity, index) => html`<div role="option" tabindex="-1" id=${`entity-option-${index}`} aria-selected=${String(entity.entity_id === this.value)}
          ?data-active=${index === this.active} @mousedown=${(event: MouseEvent) => event.preventDefault()} @click=${() => this.choose(entity.entity_id)}>
          ${entity.name}<small>${entity.entity_id}${["unknown", "unavailable"].includes(entity.state ?? "") ? ` · ${this.t("unavailable")}` : ""}</small></div>`)}
      </div><div class="help" role="status">${results.length === 0 ? this.t("noResults") : results.length === 100 ? this.t("refineSearch") : `${results.length} ${this.t("results")}`}</div>` : nothing}`;
  }
}

customElements.define("halo-entity-picker", HaloEntityPicker);
