import { css } from "lit";

export const styles = css`
  :host { display:flex; flex-direction:column; height:100vh; height:100dvh; overflow:hidden; color:var(--primary-text-color,#212121); background:var(--primary-background-color,#fafafa); font-family:var(--paper-font-body1_-_font-family,Roboto,Arial,sans-serif); color-scheme:light dark; }
  * { box-sizing:border-box; }
  header { flex-shrink:0; z-index:3; display:flex; align-items:center; gap:12px; padding:12px 20px; background:var(--app-header-background-color,var(--card-background-color,#fff)); border-bottom:1px solid var(--divider-color,#ddd); }
  header h1 { font-size:22px; margin:0; } header small { color:var(--secondary-text-color,#666); }
  .content { flex:1; min-height:0; overflow:auto; overscroll-behavior:contain; }
  main { max-width:1200px; margin:auto; padding:24px; }
  nav,.row,.actions { display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
  nav { margin-bottom:24px; } nav button[aria-current="page"] { background:var(--primary-color,#03a9f4); color:var(--text-primary-color,#fff); }
  .grow { flex:1; min-width:0; } .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,290px),1fr)); gap:16px; }
  section,.card,details { background:var(--card-background-color,#fff); border:1px solid var(--divider-color,#ddd); border-radius:var(--ha-card-border-radius,12px); padding:20px; margin-bottom:18px; }
  .card { margin:0; } .card h2 { margin-top:0; } .card .actions { margin-top:16px; }
  h2 { font-size:21px; margin:0 0 16px; } h3 { font-size:17px; margin:0 0 12px; } h4 { font-size:15px; margin:0 0 10px; }
  p { line-height:1.5; } .help,small { color:var(--secondary-text-color,#666); line-height:1.5; } .help { margin:8px 0 16px; }
  label { display:flex; flex-direction:column; gap:6px; font-size:14px; margin:10px 0; min-width:0; }
  .check { flex-direction:row; align-items:center; gap:10px; cursor:pointer; }
  input,select,button { font:inherit; color:inherit; }
  input,select { width:100%; min-height:42px; padding:9px; border:1px solid var(--divider-color,#aaa); border-radius:6px; background:var(--input-fill-color,var(--card-background-color,#fff)); }
  input[type="checkbox"] { width:20px; height:20px; min-height:20px; flex-shrink:0; accent-color:var(--primary-color,#03a9f4); }
  input[type="color"] { padding:3px; } input:invalid { border-color:var(--error-color,#db4437); }
  button { min-height:42px; border:1px solid var(--divider-color,#bbb); background:var(--card-background-color,#fff); padding:9px 14px; border-radius:8px; cursor:pointer; }
  button:hover:not(:disabled) { background:var(--secondary-background-color,#eee); } button.primary { background:var(--primary-color,#03a9f4); border-color:transparent; color:var(--text-primary-color,#fff); }
  button:disabled { opacity:.5; cursor:default; } :focus-visible { outline:3px solid var(--primary-color,#03a9f4); outline-offset:3px; }
  .danger { color:var(--error-color,#db4437); } .badge { display:inline-block; font-size:13px; padding:4px 8px; border-radius:6px; background:var(--secondary-background-color,#eee); }
  .notice { background:var(--secondary-background-color,#eee); border-left:4px solid var(--primary-color,#03a9f4); padding:14px; margin:12px 0; line-height:1.5; }
  .error { border-color:var(--error-color,#db4437); } .savebar { flex-shrink:0; z-index:2; display:flex; gap:12px; align-items:center; flex-wrap:wrap; padding:14px 20px calc(14px + env(safe-area-inset-bottom,0px)); border-top:1px solid var(--divider-color,#ddd); background:var(--card-background-color,#fff); }
  .light-list { max-height:380px; overflow:auto; } .light-option { display:flex; align-items:center; gap:12px; padding:9px 0; border-bottom:1px solid var(--divider-color,#ddd); }
  .light-option .check { flex:1; } .light-option small,.association small,.group-info { display:block; overflow-wrap:anywhere; }
  .field-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,200px),1fr)); gap:6px 18px; }
  .transition-grid { row-gap:16px; }
  .transition-field { display:grid; grid-template-rows:subgrid; grid-row:span 3; row-gap:0; min-width:0; }
  .transition-field > h4 { margin-bottom:0; }
  .lamp,.association,.scene-row,.profile { padding:16px; border:1px solid var(--divider-color,#ddd); border-radius:8px; margin:12px 0; }
  .scene-row { display:flex; align-items:center; gap:12px; flex-wrap:wrap; } .scene-row[draggable="true"] { cursor:grab; }
  .scene-lights { list-style:none; padding:0; margin:12px 0 20px; }
  .scene-lights li + li { margin-top:10px; }
  .scene-inclusion { margin-bottom:6px; }
  .import-lights li { margin:10px 0; }
  .import-lights small { display:block; overflow-wrap:anywhere; }
  .scene-lamp { display:flex; align-items:center; gap:16px; width:100%; padding:14px 16px; text-align:start; }
  .scene-lamp strong,.scene-lamp small,.scene-lamp .grow > span { display:block; overflow-wrap:anywhere; }
  .scene-lamp .grow > span { margin-top:4px; font-size:14px; }
  summary { cursor:pointer; font-weight:500; min-height:32px; } details[open]>summary { margin-bottom:12px; }
  .condition { padding:12px; margin:12px 0; border-left:3px solid var(--divider-color,#ddd); background:var(--secondary-background-color,#f6f6f6); }
  .condition .condition { margin-left:10px; background:var(--card-background-color,#fff); }
  .editor { border:2px solid var(--primary-color,#03a9f4); } .muted { opacity:.7; }
  svg { width:100%; max-height:220px; overflow:visible; color:var(--primary-color,#03a9f4); } svg text { fill:var(--secondary-text-color,#555); font-size:11px; }
  .empty { padding:28px 0; color:var(--secondary-text-color,#666); } .status-line { margin:8px 0; }
  @media (max-width:600px) { main { padding:14px; } header { padding:10px 14px; } header small { display:none; } section,details { padding:16px; } .savebar { display:grid; grid-template-columns:1fr 1fr; padding:12px 14px calc(12px + env(safe-area-inset-bottom,0px)); } .savebar .grow { grid-column:1 / -1; } .savebar button { min-width:0; } .scene-row .actions { width:100%; } }
  @media (prefers-reduced-motion:reduce) { * { scroll-behavior:auto!important; } }
`;
