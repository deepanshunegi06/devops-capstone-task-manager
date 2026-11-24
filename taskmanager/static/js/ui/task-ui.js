// Shared task rendering (rows, cards, chips) and task actions with undo.
import { html, raw } from "./dom.js";
import { icon } from "./icons.js";
import { post, patch, del } from "../api.js";
import { toast, toastError } from "./toast.js";
import { openMenu } from "./menu.js";
import { PRIORITY, changed } from "../store.js";
import { relDay, time12, parse, today, diffDays, iso, addDays, todayISO } from "../dates.js";

export function avatar(user, size = 24, cls = "") {
  if (!user) return "";
  const name = user.display_name || user.username || "?";
  const initials = user.initials || name.split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();
  return html`<span class="avatar s${size} ${cls}" data-c="${user.avatar_color || "#6d5cff"}" title="${name}">${initials}</span>`;
}

export function dueChip(t) {
  if (!t.due_date) return "";
  const n = diffDays(parse(t.due_date), today());
  const cls = t.status === "done" ? "" : n < 0 ? "due-overdue" : n === 0 ? "due-today" : n === 1 ? "due-soon" : "";
  return html`<span class="chip due ${cls}">${icon("today", 13)}${relDay(t.due_date, { overdueStyle: t.status !== "done" })}${t.due_time ? html` · ${time12(t.due_time)}` : ""}</span>`;
}

export function labelPills(labels = []) {
  return labels.map((l) => html`<span class="pill" data-c="${l.color || "#64748b"}">@${l.name}</span>`);
}

export function projectChip(p) {
  if (!p) return html`<span class="chip proj">${icon("inbox", 13)}Inbox</span>`;
  return html`<span class="chip proj" data-c="${p.color}"><i class="dot"></i>${p.icon ? html`<span class="pi">${p.icon}</span>` : ""}${p.name}</span>`;
}

export function taskMeta(t, { showProject = true } = {}) {
  const parts = [
    dueChip(t),
    t.recurrence ? html`<span class="chip" title="Repeats ${t.recurrence}">${icon("repeat", 13)}${t.recurrence}</span>` : "",
    t.estimate_minutes ? html`<span class="chip">${icon("clock", 13)}${fmtMin(t.estimate_minutes)}</span>` : "",
    t.subtasks_total ? html`<span class="chip ${t.subtasks_done === t.subtasks_total ? "chip-ok" : ""}">${icon("completed", 13)}${t.subtasks_done}/${t.subtasks_total}</span>` : "",
    t.comments_count ? html`<span class="chip">${icon("message", 13)}${t.comments_count}</span>` : "",
    t.focus_minutes ? html`<span class="chip">${icon("focus", 13)}${fmtMin(t.focus_minutes)}</span>` : "",
    labelPills(t.labels),
  ];
  return html`<div class="meta">${parts}${showProject ? projectChip(t.project) : ""}</div>`;
}

export const fmtMin = (m) => (m >= 60 ? `${Math.floor(m / 60)}h${m % 60 ? ` ${m % 60}m` : ""}` : `${m}m`);

export function checkbox(t) {
  return html`<button class="check p${t.priority || 4} ${t.status === "done" ? "is-done" : ""}" data-act="toggle"
      aria-label="${t.status === "done" ? "Mark as not done" : "Complete task"}" aria-pressed="${t.status === "done"}">${icon("check", 13)}</button>`;
}

export function taskRow(t, { showProject = true, draggable = true } = {}) {
  const desc = (t.description || "").replace(/\s+/g, " ").trim();
  return html`
  <li class="task-row ${t.status === "done" ? "done" : ""}" data-id="${t.id}" ${draggable ? "draggable=true" : ""}>
    ${draggable ? html`<span class="grip" aria-hidden="true">${icon("grip", 14)}</span>` : ""}
    ${checkbox(t)}
    <div class="task-main" data-act="open" tabindex="0" role="button" aria-label="Open ${t.title}">
      <div class="task-title">${t.pinned ? html`<span class="pin">${icon("pin", 13)}</span>` : ""}${t.status === "in_progress" ? html`<span class="status-dot" title="In progress"></span>` : ""}${t.title}</div>
      ${desc ? html`<div class="task-desc">${desc.slice(0, 140)}</div>` : ""}
      ${taskMeta(t, { showProject })}
    </div>
    <div class="task-side">
      ${t.assignee ? avatar(t.assignee, 22) : ""}
      <div class="row-actions">
        <button class="icon-btn sm" data-act="schedule" aria-label="Schedule" title="Schedule">${icon("today", 16)}</button>
        <button class="icon-btn sm" data-act="priority" aria-label="Priority" title="Priority">${icon("flag", 16)}</button>
        <button class="icon-btn sm" data-act="more" aria-label="More actions" title="More">${icon("dots", 16)}</button>
      </div>
    </div>
  </li>`;
}

export function taskCard(t) {
  const pct = t.subtasks_total ? Math.round((t.subtasks_done / t.subtasks_total) * 100) : 0;
  return html`
  <article class="card p${t.priority || 4} ${t.status === "done" ? "done" : ""}" data-id="${t.id}" draggable="true" tabindex="0">
    <div class="card-top">
      ${checkbox(t)}
      <div class="card-title" data-act="open">${t.title}</div>
    </div>
    ${(t.labels || []).length ? html`<div class="card-labels">${labelPills(t.labels)}</div>` : ""}
    ${t.subtasks_total ? html`<div class="progress"><i data-w="${pct}%"></i></div>` : ""}
    <div class="card-foot">
      ${dueChip(t)}
      ${t.subtasks_total ? html`<span class="chip">${t.subtasks_done}/${t.subtasks_total}</span>` : ""}
      ${t.comments_count ? html`<span class="chip">${icon("message", 13)}${t.comments_count}</span>` : ""}
      <span class="spacer"></span>
      ${t.project ? html`<span class="mini-proj" data-c="${t.project.color}" title="${t.project.name}">${t.project.icon || ""}</span>` : ""}
      ${t.assignee ? avatar(t.assignee, 22) : ""}
    </div>
  </article>`;
}

/* ---------------- actions ---------------- */

export async function completeTask(t, done = true, el) {
  try {
    if (el && done) { el.classList.add("completing"); await wait(380); }
    const res = await post(`/tasks/${t.id}/complete`, { done });
    if (done) {
      const next = res.next_task;
      toast(next ? `Completed. Next one due ${relDay(next.due_date)}` : "Task completed 🎉", {
        type: "success", action: "Undo",
        onAction: async () => {
          await post(`/tasks/${t.id}/complete`, { done: false });
          if (next) await del(`/tasks/${next.id}`).catch(() => {});
          changed();
        },
      });
    }
    changed();
    return res;
  } catch (e) { el?.classList.remove("completing"); toastError(e); }
}

export async function deleteTask(t) {
  try {
    await del(`/tasks/${t.id}`);
    toast(`Deleted “${t.title}”`, {
      action: "Undo",
      onAction: async () => { await post(`/tasks/${t.id}/restore`); changed(); toast("Restored", { type: "success", timeout: 2000 }); },
    });
    changed();
  } catch (e) { toastError(e); }
}

export async function updateTask(id, fields, { quiet = true } = {}) {
  try {
    const res = await patch(`/tasks/${id}`, fields);
    if (!quiet) toast("Saved", { type: "success", timeout: 1500 });
    changed();
    return res.task;
  } catch (e) { toastError(e); return null; }
}

export function priorityMenu(anchor, t) {
  openMenu(anchor, [1, 2, 3, 4].map((p) => ({
    label: `${PRIORITY[p].short} · ${PRIORITY[p].name}`, color: PRIORITY[p].color, checked: t.priority === p,
    onClick: () => updateTask(t.id, { priority: p }),
  })));
}

export function scheduleMenu(anchor, t) {
  const d = today();
  const nextMon = addDays(d, ((8 - d.getDay()) % 7) || 7);
  openMenu(anchor, [
    { label: "Today", icon: "today", hint: relDayShort(d), onClick: () => updateTask(t.id, { due_date: todayISO() }) },
    { label: "Tomorrow", icon: "sun", hint: relDayShort(addDays(d, 1)), onClick: () => updateTask(t.id, { due_date: iso(addDays(d, 1)) }) },
    { label: "Next week", icon: "upcoming", hint: relDayShort(nextMon), onClick: () => updateTask(t.id, { due_date: iso(nextMon) }) },
    { label: "In 2 weeks", icon: "calendar", hint: relDayShort(addDays(d, 14)), onClick: () => updateTask(t.id, { due_date: iso(addDays(d, 14)) }) },
    { sep: true },
    { label: "No date", icon: "x", onClick: () => updateTask(t.id, { due_date: null, due_time: null }) },
  ]);
}
const relDayShort = (d) => ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][d.getDay()];

export function moreMenu(anchor, t, { openTask }) {
  openMenu(anchor, [
    { label: "Open details", icon: "edit", onClick: () => openTask(t.id) },
    { label: t.pinned ? "Unpin" : "Pin to top", icon: "pin", onClick: () => updateTask(t.id, { pinned: !t.pinned }) },
    { label: t.status === "in_progress" ? "Move to To do" : "Start (In progress)", icon: "play",
      onClick: () => updateTask(t.id, { status: t.status === "in_progress" ? "todo" : "in_progress" }) },
    { label: "Start focus session", icon: "focus", onClick: () => { location.hash = `#/focus?task=${t.id}`; } },
    { label: "Duplicate", icon: "copy", onClick: async () => { try { await post(`/tasks/${t.id}/duplicate`); toast("Duplicated", { type: "success", timeout: 2000 }); changed(); } catch (e) { toastError(e); } } },
    { sep: true },
    { label: "Delete", icon: "trash", danger: true, onClick: () => deleteTask(t) },
  ], { align: "right" });
}

/** Wire click/keyboard handlers for rows & cards inside root. getTask(id) returns the task object. */
export function bindTaskEvents(root, getTask, { openTask }) {
  root.addEventListener("click", (e) => {
    const actEl = e.target.closest("[data-act]");
    const holder = e.target.closest("[data-id]");
    if (!holder || !root.contains(holder)) return;
    const t = getTask(holder.dataset.id);
    if (!t) return;
    const act = actEl?.dataset.act;
    if (act === "toggle") { e.stopPropagation(); completeTask(t, t.status !== "done", t.status !== "done" ? holder : null); }
    else if (act === "priority") { e.stopPropagation(); priorityMenu(actEl, t); }
    else if (act === "schedule") { e.stopPropagation(); scheduleMenu(actEl, t); }
    else if (act === "more") { e.stopPropagation(); moreMenu(actEl, t, { openTask }); }
    else if (act === "open" || holder.classList.contains("card")) { openTask(t.id); }
  });
  root.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    const holder = e.target.closest("[data-id]");
    if (holder && (e.target.dataset.act === "open" || e.target.classList.contains("card"))) openTask(holder.dataset.id);
  });
}

export const wait = (ms) => new Promise((r) => setTimeout(r, ms));

export function sortTasks(list) {
  return [...list].sort((a, b) =>
    (b.pinned - a.pinned) || ((a.position ?? 0) - (b.position ?? 0)) || (a.priority - b.priority) || (a.id - b.id));
}

export function emptyState(title, text, art = "calm") {
  const arts = {
    calm: `<svg viewBox="0 0 200 140" class="empty-art" aria-hidden="true">
      <defs><linearGradient id="eg" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stop-color="#a99fff"/><stop offset="1" stop-color="#6d5cff"/></linearGradient></defs>
      <ellipse cx="100" cy="122" rx="62" ry="8" class="ea-shadow"/>
      <circle cx="100" cy="64" r="40" fill="url(#eg)" opacity=".18"/>
      <ellipse cx="100" cy="64" rx="70" ry="22" fill="none" stroke="url(#eg)" stroke-width="3" transform="rotate(-18 100 64)" opacity=".7"/>
      <circle cx="100" cy="64" r="24" fill="url(#eg)"/>
      <path d="M89 65l8 8 15-16" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
      <circle cx="160" cy="40" r="6" fill="#ffb4d9"/><circle cx="38" cy="86" r="4" fill="#8be0c4"/><circle cx="150" cy="100" r="3" fill="#ffd27a"/></svg>`,
    search: `<svg viewBox="0 0 200 140" class="empty-art" aria-hidden="true"><ellipse cx="100" cy="122" rx="56" ry="7" class="ea-shadow"/>
      <circle cx="90" cy="62" r="32" fill="none" stroke="#a99fff" stroke-width="8"/><path d="M114 86l26 26" stroke="#6d5cff" stroke-width="10" stroke-linecap="round"/>
      <circle cx="90" cy="62" r="20" fill="#a99fff" opacity=".2"/></svg>`,
  };
  return html`<div class="empty">${arts[art] ? rawSvg(arts[art]) : ""}<h3>${title}</h3><p>${text}</p></div>`;
}
const rawSvg = (s) => raw(s);
