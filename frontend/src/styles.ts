import { css } from "lit";

/** Inherit the active Home Assistant theme, including changes made after mount. */
export const styles = css`
  :host {
    --halo-bg: var(--primary-background-color, Canvas);
    --halo-surface: var(--ha-card-background, var(--card-background-color, var(--halo-bg)));
    --halo-muted-bg: var(--secondary-background-color, var(--halo-surface));
    --halo-text: var(--primary-text-color, CanvasText);
    --halo-secondary: var(--secondary-text-color, var(--halo-text));
    --halo-line: var(--divider-color, var(--outline-color, GrayText));
    --halo-accent: var(--primary-color, Highlight);
    --halo-on-accent: var(--text-primary-color, HighlightText);
    --halo-selected: color-mix(in srgb, var(--halo-accent) 10%, var(--halo-surface));
    --halo-radius: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px));
    --halo-control-radius: var(--ha-border-radius-md, 8px);
    --halo-fast: var(--ha-animation-duration-fast, 150ms);
    --halo-space: var(--ha-space-4, 16px);
    display: flex; flex-direction: column; height: 100vh; height: 100dvh; overflow: hidden;
    color: var(--halo-text); background: var(--halo-bg); color-scheme: inherit;
    font-family: var(--ha-font-family-body, var(--paper-font-body1_-_font-family, inherit));
    font-size: var(--ha-font-size-m, 14px); line-height: var(--ha-line-height-normal, 1.6);
    font-weight: var(--ha-font-weight-normal, 400);
  }
  * { box-sizing: border-box; scrollbar-width: thin; scrollbar-color: var(--scrollbar-thumb-color,var(--halo-line)) transparent; }
  [hidden] { display: none !important; }
  ::selection { background: var(--halo-accent); color: var(--halo-on-accent); }
  :focus-visible { outline: 2px solid var(--halo-accent); outline-offset: 3px; }
  .app-header {
    display: flex; align-items: center; gap: var(--ha-space-6, 24px); min-height: 60px;
    padding: 0 var(--ha-space-5, 20px); flex-shrink: 0; z-index: 3;
    background: var(--app-header-background-color, var(--halo-surface));
    color: var(--app-header-text-color, var(--halo-text));
    border-bottom: var(--app-header-border-bottom, 1px solid var(--halo-line));
  }
  .brand { display: flex; align-items: center; gap: var(--ha-space-3, 12px); flex-shrink: 0; }
  .brand h1 { font-size: var(--ha-font-size-xl, 20px); margin: 0; letter-spacing: -.02em; }
  .brand small { display: none; }
  ha-icon { --mdc-icon-size: 20px; width: 20px; height: 20px; display: inline-flex; flex-shrink: 0; color: currentColor; }
  .brand ha-icon { --mdc-icon-size: 24px; width: 24px; height: 24px; }
  h1,h2,h3,h4 { font-family: var(--ha-font-family-heading, var(--ha-font-family-body, inherit)); font-weight: var(--ha-font-weight-bold, 700); line-height: var(--ha-line-height-condensed, 1.2); overflow-wrap: anywhere; }
  h2 { font-size: var(--ha-font-size-xl, 20px); margin: 0; }
  h3 { font-size: var(--ha-font-size-l, 16px); margin: 0 0 var(--ha-space-3, 12px); }
  h4 { font-size: var(--ha-font-size-m, 14px); margin: 0 0 var(--ha-space-2, 8px); }
  p { margin: var(--ha-space-2, 8px) 0 var(--ha-space-4, 16px); }
  small,.help,.room-meta,.scene-meta { color: var(--halo-secondary); }
  small { font-size: var(--ha-font-size-s, 12px); }
  .help { line-height: 1.55; max-width: 75ch; }
  .content { flex: 1; min-height: 0; display: flex; overflow: hidden; }
  main { flex: 1; min-width: 0; min-height: 0; display: flex; flex-direction: column; }
  .row,.actions,.section-actions,.room-toolbar,.room-modes { display: flex; align-items: center; gap: var(--ha-space-2, 8px); flex-wrap: wrap; }
  .grow { flex: 1; min-width: 0; }
  .top-nav { display: flex; align-self: stretch; gap: var(--ha-space-2, 8px); min-width: 0; }
  .top-nav button {
    position: relative; border: 0; border-radius: 0; padding: var(--ha-space-3, 12px) var(--ha-space-4, 16px);
    background: transparent; color: inherit; font-weight: var(--ha-font-weight-medium, 500);
  }
  .top-nav button[aria-current="page"]::after {
    content: ""; position: absolute; inset-inline: var(--ha-space-4, 16px); bottom: 0; height: 3px;
    background: currentColor; border-radius: 3px 3px 0 0;
  }
  .top-nav button:hover:not(:disabled) { background: color-mix(in srgb, currentColor 8%, transparent); }
  .workspace { display: grid; grid-template-columns: 264px minmax(0,1fr); flex: 1; min-height: 0; }
  .room-rail { min-height: 0; overflow-y: auto; background: var(--halo-surface); border-inline-end: 1px solid var(--halo-line); padding: var(--ha-space-4, 16px) var(--ha-space-3, 12px); }
  .rail-heading { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 4px 8px 12px; }
  .rail-heading h2 { font-size: var(--ha-font-size-l, 16px); }
  .rail-search { margin: 0 4px 12px; }
  .room-list { list-style: none; margin: 0; padding: 0; }
  .room-item { display: flex; align-items: center; gap: 4px; padding: 3px; margin-bottom: 4px; border-radius: var(--halo-control-radius); min-width: 0; }
  .room-item[data-active] { background: var(--halo-selected); }
  .room-link { justify-content: flex-start; display: flex; gap: 10px; align-items: center; flex: 1; min-width: 0; text-align: start; border: 0; background: transparent; padding: 10px 8px; }
  .room-link > span { min-width: 0; }
  .room-link strong { display: block; font-weight: var(--ha-font-weight-medium, 500); overflow-wrap: anywhere; }
  .room-link .room-meta { display: block; font-size: var(--ha-font-size-s, 12px); line-height: 1.45; overflow-wrap: anywhere; }
  .room-item[data-active] .room-link { color: var(--halo-accent); }
  .quick-toggle { align-self: center; margin-inline-end: 4px; }
  .quick-toggle[aria-pressed="true"],.room-item[data-state="on"] .room-link > ha-icon {
    color: var(--state-light-on-color, var(--state-light-active-color, var(--state-active-color, var(--halo-accent))));
  }
  .quick-toggle[aria-pressed="false"] { color: var(--state-light-off-color, var(--state-light-inactive-color, var(--state-inactive-color, var(--halo-secondary)))); }
  .room-detail { min-width: 0; min-height: 0; overflow: auto; padding: var(--ha-space-5, 20px) var(--ha-space-6, 24px) 32px; scroll-padding: 16px; }
  .room-heading { display: flex; align-items: center; justify-content: flex-start; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
  .room-heading .help { margin: 4px 0 0; }
  .room-heading .back-button { display: none; }
  .room-heading h2 { font-size: var(--ha-font-size-2xl, 24px); }
  .room-toolbar { margin: 12px 0; justify-content: space-between; row-gap: 12px; }
  .room-modes { column-gap: 20px; margin: 0; }
  .room-modes .check { margin: 0; }
  .room-tabs { display: flex; gap: 4px; overflow-x: auto; padding: 4px 0; border-bottom: 1px solid var(--halo-line); margin-bottom: var(--ha-space-5, 20px); }
  .room-tabs button { flex-shrink: 0; border: 0; background: transparent; color: var(--halo-secondary); border-radius: var(--halo-control-radius); padding: 8px 12px; }
  .room-tabs button[aria-current="page"],.room-tabs button[aria-selected="true"] { color: var(--halo-accent); background: var(--halo-selected); font-weight: var(--ha-font-weight-medium, 500); }
  .room-panel { min-width: 0; }
  section,.card { min-width: 0; }
  .room-panel > section,.room-panel > details,.room-panel > div > section { padding: 0; margin-bottom: 24px; }
  .section-heading { display: flex; align-items: center; gap: 12px; justify-content: space-between; flex-wrap: wrap; margin-bottom: 16px; }
  .section-heading .help-details { margin: 0; }
  .settings-group { padding: 20px 0; border-bottom: 1px solid var(--halo-line); }
  .settings-group:first-child { padding-top: 0; }
  .compact-help { font-size: var(--ha-font-size-s,12px); }
  .room-summary { margin-bottom: 16px; }
  .count { color: var(--halo-secondary); font-size: var(--ha-font-size-s,12px); font-variant-numeric: tabular-nums; }
  .danger-zone { margin-top: 32px; padding-top: 20px; border-top: 1px solid var(--halo-line); }
  .scene-automation { margin: 16px 0; }
  .section-heading h2 { font-size: var(--ha-font-size-l, 16px); }
  .room-panel > details > summary { font-size: var(--ha-font-size-l, 16px); }
  .grid { display: grid; grid-template-columns: repeat(auto-fit,minmax(min(100%,290px),1fr)); gap: var(--ha-space-5, 20px); }
  .field-grid { display: grid; grid-template-columns: repeat(auto-fit,minmax(min(100%,200px),1fr)); gap: var(--ha-space-2, 8px) var(--ha-space-4, 16px); }
  label { display: flex; flex-direction: column; gap: 6px; font-size: var(--ha-font-size-m, 14px); margin: 8px 0; min-width: 0; }
  /* Share label/control rows, including the entity picker's shadow content. */
  .field-grid > label:not(.check),.field-grid > halo-entity-picker { display: grid; grid-row: span 2; grid-template-rows: subgrid; row-gap: 6px; align-items: start; }
  .field-grid > halo-entity-picker::part(control) { margin-top: 0; }
  .check { flex-direction: row; align-items: center; gap: 10px; min-height: 32px; cursor: pointer; }
  input,select,button { font: inherit; }
  input,select { min-width: 0; width: 100%; min-height: 38px; padding: 7px 10px; border: 1px solid var(--input-outlined-idle-border-color,var(--halo-line)); border-radius: var(--halo-control-radius); background: var(--input-fill-color,var(--halo-surface)); color: var(--input-ink-color,var(--halo-text)); caret-color: var(--halo-accent); }
  input:hover,select:hover { border-color: var(--input-outlined-hover-border-color,var(--halo-secondary)); }
  input::placeholder { color: var(--input-label-ink-color,var(--halo-secondary)); opacity: 1; }
  input[type="checkbox"] { width: 18px; height: 18px; min-height: 18px; padding: 0; flex-shrink: 0; accent-color: var(--halo-accent); }
  input[type="color"] { padding: 3px; }
  input:invalid { border-color: var(--error-color,var(--halo-text)); }
  button { display: inline-flex; align-items: center; justify-content: center; gap: 7px; min-height: 36px; max-width: 100%; padding: 7px 12px; border: 1px solid var(--outline-color,var(--halo-line)); border-radius: var(--halo-control-radius); background: var(--halo-surface); color: var(--halo-text); cursor: pointer; line-height: 1.4; transition: background-color var(--halo-fast),color var(--halo-fast),border-color var(--halo-fast); }
  button:hover:not(:disabled) { background: var(--halo-muted-bg); border-color: var(--outline-hover-color,var(--halo-secondary)); }
  button:active:not(:disabled) { background: var(--halo-selected); }
  button.primary { background: var(--halo-accent); color: var(--halo-on-accent); border-color: transparent; }
  button.primary:hover:not(:disabled) { background: var(--halo-accent); filter: brightness(.94); }
  button:disabled { color: var(--disabled-text-color,var(--halo-secondary)); cursor: default; }
  button.primary:disabled { background: var(--halo-muted-bg); border-color: var(--halo-line); filter: none; }
  .icon-button { width: 36px; min-width: 36px; height: 36px; padding: 7px; border-color: transparent; background: transparent; }
  .danger { color: var(--error-color,var(--halo-text)); }
  .badge { display: inline-flex; align-items: center; gap: 5px; font-size: var(--ha-font-size-s,12px); color: var(--halo-secondary); padding: 2px 0; font-variant-numeric: tabular-nums; }
  .badge + .badge::before { content: "·"; margin-inline: 8px; }
  [aria-label] > .status-line { display: inline-block; margin: 2px 12px 2px 0; font-size: var(--ha-font-size-s,12px); }
  [aria-label] > .lighting-authorization { display: block; margin: 4px 0; }
  .notice { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 16px; margin: 12px 20px; background: var(--halo-selected); border: 1px solid var(--halo-line); border-radius: var(--halo-control-radius); line-height: 1.5; }
  .notice.error { color: var(--error-color,var(--halo-text)); background: var(--halo-surface); }
  .room-detail .notice,.profile-detail .notice { margin: 12px 0; }
  .savebar { flex-shrink: 0; z-index: 4; display: flex; align-items: center; gap: 12px; padding: 12px 20px calc(12px + env(safe-area-inset-bottom,0px)); border-top: 1px solid var(--halo-line); background: var(--halo-surface); }
  .savebar .grow { font-size: var(--ha-font-size-m,14px); }
  details { min-width: 0; }
  summary { cursor: pointer; font-weight: var(--ha-font-weight-medium,500); min-height: 36px; padding: 6px 0; }
  details[open] > summary { margin-bottom: 12px; }
  .help-details { color: var(--halo-secondary); margin: 8px 0 16px; }
  .help-details summary ha-icon { vertical-align: middle; margin-inline-end: 4px; }
  .help-details summary { font-size: var(--ha-font-size-s,12px); min-height: 28px; }
  .help-details .help { margin: 0 0 10px; }
  .help-details[open] > summary { margin-bottom: 4px; }
  .light-list { max-height: none; overflow: visible; }
  .light-list h3 { color: var(--halo-secondary); font-weight: var(--ha-font-weight-medium,500); font-size: var(--ha-font-size-s,12px); margin: 18px 0 6px; }
  .light-option { display: flex; align-items: center; gap: 12px; padding: 4px 0; border-bottom: 1px solid var(--halo-line); }
  .light-option .check { flex: 1; }
  .light-option small,.group-info { display: block; overflow-wrap: anywhere; }
  .group-info { font-size: var(--ha-font-size-s,12px); line-height: 1.45; }
  .association,.lamp { border-bottom: 1px solid var(--halo-line); padding: 12px 0; margin: 0; }
  .association > summary,.lamp > summary { display: list-item; }
  .association > summary small,.scene-automation > summary small { margin-inline-start: 8px; }
  .lamp h4 { display: inline; }
  .association .help { margin-bottom: 8px; }
  .transition-grid { grid-template-columns: 1fr; gap: 0; }
  .transition-field { display: grid; grid-template-columns: minmax(140px,1fr) minmax(170px,1fr) minmax(100px,.65fr); gap: 12px; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--halo-line); }
  .transition-field h4 { margin: 0; }
  .transition-field label,.transition-field p { margin: 0; }
  .transition-field label { font-size: var(--ha-font-size-s,12px); }
  .transition-field p { color: var(--halo-secondary); font-size: var(--ha-font-size-s,12px); }
  .scene-row { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; padding: 14px 0; border-bottom: 1px solid var(--halo-line); position: relative; }
  .scene-row > .scene-order { width: 22px; flex-shrink: 0; color: var(--halo-secondary); }
  .scene-row .actions { flex-wrap: nowrap; }
  .scene-row:has(.row-menu[open]) > .actions { flex-basis: 100%; flex-wrap: wrap; justify-content: flex-end; }
  .scene-row[draggable="true"] { cursor: grab; }
  .scene-meta { display: block; font-size: var(--ha-font-size-s,12px); font-weight: var(--ha-font-weight-normal,400); line-height: 1.4; }
  .row-menu { position: relative; }
  .row-menu summary { list-style: none; display: flex; align-items: center; justify-content: center; margin: 0; border-radius: var(--halo-control-radius); }
  .row-menu summary::-webkit-details-marker { display: none; }
  .row-menu[open] > summary { background: var(--halo-muted-bg); margin: 0; }
  .menu-actions { display: flex; flex-wrap: wrap; gap: 4px; padding: 6px 0; }
  .row-menu[open] { flex-basis: 100%; }
  .row-menu[open] > summary { width: 36px; margin-inline-start: auto; }
  .menu-actions button { border: 0; justify-content: flex-start; text-align: start; }
  .profiles-page { display: flex; flex-direction: column; flex: 1; min-height: 0; min-width: 0; overflow: hidden; }
  .profiles-page > .section-heading { padding: 20px 24px 0; margin-bottom: 8px; }
  .profiles-page > .help-details { margin: 0 24px 16px; }
  .profile-link > span { min-width: 0; }
  .profile-link strong,.profile-link small { display: block; overflow-wrap: anywhere; }
  .profiles-workspace { display: grid; grid-template-columns: 240px minmax(0,1fr); flex: 1; min-height: 0; }
  .profile-list { background: var(--halo-surface); padding: 20px 12px; border-inline-end: 1px solid var(--halo-line); overflow-y: auto; }
  .profile-list > button { width: 100%; margin: 4px 0; justify-content: flex-start; text-align: start; }
  .profile-list > button[aria-current="true"],.profile-list > button[aria-current="page"] { background: var(--halo-selected); color: var(--halo-accent); }
  .profile-detail { min-width: 0; overflow: auto; padding: 20px 24px 32px; }
  .profile { min-width: 0; }
  .profile > h3 { margin: 24px 0 12px; }
  .profile .grid > div { min-width: 0; }
  .profile svg { display: block; margin: 12px 0 0; }
  .global-settings { padding: 24px; overflow: auto; flex: 1; min-height: 0; }
  .global-settings > section { max-width: 980px; margin: 0 auto 28px; }
  .global-settings > h2 { max-width: 980px; margin: 0 auto 24px; }
  .editor,.scene-import,.scene-link { max-width: 980px; margin: 0 auto; width: 100%; }
  .scene-add-menu > summary { display: flex; align-items: center; gap: 6px; padding: 8px 12px; border-radius: var(--halo-control-radius); background: var(--halo-accent); color: var(--halo-on-accent); list-style: none; }
  .scene-add-menu > summary::-webkit-details-marker { display: none; }
  .scene-add-menu .menu-actions { flex-direction: column; align-items: stretch; }
  .scene-scope { margin: 12px 0; }
  .scene-scope .notice { margin: 12px 0; }
  .scope-warning { border-block-start: 1px solid var(--halo-line); padding-block-start: 12px; margin-block: 12px; }
  .scene-scope ul { padding-inline-start: 20px; }
  .scene-scope li { margin-bottom: 6px; overflow-wrap: anywhere; }
  .scene-scope li small { display: block; }
  .editor-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
  .editor-actions { position: sticky; bottom: -32px; z-index: 3; display: flex; justify-content: flex-end; gap: 10px; margin-top: 24px; padding: 12px 0 calc(12px + env(safe-area-inset-bottom,0px)); background: var(--halo-bg); border-top: 1px solid var(--halo-line); }
  .scene-lights { list-style: none; padding: 0; margin: 12px 0 20px; }
  .scene-lights li { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--halo-line); min-width: 0; }
  .scene-inclusion { margin: 0; }
  .scene-lamp { display: flex; align-items: center; gap: 12px; width: 100%; text-align: start; justify-content: flex-start; border: 0; padding: 8px; background: transparent; }
  .scene-lamp strong,.scene-lamp small,.scene-lamp .grow > span { display: block; overflow-wrap: anywhere; }
  .scene-lamp .grow > span { margin-top: 3px; font-size: var(--ha-font-size-s,12px); }
  .import-lights { padding: 0; list-style: none; }
  .import-lights li { padding: 10px 0; border-bottom: 1px solid var(--halo-line); }
  .import-lights small { display: block; overflow-wrap: anywhere; }
  .condition { padding: 12px; margin: 12px 0; border: 1px solid var(--halo-line); border-radius: var(--halo-control-radius); background: var(--halo-surface); min-width: 0; }
  .condition .condition { border-radius: 0; border-width: 0 0 1px; padding: 8px 0; margin: 4px 0; }
  .condition > .row > .grow { min-width: min(100%,180px); }
  svg { width: 100%; max-height: 200px; overflow: visible; color: var(--halo-accent); }
  svg text { fill: var(--halo-secondary); font-size: 11px; font-variant-numeric: tabular-nums; }
  .empty { padding: 24px 0; color: var(--halo-secondary); max-width: 65ch; }
  .empty h2,.empty h3 { color: var(--halo-text); margin-bottom: 12px; }
  .empty-state { padding: 40px 24px; max-width: 520px; margin: 8vh auto 0; }
  .empty-state > ha-icon { --mdc-icon-size: 32px; width: 32px; height: 32px; color: var(--halo-secondary); margin-bottom: 16px; }
  .empty-state p { color: var(--halo-secondary); }
  @media (max-width:1100px) {
    .workspace { grid-template-columns: 224px minmax(0,1fr); }
    .room-detail,.profile-detail { padding: 16px 18px 28px; }
    .room-tabs button { padding: 8px 10px; }
    .transition-field { grid-template-columns: minmax(130px,1fr) minmax(170px,1fr); }
    .transition-field > :last-child:not(:nth-child(2)) { grid-column: 2; }
  }
  @media (max-width:760px) {
    .app-header { gap: 8px; padding: 8px 12px 0; flex-wrap: wrap; min-height: 52px; }
    .brand { padding-bottom: 8px; gap: 8px; }
    .brand h1 { font-size: var(--ha-font-size-l,16px); }
    .top-nav { margin-inline-start: auto; overflow-x: auto; }
    .top-nav button { padding: 10px 9px; font-size: var(--ha-font-size-s,12px); }
    .workspace { display: block; overflow: hidden; }
    .room-rail { height: 100%; border-inline-end: 0; padding: 16px 12px; }
    .workspace:not(.has-room) .room-detail { display: none; }
    .workspace.has-room .room-rail { display: none; }
    .workspace.has-room .room-detail { display: block; height: 100%; }
    .room-detail { padding: 16px 14px 28px; }
    .room-heading .back-button { display: inline-flex; }
    .room-link { padding: 12px 8px; }
    .room-heading h2 { font-size: var(--ha-font-size-xl,20px); }
    .room-tabs { margin-inline: -14px; padding: 4px 14px 8px; }
    .profiles-workspace { display: flex; flex-direction: column; overflow: auto; }
    .profile-list { overflow: visible; border: 0; border-bottom: 1px solid var(--halo-line); padding: 14px; }
    .profile-detail { overflow: visible; padding: 16px 14px 28px; }
    .global-settings { padding: 20px 14px; }
    .savebar { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 10px 14px calc(10px + env(safe-area-inset-bottom,0px)); }
    .savebar .grow { grid-column: 1 / -1; font-size: var(--ha-font-size-s,12px); }
    .savebar button { min-width: 0; padding: 9px 6px; font-size: var(--ha-font-size-s,12px); }
    .transition-field { grid-template-columns: 1fr 1fr; }
    .transition-field > h4 { grid-column: 1 / -1; }
    .transition-field > :last-child:not(:nth-child(2)) { grid-column: auto; }
    .scene-row { gap: 8px; }
    .scene-row > .grow { flex-basis: calc(100% - 40px); }
    .scene-row > .actions { margin-inline-start: 30px; }
    .scene-lights li { align-items: flex-start; }
    .scene-inclusion { margin-top: 8px; }
    .scene-inclusion > span { display: none; }
    .notice { margin: 8px 12px; flex-wrap: wrap; }
    .empty-state { margin-top: 24px; padding: 16px; }
  }
  @media (pointer:coarse) { button,input,select,summary { min-height: 44px; } input[type="checkbox"] { min-height: 20px; width: 20px; height: 20px; } .icon-button { width: 44px; min-width: 44px; height: 44px; } }
  @media (prefers-reduced-motion:reduce) { *,*::before,*::after { animation: none !important; transition: none !important; scroll-behavior: auto !important; } }
`;
