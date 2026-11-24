// Command palette (⌘K): navigation, actions and live search.
import { html, render, frag, debounce } from "./dom.js";
import { icon } from "./icons.js";
import { get, qs } from "../api.js";
import { state } from "../store.js";

let open = null;

function fuzzy(q, text) {
  q = q.toLowerCase(); text = text.toLowerCase();
  if (!q) return 1;
  const idx = text.indexOf(q);
  if (idx >= 0) return 100 - idx;
  let ti = 0, score = 0;
  for (const ch of q) {
    const f = text.indexOf(ch, ti);
    if (f < 0) return 0;
    score += f === ti ? 3 : 1;
    ti = f + 1;
  }
  return score;
}

export function closePalette() { if (open) { open(); open = null; } }
export const paletteOpen = () => !!open;

/** commands: [{ id, label, icon, hint, group, run }] */
export function openPalette(commands, { openTask }) {
  if (open) return;
  const el = frag(html`<div class="palette-backdrop"><div class="palette" role="dialog" aria-modal="true" aria-label="Command palette">
      <div class="pal-input">${icon("search", 18)}<input placeholder="Search tasks, projects, or type a command…" aria-label="Search" autocomplete="off"><kbd>esc</kbd></div>
      <div class="pal-list" role="listbox"></div>
      <footer class="pal-foot"><span><kbd>↑</kbd><kbd>↓</kbd> navigate</span><span><kbd>↵</kbd> select</span><span><kbd>esc</kbd> close</span></footer>
    </div></div>`);
  document.getElementById("palette-root").appendChild(el);
  requestAnimationFrame(() => el.classList.add("in"));
  const input = el.querySelector("input");
  const list = el.querySelector(".pal-list");
  let items = [], sel = 0, remote = { tasks: [], projects: [], labels: [] };

  const close = () => { el.classList.remove("in"); setTimeout(() => el.remove(), 150); };
  open = close;
  el.addEventListener("mousedown", (e) => { if (e.target === el) closePalette(); });

  function compute() {
    const q = input.value.trim();
    const cmds = commands.map((c) => ({ ...c, score: fuzzy(q, `${c.label} ${c.keywords || ""}`) })).filter((c) => c.score > 0)
      .sort((a, b) => b.score - a.score).slice(0, q ? 8 : 12);
    const out = [];
    if (q) {
      [...remote.tasks].sort((a, b) => (a.status === "done") - (b.status === "done")).forEach((t) => out.push({ group: "Tasks", label: t.title, icon: t.status === "done" ? "completed" : "list",
        hint: t.project ? t.project.name : "Inbox", color: t.project?.color, run: () => openTask(t.id), done: t.status === "done" }));
      const localP = state.projects.filter((p) => fuzzy(q, p.name) > 0).map((p) => p.id);
      const seen = new Set();
      [...remote.projects, ...state.projects.filter((p) => localP.includes(p.id))].forEach((p) => {
        if (seen.has(p.id)) return; seen.add(p.id);
        out.push({ group: "Projects", label: `${p.icon || ""} ${p.name}`, icon: "hash", color: p.color, run: () => { location.hash = `#/project/${p.id}`; } });
      });
      remote.labels.forEach((l) => out.push({ group: "Labels", label: `@${l.name}`, icon: "tag", color: l.color, run: () => { location.hash = `#/label/${l.id}`; } }));
    }
    const cmdItems = cmds.map((c) => ({ ...c, group: c.group || "Commands" }));
    const ql = q.toLowerCase();
    const cmdFirst = q && cmds.some((c) => c.label.toLowerCase().startsWith(ql) || c.label.toLowerCase().includes(` ${ql}`));
    if (cmdFirst) out.unshift(...cmdItems); else out.push(...cmdItems);
    items = out;
    sel = Math.min(sel, Math.max(0, items.length - 1));
    paint();
  }

  function paint() {
    if (!items.length) { render(list, html`<div class="pal-empty">${icon("search", 22)}<p>No results for “${input.value}”</p></div>`); return; }
    let g = null;
    render(list, html`${items.map((it, i) => {
      const head = it.group !== g ? html`<div class="pal-group">${it.group}</div>` : "";
      g = it.group;
      return html`${head}<button class="pal-item ${i === sel ? "sel" : ""} ${it.done ? "done" : ""}" data-i="${i}" role="option" aria-selected="${i === sel}">
        <span class="pal-ic" ${it.color ? html`data-c="${it.color}"` : ""}>${icon(it.icon || "arrow", 16)}</span>
        <span class="pal-label">${it.label}</span>${it.hint ? html`<span class="pal-hint">${it.hint}</span>` : ""}</button>`;
    })}`);
    list.querySelector(".pal-item.sel")?.scrollIntoView({ block: "nearest" });
  }

  const search = debounce(async () => {
    const q = input.value.trim();
    if (!q) { remote = { tasks: [], projects: [], labels: [] }; compute(); return; }
    try { remote = await get(`/search${qs({ q })}`); } catch { remote = { tasks: [], projects: [], labels: [] }; }
    compute();
  }, 140);

  const run = (i) => { const it = items[i]; if (!it) return; closePalette(); setTimeout(() => it.run?.(), 10); };
  input.addEventListener("input", () => { sel = 0; compute(); search(); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); sel = (sel + 1) % Math.max(items.length, 1); paint(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); sel = (sel - 1 + items.length) % Math.max(items.length, 1); paint(); }
    else if (e.key === "Enter") { e.preventDefault(); run(sel); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closePalette(); }
  });
  list.addEventListener("click", (e) => { const b = e.target.closest(".pal-item"); if (b) run(Number(b.dataset.i)); });
  list.addEventListener("mousemove", (e) => {
    const b = e.target.closest(".pal-item");
    if (b && Number(b.dataset.i) !== sel) { sel = Number(b.dataset.i); list.querySelectorAll(".pal-item").forEach((x) => x.classList.toggle("sel", x === b)); }
  });
  compute();
  setTimeout(() => input.focus(), 20);
}
