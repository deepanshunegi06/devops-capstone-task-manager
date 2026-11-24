// Eisenhower matrix: urgency (due soon) x importance (priority).
import { html, render, $ } from "../ui/dom.js";
import { icon } from "../ui/icons.js";
import { get, patch, qs } from "../api.js";
import { changed, state } from "../store.js";
import { dropZones } from "../ui/dnd.js";
import { toast, toastError } from "../ui/toast.js";
import { checkbox, dueChip, labelPills, bindTaskEvents, sortTasks, avatar } from "../ui/task-ui.js";
import { parse, today, diffDays, iso, addDays, todayISO } from "../dates.js";

const Q = [
  { key: "do", title: "Do first", sub: "Urgent & important", ic: "bolt", tone: "q-do" },
  { key: "schedule", title: "Schedule", sub: "Important, not urgent", ic: "calendar", tone: "q-schedule" },
  { key: "delegate", title: "Delegate", sub: "Urgent, less important", ic: "users", tone: "q-delegate" },
  { key: "eliminate", title: "Eliminate", sub: "Neither. Drop or defer", ic: "trash", tone: "q-elim" },
];

const urgent = (t) => t.due_date && diffDays(parse(t.due_date), today()) <= 2;
const important = (t) => (t.priority || 4) <= 2;
export const quadrant = (t) => important(t) ? (urgent(t) ? "do" : "schedule") : (urgent(t) ? "delegate" : "eliminate");

let filterProject = "";

export async function renderMatrix(ctx) {
  const { el, openTask } = ctx;
  let tasks = [];
  const byId = (id) => tasks.find((t) => String(t.id) === String(id));
  render(el, html`<div class="page matrix-page">
    <div class="cal-toolbar">
      <p class="muted matrix-intro">Sort open tasks by <b>urgency</b> (due within 2 days) and <b>importance</b> (P1–P2). Drag between quadrants to re-prioritise.</p>
      <select class="select sm" id="mx-proj" aria-label="Filter by project"><option value="">All projects</option>
        ${state.projects.map((p) => html`<option value="${p.id}" ${String(p.id) === String(filterProject) ? "selected" : ""}>${p.icon || ""} ${p.name}</option>`)}</select>
    </div>
    <div class="matrix" id="matrix">
      <div class="axis axis-top"><span>Urgent</span><span>Not urgent</span></div>
      ${[Q[0], Q[1], Q[2], Q[3]].map((q) => html`<section class="quad ${q.tone}" data-q="${q.key}">
        <header><span class="q-ic">${icon(q.ic, 16)}</span><div><h3>${q.title}</h3><small>${q.sub}</small></div><span class="count" data-qc="${q.key}">0</span></header>
        <ul class="quad-list" data-q="${q.key}"></ul></section>`)}
    </div></div>`);
  const mx = $("#matrix", el);
  // Layout order: Do (urgent+important) | Schedule (important) / Delegate (urgent) | Eliminate
  bindTaskEvents(mx, byId, { openTask });
  $("#mx-proj", el).addEventListener("change", (e) => { filterProject = e.target.value; load(); });

  dropZones(mx, {
    item: ".mx-item", zone: ".quad",
    onDrop: async ({ id, zone }) => {
      const t = byId(id);
      const target = zone.dataset.q;
      if (!t || quadrant(t) === target) return;
      const f = {};
      const isUrgent = urgent(t);
      if (target === "do") { if (!important(t)) f.priority = 1; if (!isUrgent) f.due_date = todayISO(); }
      if (target === "schedule") { if (!important(t)) f.priority = 2; if (isUrgent) f.due_date = iso(addDays(today(), 7)); }
      if (target === "delegate") { if (important(t)) f.priority = 3; if (!isUrgent) f.due_date = iso(addDays(today(), 1)); }
      if (target === "eliminate") { if (important(t)) f.priority = 4; if (isUrgent) f.due_date = null; }
      Object.assign(t, f); paint();
      try { await patch(`/tasks/${id}`, f); toast(`Moved to “${Q.find((q) => q.key === target).title}”`, { type: "success", timeout: 1800 }); changed({ view: false }); }
      catch (e) { toastError(e); load(); }
    },
  });

  async function load() {
    try { tasks = (await get(`/tasks${qs({ view: "all", project_id: filterProject })}`)).tasks || []; paint(); }
    catch (e) { toastError(e); }
  }

  function paint() {
    const open = tasks.filter((t) => t.status !== "done");
    ctx.setSub(`${open.length} open tasks`);
    Q.forEach((q) => {
      const list = sortTasks(open.filter((t) => quadrant(t) === q.key));
      mx.querySelector(`[data-qc="${q.key}"]`).textContent = list.length;
      render(mx.querySelector(`.quad-list[data-q="${q.key}"]`), list.length ? html`${list.map((t) => html`
        <li class="mx-item" draggable="true" data-id="${t.id}">
          ${checkbox(t)}
          <div class="mx-main" data-act="open"><span class="mx-title">${t.title}</span>
            <div class="meta">${dueChip(t)}${labelPills(t.labels)}${t.project ? html`<span class="chip proj" data-c="${t.project.color}"><i class="dot"></i>${t.project.name}</span>` : ""}</div></div>
          ${t.assignee ? avatar(t.assignee, 20) : ""}
        </li>`)}` : html`<li class="quad-empty">Nothing here</li>`);
    });
  }

  await load();
  return { refresh: load };
}
