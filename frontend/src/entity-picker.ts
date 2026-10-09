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
    :host { display:block; min-width:0; font-size:14px; }
    * { box-sizing:border-box; }
    label { display:block; margin:10px 0 6px; }
    input,button { font:inherit; color:inherit; }
    input { width:100%; min-height:42px; padding:9px; border:1px solid var(--divider-color,#aaa); border-radius:6px; background:var(--input-fill-color,var(--card-background-color,#fff)); }
    :focus-visible { outline:3px solid var(--primary-color,#03a9f4); outline-offset:2px; }
    .field { display:flex; gap:6px; align-items:center; }
    button { min-height:42px; border:1px solid var(--divider-color,#bbb); border-radius:6px; background:var(--card-background-color,#fff); cursor:pointer; }
    .results { max-height:260px; overflow:auto; border:1px solid var(--divider-color,#aaa); border-radius:6px; background:var(--card-background-color,#fff); margin:4px 0 10px; }
    [role="option"] { padding:10px; cursor:pointer; overflow-wrap:anywhere; }
    [role="option"][data-active], [role="option"]:hover { background:var(--secondary-background-color,#eee); outline:2px solid var(--primary-color,#03a9f4); outline-offset:-2px; }
    [aria-selected="true"] { font-weight:600; }
    small { display:block; color:var(--secondary-text-color,#666); line-height:1.5; }
    .help { color:var(--secondary-text-color,#666); margin:6px 0 10px; line-height:1.5; }
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
        ${this.value ? html`<button type="button" aria-label=${`${this.t("clearEntity")}: ${this.label}`} @click=${() => this.choose(null)}>×</button>` : nothing}</div>
      <small id="entity-help" class="help">${this.value ? `${this.t("selected")}: ${this.selected?.name ?? this.value} · ${this.value}${!this.selected || ["unknown", "unavailable"].includes(this.selected.state ?? "") ? ` · ${this.t("unavailable")}` : ""}` : this.t("noEntity")}</small>
      ${this.open ? html`<div class="results" id="entity-results" role="listbox" aria-label=${this.label}>
        ${results.map((entity, index) => html`<div role="option" tabindex="-1" id=${`entity-option-${index}`} aria-selected=${String(entity.entity_id === this.value)}
          ?data-active=${index === this.active} @mousedown=${(event: MouseEvent) => event.preventDefault()} @click=${() => this.choose(entity.entity_id)}>
          ${entity.name}<small>${entity.entity_id}${["unknown", "unavailable"].includes(entity.state ?? "") ? ` · ${this.t("unavailable")}` : ""}</small></div>`)}
      </div><div class="help" role="status">${results.length === 0 ? this.t("noResults") : results.length === 100 ? this.t("refineSearch") : `${results.length} ${this.t("results")}`}</div>` : nothing}`;
  }
}

customElements.define("halo-entity-picker", HaloEntityPicker);
