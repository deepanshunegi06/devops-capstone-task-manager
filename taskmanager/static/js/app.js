// Orbit SPA entry: bootstrap, sidebar, router, shortcuts.
import { html, render, $, isTyping } from "./ui/dom.js";
import { icon } from "./ui/icons.js";
import { state, bootstrap, on as onStore, projectById, labelById } from "./store.js";
import { applyTheme, themePref, isDark } from "./theme.js";
import { openMenu, closeMenu } from "./ui/menu.js";
import { openModal, closeTopModal } from "./ui/modal.js";
import { openPalette, closePalette, paletteOpen } from "./ui/palette.js";
import { openDrawer, closeDrawer, isDrawerOpen, reloadDrawer } from "./ui/drawer.js";
import { toastError } from "./ui/toast.js";
import { avatar } from "./ui/task-ui.js";
import { mountQuickAdd } from "./quickadd.js";
import { renderList } from "./views/list.js";
import { renderBoard } from "./views/board.js";
import { renderCalendar } from "./views/calendar.js";
import { renderMatrix } from "./views/matrix.js";
import { renderAnalytics } from "./views/analytics.js";
import { renderFocus } from "./views/focus.js";
import { renderActivity } from "./views/activity.js";
import { renderSettings } from "./views/settings.js";
import { projectModal, labelModal, projectMenu } from "./views/projects.js";

const LIST_ROUTES = ["today", "inbox", "upcoming", "overdue", "completed", "assigned", "project", "label"];
const SMART = [
  { r: "inbox", label: "Inbox", ic: "inbox", count: "inbox" },
  { r: "today", label: "Today", ic: "today", count: "today" },
  { r: "upcoming", label: "Upcoming", ic: "upcoming", count: "upcoming" },
  { r: "overdue", label: "Overdue", ic: "overdue", count: "overdue", danger: true },
  { r: "assigned", label: "Assigned to me", ic: "assigned", count: "assigned" },
  { r: "completed", label: "Completed", ic: "completed", count: "completed_today", hint: "today" },
];
const TOOLS = [
  { r: "board", label: "Board", ic: "board" },
  { r: "calendar", label: "Calendar", ic: "calendar" },
  { r: "matrix", label: "Priority matrix", ic: "matrix" },
  { r: "analytics", label: "Analytics", ic: "analytics" },
  { r: "focus", label: "Focus", ic: "focus" },
  { r: "activity", label: "Activity", ic: "activity" },
];
const TITLES = {
  today: "Today", inbox: "Inbox", upcoming: "Upcoming", overdue: "Overdue", completed: "Completed", assigned: "Assigned to me",
  board: "Board", calendar: "Calendar", matrix: "Priority matrix", analytics: "Analytics", focus: "Focus", activity: "Activity", settings: "Settings",
};

const viewEl = () => document.getElementById("view");
let current = { hash: null, view: null, route: null };
let lastViewHash = "#/today";
let renderSeq = 0;

/* ---------------- routing ---------------- */
function parseHash(h = location.hash) {
  const raw = (h || "").replace(/^#\/?/, "") || "today";
  const [path, q = ""] = raw.split("?");
  const parts = path.split("/").filter(Boolean);
  const query = Object.fromEntries(new URLSearchParams(q));
  return { route: parts[0] || "today", params: { id: parts[1] }, query, hash: `#/${raw}` };
}

export function openTask(id) { location.hash = `#/task/${id}`; }

async function router() {
  closeMenu();
  closePalette();
  const r = parseHash();
  document.getElementById("sidebar").classList.remove("open");
  $("#scrim").hidden = true;

  if (r.route === "task") {
    if (!current.view) await renderView(parseHash(lastViewHash));
    openDrawer(r.params.id, { onClose: () => { history.length > 1 && current.hash === lastViewHash ? (location.hash = lastViewHash) : (location.hash = lastViewHash); } });
    return;
  }
  if (isDrawerOpen()) closeDrawer({ fromRouter: true });
  if (r.hash === current.hash && current.view) return;
  lastViewHash = r.hash;
  await renderView(r);
}

async function renderView(r) {
  const seq = ++renderSeq;
  const el = viewEl();
  current = { hash: r.hash, view: null, route: r.route };
  let mode = r.query.mode || "list";
  if (r.route === "board") mode = "board";
  const project = r.route === "project" ? projectById(r.params.id) : null;
  const label = r.route === "label" ? labelById(r.params.id) : null;

  if ((r.route === "project" && !project) || (r.route === "label" && !label)) {
    if (!state.loaded) await bootstrap();
  }
  const p2 = r.route === "project" ? projectById(r.params.id) : null;
  const l2 = r.route === "label" ? labelById(r.params.id) : null;
  const title = p2 ? html`<span class="t-emoji">${p2.icon || "📁"}</span>${p2.name}` : l2 ? html`<span class="t-label" data-c="${l2.color}">@${l2.name}</span>` : (TITLES[r.route] || "Orbit");
  render($("#view-title"), title);
  document.title = `${p2?.name || (l2 ? `@${l2.name}` : TITLES[r.route] || "Orbit")} · Orbit`;
  $("#view-sub").textContent = "";
  paintSwitcher(r, mode);
  paintActive(r);

  el.classList.remove("view-in");
  void el.offsetWidth;
  el.classList.add("view-in");

  const ctx = {
    el, route: r.route, params: r.params, query: r.query, openTask,
    setSub: (s) => { if (seq === renderSeq) $("#view-sub").textContent = s; },
  };
  try {
    let view;
    if (LIST_ROUTES.includes(r.route)) view = mode === "board" ? await renderBoard(ctx) : await renderList(ctx);
    else if (r.route === "board") view = await renderBoard(ctx);
    else if (r.route === "calendar") view = await renderCalendar(ctx);
    else if (r.route === "matrix") view = await renderMatrix(ctx);
    else if (r.route === "analytics") view = await renderAnalytics(ctx);
    else if (r.route === "focus") view = await renderFocus(ctx);
    else if (r.route === "activity") view = await renderActivity(ctx);
    else if (r.route === "settings") view = await renderSettings(ctx);
    else { location.hash = "#/today"; return; }
    if (seq === renderSeq) current.view = view;
  } catch (e) { toastError(e); }
}

function paintSwitcher(r, mode) {
  const sw = $("#view-switch");
  const isList = LIST_ROUTES.includes(r.route);
  const showFor = isList || ["board", "calendar", "matrix"].includes(r.route);
  if (!showFor || r.route === "completed") { render(sw, ""); return; }
  const base = isList ? `#/${r.route}${r.params.id ? `/${r.params.id}` : ""}` : "#/today";
  const projQ = r.route === "project" ? `?project=${r.params.id}` : "";
  const opts = [
    { k: "list", label: "List", ic: "list", href: base, on: isList && mode !== "board" },
    { k: "board", label: "Board", ic: "board", href: isList ? `${base}?mode=board` : "#/board", on: mode === "board" || r.route === "board" },
    { k: "calendar", label: "Calendar", ic: "calendar", href: `#/calendar${projQ}`, on: r.route === "calendar" },
    { k: "matrix", label: "Matrix", ic: "matrix", href: "#/matrix", on: r.route === "matrix" },
  ];
  render(sw, html`${opts.map((o) => html`<a class="sw ${o.on ? "on" : ""}" href="${o.href}" role="tab" aria-selected="${o.on}" title="${o.label}">${icon(o.ic, 15)}<span>${o.label}</span></a>`)}`);
}

/* ---------------- sidebar ---------------- */
function paintSidebar() {
  const c = state.counts || {};
  render($("#sidebar-nav"), html`
    <button class="add-task-btn" id="side-add">${icon("plus", 16)}<span>Add task</span><kbd>Q</kbd></button>
    <ul class="nav-list">${SMART.map((s) => html`<li><a class="nav-link" href="#/${s.r}" data-route="${s.r}">
      <span class="nav-ic ic-${s.r}">${icon(s.ic, 18)}</span><span class="nav-label">${s.label}</span>
      ${c[s.count] ? html`<span class="nav-count ${s.danger ? "danger" : ""}" title="${s.hint || ""}">${c[s.count]}</span>` : ""}</a></li>`)}</ul>
    <ul class="nav-list">${TOOLS.map((s) => html`<li><a class="nav-link" href="#/${s.r}" data-route="${s.r}">
      <span class="nav-ic">${icon(s.ic, 18)}</span><span class="nav-label">${s.label}</span></a></li>`)}</ul>
    <div class="nav-section"><span>Projects</span><button class="icon-btn xs" id="add-project" aria-label="New project" title="New project">${icon("plus", 15)}</button></div>
    <ul class="nav-list">${state.projects.length ? state.projects.map((p) => html`<li class="proj-li"><a class="nav-link" href="#/project/${p.id}" data-route="project/${p.id}">
        <span class="nav-emoji" data-c="${p.color}">${p.icon || "📁"}</span><span class="nav-label">${p.name}</span>
        ${p.members && p.members.length > 1 ? html`<span class="shared-ic" title="Shared">${icon("users", 13)}</span>` : ""}
        ${p.open_count ? html`<span class="nav-count">${p.open_count}</span>` : ""}</a>
        <button class="icon-btn xs nav-more" data-pmenu="${p.id}" aria-label="Project options">${icon("dots", 15)}</button></li>`)
      : html`<li class="nav-empty">No projects yet. <button class="link-btn" id="first-project">Create one</button></li>`}</ul>
    <div class="nav-section"><span>Labels</span><button class="icon-btn xs" id="add-label" aria-label="New label" title="New label">${icon("plus", 15)}</button></div>
    <ul class="nav-list labels">${state.labels.map((l) => html`<li><a class="nav-link" href="#/label/${l.id}" data-route="label/${l.id}">
        <span class="nav-ic lbl-ic" data-c="${l.color}">${icon("tag", 16)}</span><span class="nav-label">${l.name}</span>
        ${l.open_count ? html`<span class="nav-count">${l.open_count}</span>` : ""}</a></li>`)}</ul>
    <ul class="nav-list bottom"><li><a class="nav-link" href="#/settings" data-route="settings"><span class="nav-ic">${icon("settings", 18)}</span><span class="nav-label">Settings</span></a></li></ul>`);
  paintActive(parseHash(current.hash || location.hash));
  render($("#avatar-btn"), avatar(state.user, 30));
}

function paintActive(r) {
  const key = r.route === "project" || r.route === "label" ? `${r.route}/${r.params.id}` : r.route;
  document.querySelectorAll(".nav-link").forEach((a) => a.classList.toggle("active", a.dataset.route === key || (r.route === "board" && a.dataset.route === "board" && !r.params.id)));
  document.querySelectorAll(".bn-item").forEach((a) => a.classList.toggle("active", a.dataset.route === key));
}

function paintChrome() {
  render($("#menu-btn"), icon("menu", 20));
  render($("#collapse-btn"), icon("sidebar", 18));
  render($("#fab"), icon("plus", 26));
  render($(".search-ic"), icon("search", 16));
  $("#kbd-hint").textContent = /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘K" : "Ctrl K";
  paintThemeBtn();
  render($("#bottomnav"), html`
    <a class="bn-item" href="#/today" data-route="today">${icon("today", 20)}<span>Today</span></a>
    <a class="bn-item" href="#/upcoming" data-route="upcoming">${icon("upcoming", 20)}<span>Upcoming</span></a>
    <span class="bn-gap"></span>
    <a class="bn-item" href="#/board" data-route="board">${icon("board", 20)}<span>Board</span></a>
    <button class="bn-item" id="bn-menu">${icon("menu", 20)}<span>Menu</span></button>`);
}

function paintThemeBtn() {
  render($("#theme-btn"), icon(isDark() ? "sun" : "moon", 18));
  $("#theme-btn").title = isDark() ? "Switch to light" : "Switch to dark";
}

async function toggleTheme() {
  const next = isDark() ? "light" : "dark";
  applyTheme(next);
  try { const { patch } = await import("./api.js"); await patch("/me", { theme: next }); } catch { /* offline ok */ }
}

/* ---------------- quick add modal, help, account ---------------- */
function quickAddModal(opts = {}) {
  const r = parseHash(current.hash || location.hash);
  openModal({
    title: "Add task", className: "qa-modal",
    body: html`<div id="qa-modal"></div>`,
    onMount(el, close) {
      mountQuickAdd(el.querySelector("#qa-modal"), {
        projectId: opts.projectId ?? (r.route === "project" ? r.params.id : undefined), autofocus: true,
        onCreated: () => close(),
      });
    },
  });
}

function shortcutsHelp() {
  const rows = [
    ["Q", "Quick add task"], ["⌘K / Ctrl K or /", "Command palette & search"], ["G then T", "Go to Today"], ["G then I", "Go to Inbox"],
    ["G then U", "Go to Upcoming"], ["G then B", "Board"], ["G then C", "Calendar"], ["G then M", "Priority matrix"], ["G then A", "Analytics"],
    ["G then F", "Focus timer"], ["G then S", "Settings"], ["Shift D", "Toggle dark mode"], ["?", "This help"], ["Esc", "Close dialogs / drawer"],
  ];
  openModal({
    title: "Keyboard shortcuts",
    body: html`<ul class="shortcuts">${rows.map(([k, d]) => html`<li><span>${d}</span><span>${k.split(" ").map((x) => (["then", "or", "/"].includes(x) && x !== "/") ? html`<em>${x}</em>` : html`<kbd>${x}</kbd>`)}</span></li>`)}</ul>`,
  });
}

function accountMenu(anchor) {
  const u = state.user || {};
  openMenu(anchor, [
    { header: `${u.display_name || u.username} · @${u.username}` },
    { label: "Settings", icon: "settings", onClick: () => { location.hash = "#/settings"; } },
    { label: isDark() ? "Light mode" : "Dark mode", icon: isDark() ? "sun" : "moon", hint: "⇧D", onClick: toggleTheme },
    { label: "Keyboard shortcuts", icon: "keyboard", hint: "?", onClick: shortcutsHelp },
    { sep: true },
    { label: "Export JSON", icon: "download", onClick: () => { location.href = "/api/export.json"; } },
    { label: "Export CSV", icon: "download", onClick: () => { location.href = "/api/export.csv"; } },
    { sep: true },
    { label: "Log out", icon: "logout", danger: true, onClick: () => { location.href = "/logout"; } },
  ], { align: "right", width: 240 });
}

function commands() {
  const go = (h) => () => { location.hash = h; };
  return [
    { label: "New task", icon: "plus", hint: "Q", run: () => quickAddModal(), keywords: "add create" },
    { label: "New project", icon: "hash", run: () => projectModal(), keywords: "create" },
    { label: "New label", icon: "tag", run: () => labelModal(), keywords: "create tag" },
    { label: "Go to Today", icon: "today", hint: "G T", run: go("#/today") },
    { label: "Go to Inbox", icon: "inbox", hint: "G I", run: go("#/inbox") },
    { label: "Go to Upcoming", icon: "upcoming", hint: "G U", run: go("#/upcoming") },
    { label: "Go to Overdue", icon: "overdue", run: go("#/overdue") },
    { label: "Assigned to me", icon: "assigned", run: go("#/assigned") },
    { label: "Completed tasks", icon: "completed", run: go("#/completed") },
    { label: "Open Board", icon: "board", hint: "G B", run: go("#/board"), keywords: "kanban" },
    { label: "Open Calendar", icon: "calendar", hint: "G C", run: go("#/calendar") },
    { label: "Open Priority matrix", icon: "matrix", hint: "G M", run: go("#/matrix"), keywords: "eisenhower" },
    { label: "Open Analytics", icon: "analytics", hint: "G A", run: go("#/analytics"), keywords: "stats insights" },
    { label: "Start focus session", icon: "focus", hint: "G F", run: go("#/focus"), keywords: "pomodoro timer" },
    { label: "Activity feed", icon: "activity", run: go("#/activity") },
    { label: "Settings", icon: "settings", hint: "G S", run: go("#/settings"), keywords: "profile share members" },
    { label: "Toggle dark mode", icon: "moon", hint: "⇧D", run: toggleTheme, keywords: "theme light" },
    { label: "Keyboard shortcuts", icon: "keyboard", hint: "?", run: shortcutsHelp, keywords: "help" },
    { label: "Export data as JSON", icon: "download", run: () => { location.href = "/api/export.json"; } },
    { label: "Export data as CSV", icon: "download", run: () => { location.href = "/api/export.csv"; } },
    { label: "Log out", icon: "logout", run: () => { location.href = "/logout"; } },
  ];
}
const showPalette = () => openPalette(commands(), { openTask });

/* ---------------- keyboard ---------------- */
let gPending = 0;
function onKey(e) {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); paletteOpen() ? closePalette() : showPalette(); return; }
  if (e.key === "Escape") {
    if (paletteOpen()) { closePalette(); return; }
    if (document.querySelector(".menu")) { closeMenu(); return; }
    if (closeTopModal()) return;
    if (isDrawerOpen()) { closeDrawer(); return; }
    if (isTyping(e)) e.target.blur();
    return;
  }
  if (isTyping(e) || e.metaKey || e.ctrlKey || e.altKey || paletteOpen() || document.querySelector(".modal-backdrop")) return;
  const k = e.key;
  if (gPending && Date.now() - gPending < 1200) {
    gPending = 0;
    const map = { t: "#/today", i: "#/inbox", u: "#/upcoming", b: "#/board", c: "#/calendar", m: "#/matrix", a: "#/analytics", f: "#/focus", s: "#/settings", o: "#/overdue" };
    if (map[k.toLowerCase()]) { e.preventDefault(); location.hash = map[k.toLowerCase()]; }
    return;
  }
  if (k === "g") { gPending = Date.now(); return; }
  if (k === "q" || k === "n") {
    e.preventDefault();
    const qa = document.querySelector("#view .qa-input");
    if (qa && !isDrawerOpen()) { qa.focus(); qa.scrollIntoView({ block: "center", behavior: "smooth" }); } else quickAddModal();
  } else if (k === "/") { e.preventDefault(); showPalette(); }
  else if (k === "?") { e.preventDefault(); shortcutsHelp(); }
  else if (k === "D" && e.shiftKey) { toggleTheme(); }
}

/* ---------------- init ---------------- */
async function init() {
  paintChrome();
  if (localStorage.getItem("orbit-sidebar") === "collapsed") document.body.classList.add("sidebar-collapsed");

  $("#search-btn").addEventListener("click", showPalette);
  $("#theme-btn").addEventListener("click", toggleTheme);
  $("#avatar-btn").addEventListener("click", (e) => accountMenu(e.currentTarget));
  $("#fab").addEventListener("click", () => quickAddModal());
  $("#collapse-btn").addEventListener("click", () => {
    document.body.classList.toggle("sidebar-collapsed");
    localStorage.setItem("orbit-sidebar", document.body.classList.contains("sidebar-collapsed") ? "collapsed" : "open");
  });
  const openSide = () => { $("#sidebar").classList.add("open"); $("#scrim").hidden = false; };
  const closeSide = () => { $("#sidebar").classList.remove("open"); $("#scrim").hidden = true; };
  $("#menu-btn").addEventListener("click", openSide);
  $("#scrim").addEventListener("click", closeSide);
  $("#bottomnav").addEventListener("click", (e) => { if (e.target.closest("#bn-menu")) openSide(); });
  $("#sidebar-nav").addEventListener("click", (e) => {
    if (e.target.closest("#side-add")) quickAddModal();
    if (e.target.closest("#add-project") || e.target.closest("#first-project")) projectModal();
    if (e.target.closest("#add-label")) labelModal();
    const pm = e.target.closest("[data-pmenu]");
    if (pm) { e.preventDefault(); projectMenu(pm, projectById(pm.dataset.pmenu)); }
  });
  document.addEventListener("keydown", onKey);
  document.addEventListener("themechange", paintThemeBtn);
  window.addEventListener("hashchange", router);

  try {
    await bootstrap();
  } catch (e) { toastError(e); return; }
  if (state.user?.theme && state.user.theme !== themePref()) applyTheme(state.user.theme);
  paintSidebar();
  onStore("bootstrap", paintSidebar);
  onStore("refresh", () => { current.view?.refresh?.(); reloadDrawer(); });
  if (!location.hash) history.replaceState(null, "", "#/today");
  router();
}

init();
