// Month calendar with drag-to-reschedule and click-to-add.
import { html, render, $ } from "../ui/dom.js";
import { icon } from "../ui/icons.js";
import { get, post, patch, qs } from "../api.js";
import { changed, state, PRIORITY } from "../store.js";
import { dropZones } from "../ui/dnd.js";
import { openModal } from "../ui/modal.js";
import { toast, toastError } from "../ui/toast.js";
import { iso, addDays, today, MONTHS_LONG, time12, dayHeader } from "../dates.js";
import { chipsFor } from "../quickadd.js";
import { debounce } from "../ui/dom.js";

let cursor = null; // first day of the visible month
let filterProject = "";

export async function renderCalendar(ctx) {
  const { el, openTask } = ctx;
  if (!cursor) { const t = today(); cursor = new Date(t.getFullYear(), t.getMonth(), 1); }
  if (ctx.query.project) filterProject = ctx.query.project;
  let tasks = [];

  render(el, html`<div class="page cal-page">
    <div class="cal-toolbar">
      <div class="cal-nav">
        <button class="icon-btn" data-nav="-1" aria-label="Previous month">${icon("left", 18)}</button>
        <h2 id="cal-title"></h2>
        <button class="icon-btn" data-nav="1" aria-label="Next month">${icon("right", 18)}</button>
        <button class="btn btn-ghost sm" data-nav="0">Today</button>
      </div>
      <select class="select sm" id="cal-proj" aria-label="Filter by project">
        <option value="">All projects</option>
        ${state.projects.map((p) => html`<option value="${p.id}" ${String(p.id) === String(filterProject) ? "selected" : ""}>${p.icon || ""} ${p.name}</option>`)}
      </select>
    </div>
    <div class="cal-grid-head">${["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => html`<div>${d}</div>`)}</div>
    <div class="cal-grid" id="cal-grid"></div>
    <p class="cal-tip">${icon("sparkles", 14)} Drag a task onto another day to reschedule. Click an empty spot to add a task.</p>
  </div>`);

  const grid = $("#cal-grid", el);
  el.querySelectorAll("[data-nav]").forEach((b) => b.addEventListener("click", () => {
    const n = Number(b.dataset.nav);
    if (n === 0) { const t = today(); cursor = new Date(t.getFullYear(), t.getMonth(), 1); }
    else cursor = new Date(cursor.getFullYear(), cursor.getMonth() + n, 1);
    paint();
  }));
  $("#cal-proj", el).addEventListener("change", (e) => { filterProject = e.target.value; load(); });

  dropZones(grid, {
    item: ".cal-chip", zone: ".cal-day",
    onDrop: async ({ id, zone }) => {
      const t = tasks.find((x) => x.id === id);
      if (!t || t.due_date === zone.dataset.date) return;
      t.due_date = zone.dataset.date; paint();
      try { await patch(`/tasks/${id}`, { due_date: zone.dataset.date }); toast(`Moved to ${dayHeader(zone.dataset.date).sub}`, { type: "success", timeout: 1800 }); changed({ view: false }); }
      catch (e) { toastError(e); load(); }
    },
  });

  grid.addEventListener("click", (e) => {
    const chip = e.target.closest(".cal-chip");
    if (chip) { openTask(chip.dataset.id); return; }
    if (e.target.closest(".cal-more")) {
      const day = e.target.closest(".cal-day");
      day.classList.add("expanded");
      return;
    }
    const day = e.target.closest(".cal-day");
    if (day) addOnDay(day.dataset.date);
  });

  function addOnDay(date) {
    openModal({
      title: `New task · ${dayHeader(date).name}, ${dayHeader(date).sub}`,
      body: html`<form class="form"><input class="input" name="text" placeholder="What needs doing? (#project @label p1 5pm…)" maxlength="300">
        <div class="qa-preview modal-preview"></div>
        <div class="modal-actions"><button type="button" class="btn btn-ghost" data-cancel>Cancel</button><button class="btn btn-primary">Add task</button></div></form>`,
      onMount(m, close) {
        const f = m.querySelector("form");
        const prev = m.querySelector(".qa-preview");
        m.querySelector("[data-cancel]").addEventListener("click", close);
        const parse = debounce(async () => {
          const text = f.text.value.trim();
          if (!text) { render(prev, ""); return; }
          try { const { parsed } = await post("/tasks/parse", { text }); render(prev, html`${chipsFor(parsed)}`); } catch { /* ignore */ }
        }, 200);
        f.text.addEventListener("input", parse);
        f.addEventListener("submit", async (e) => {
          e.preventDefault();
          const text = f.text.value.trim();
          if (!text) return;
          try {
            const body = { text };
            if (filterProject) body.project_id = Number(filterProject);
            const res = await post("/tasks/quick", body);
            if (!res.task.due_date) await patch(`/tasks/${res.task.id}`, { due_date: date });
            close(); changed();
          } catch (err) { toastError(err); }
        });
      },
    });
  }

  async function load() {
    try {
      tasks = (await get(`/tasks${qs({ view: "all", include_done: 1, project_id: filterProject })}`)).tasks || [];
      paint();
    } catch (e) { toastError(e); }
  }

  function paint() {
    $("#cal-title", el).textContent = `${MONTHS_LONG[cursor.getMonth()]} ${cursor.getFullYear()}`;
    ctx.setSub(`${tasks.filter((t) => t.due_date && t.status !== "done").length} scheduled`);
    const start = addDays(cursor, -((cursor.getDay() + 6) % 7));
    const tISO = iso(today());
    const byDate = new Map();
    tasks.forEach((t) => { if (t.due_date) { if (!byDate.has(t.due_date)) byDate.set(t.due_date, []); byDate.get(t.due_date).push(t); } });
    const cells = [];
    for (let i = 0; i < 42; i++) {
      const d = addDays(start, i);
      const ds = iso(d);
      const list = (byDate.get(ds) || []).sort((a, b) => (a.status === "done") - (b.status === "done") || (a.due_time || "99").localeCompare(b.due_time || "99") || a.priority - b.priority);
      const out = d.getMonth() !== cursor.getMonth();
      cells.push(html`<div class="cal-day ${out ? "out" : ""} ${ds === tISO ? "is-today" : ""} ${ds < tISO ? "past" : ""}" data-date="${ds}">
        <div class="cal-date"><span>${d.getDate()}</span>${list.length ? html`<em>${list.length}</em>` : ""}</div>
        <div class="cal-chips">
          ${list.map((t, idx) => html`<button class="cal-chip ${t.status === "done" ? "done" : ""} ${idx >= 3 ? "extra" : ""}" draggable="true" data-id="${t.id}"
              data-c="${t.project?.color || PRIORITY[t.priority || 4].color}" title="${t.title}">
              <i class="pdot p${t.priority || 4}"></i>${t.due_time ? html`<b>${time12(t.due_time)}</b>` : ""}<span>${t.title}</span></button>`)}
          ${list.length > 3 ? html`<button class="cal-more">+${list.length - 3} more</button>` : ""}
        </div>
      </div>`);
    }
    render(grid, html`${cells}`);
  }

  await load();
  return { refresh: load };
}
