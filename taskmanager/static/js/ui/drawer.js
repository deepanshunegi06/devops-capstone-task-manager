// Task detail drawer with autosave, subtasks, comments and activity.
import { html, render, frag, $, debounce } from "./dom.js";
import { icon } from "./icons.js";
import { get, post, patch, del } from "../api.js";
import { state, changed, PRIORITY, STATUS, projectById } from "../store.js";
import { toast, toastError } from "./toast.js";
import { avatar, completeTask, deleteTask, fmtMin } from "./task-ui.js";
import { ago, relDay } from "../dates.js";

let current = null; // { el, id, close }

export function isDrawerOpen() { return !!current; }

export function closeDrawer({ fromRouter = false } = {}) {
  if (!current) return;
  const { el, onClose } = current;
  current = null;
  el.classList.remove("in");
  setTimeout(() => el.remove(), 240);
  document.body.classList.remove("drawer-open");
  if (!fromRouter) onClose?.();
}

export async function openDrawer(id, { onClose } = {}) {
  if (current && String(current.id) === String(id)) return;
  if (current) closeDrawer({ fromRouter: true });
  const el = frag(html`<div class="drawer-wrap">
      <div class="drawer-scrim"></div>
      <aside class="drawer" role="dialog" aria-modal="true" aria-label="Task details">
        <div class="drawer-loading"><i></i><i></i><i></i><i></i></div>
      </aside></div>`);
  document.getElementById("drawer-root").appendChild(el);
  document.body.classList.add("drawer-open");
  requestAnimationFrame(() => el.classList.add("in"));
  current = { el, id, onClose };
  el.querySelector(".drawer-scrim").addEventListener("click", () => closeDrawer());
  try {
    const { task } = await get(`/tasks/${id}`);
    if (!current || current.el !== el) return;
    paint(el.querySelector(".drawer"), task);
  } catch (e) {
    render(el.querySelector(".drawer"), html`<div class="drawer-error"><h3>Task not found</h3><p>${e.message}</p><button class="btn btn-ghost" data-x>Close</button></div>`);
    el.querySelector("[data-x]").addEventListener("click", () => closeDrawer());
  }
}

export async function reloadDrawer() {
  if (!current) return;
  const el = current.el;
  try {
    const { task } = await get(`/tasks/${current.id}`);
    if (current && current.el === el) paint(el.querySelector(".drawer"), task, { keepScroll: true });
  } catch { /* deleted elsewhere */ }
}

function paint(d, t, { keepScroll = false } = {}) {
  const scroll = d.querySelector(".drawer-body")?.scrollTop || 0;
  const project = t.project ? projectById(t.project.id) : null;
  const readOnly = project?.role === "viewer";
  const members = project?.members?.map((m) => m.user) || (state.user ? [state.user] : []);
  const labelIds = new Set((t.labels || []).map((l) => l.id));
  const subDone = (t.subtasks || []).filter((s) => s.done).length;
  const subTot = (t.subtasks || []).length;

  render(d, html`
    <header class="drawer-head">
      <div class="crumb">${t.project ? html`<span class="chip proj" data-c="${t.project.color}"><i class="dot"></i>${t.project.icon || ""} ${t.project.name}</span>` : html`<span class="chip proj">${icon("inbox", 13)}Inbox</span>`}
        <span class="saved" id="saved">${icon("check", 13)}Saved</span></div>
      <div class="drawer-tools">
        <button class="icon-btn" data-do="focus" title="Start focus" aria-label="Start focus session">${icon("focus", 18)}</button>
        <button class="icon-btn" data-do="pin" title="${t.pinned ? "Unpin" : "Pin"}" aria-label="Pin">${icon("pin", 18)}</button>
        <button class="icon-btn" data-do="dup" title="Duplicate" aria-label="Duplicate">${icon("copy", 18)}</button>
        ${readOnly ? "" : html`<button class="icon-btn danger" data-do="delete" title="Delete" aria-label="Delete">${icon("trash", 18)}</button>`}
        <button class="icon-btn" data-do="close" title="Close (Esc)" aria-label="Close">${icon("x", 18)}</button>
      </div>
    </header>
    <div class="drawer-body">
      <div class="title-row">
        <button class="check lg p${t.priority} ${t.status === "done" ? "is-done" : ""}" data-do="toggle" aria-label="Toggle complete">${icon("check", 15)}</button>
        <textarea class="title-input" rows="1" maxlength="200" ${readOnly ? "readonly" : ""} aria-label="Title">${t.title}</textarea>
      </div>
      <textarea class="desc-input" rows="3" placeholder="Add notes, links, acceptance criteria…" ${readOnly ? "readonly" : ""} aria-label="Description">${t.description || ""}</textarea>

      <div class="segmented" role="radiogroup" aria-label="Status">
        ${Object.entries(STATUS).map(([k, v]) => html`<button class="${t.status === k ? "on" : ""}" data-status="${k}" role="radio" aria-checked="${t.status === k}">${v}</button>`)}
      </div>

      <div class="props">
        <div class="prop"><span class="prop-k">${icon("flag", 15)}Priority</span>
          <div class="prio-pick">${[1, 2, 3, 4].map((p) => html`<button class="prio-btn ${t.priority === p ? "on" : ""}" data-prio="${p}" data-c="${PRIORITY[p].color}" title="${PRIORITY[p].name}">${PRIORITY[p].short}</button>`)}</div></div>
        <div class="prop"><span class="prop-k">${icon("today", 15)}Due</span>
          <div class="prop-v row"><input type="date" class="input sm" name="due_date" value="${t.due_date || ""}">
            <input type="time" class="input sm" name="due_time" value="${t.due_time || ""}">
            ${t.due_date ? html`<span class="muted small">${relDay(t.due_date)}</span>` : ""}</div></div>
        <div class="prop"><span class="prop-k">${icon("repeat", 15)}Repeat</span>
          <select class="select sm" name="recurrence">
            ${[["", "Does not repeat"], ["daily", "Every day"], ["weekdays", "Every weekday"], ["weekly", "Every week"], ["monthly", "Every month"], ["yearly", "Every year"]]
              .map(([v, l]) => html`<option value="${v}" ${(t.recurrence || "") === v ? "selected" : ""}>${l}</option>`)}
          </select></div>
        <div class="prop"><span class="prop-k">${icon("clock", 15)}Estimate</span>
          <select class="select sm" name="estimate_minutes">
            ${[["", "None"], [15, "15m"], [30, "30m"], [45, "45m"], [60, "1h"], [90, "1h 30m"], [120, "2h"], [180, "3h"], [240, "4h"], [480, "1 day"]]
              .map(([v, l]) => html`<option value="${v}" ${String(t.estimate_minutes || "") === String(v) ? "selected" : ""}>${l}</option>`)}
            ${t.estimate_minutes && ![15, 30, 45, 60, 90, 120, 180, 240, 480].includes(t.estimate_minutes) ? html`<option selected value="${t.estimate_minutes}">${fmtMin(t.estimate_minutes)}</option>` : ""}
          </select>${t.focus_minutes ? html`<span class="muted small">${fmtMin(t.focus_minutes)} focused</span>` : ""}</div>
        <div class="prop"><span class="prop-k">${icon("hash", 15)}Project</span>
          <select class="select sm" name="project_id">
            <option value="">📥 Inbox</option>
            ${state.projects.filter((p) => p.role !== "viewer" || p.id === t.project?.id).map((p) => html`<option value="${p.id}" ${t.project?.id === p.id ? "selected" : ""}>${p.icon || ""} ${p.name}</option>`)}
          </select></div>
        <div class="prop"><span class="prop-k">${icon("assigned", 15)}Assignee</span>
          <select class="select sm" name="assignee_id">
            <option value="">Unassigned</option>
            ${members.map((u) => html`<option value="${u.id}" ${t.assignee?.id === u.id ? "selected" : ""}>${u.display_name || u.username}${u.id === state.user?.id ? " (you)" : ""}</option>`)}
          </select></div>
        <div class="prop top"><span class="prop-k">${icon("tag", 15)}Labels</span>
          <div class="label-pick">
            ${state.labels.map((l) => html`<button class="pill toggle ${labelIds.has(l.id) ? "on" : ""}" data-label="${l.id}" data-c="${l.color}">@${l.name}</button>`)}
            <form class="new-label"><input placeholder="+ new label" maxlength="40" aria-label="New label"></form>
          </div></div>
      </div>

      <section class="d-sec">
        <header><h4>${icon("completed", 16)}Subtasks</h4><span class="muted small">${subDone}/${subTot}</span></header>
        ${subTot ? html`<div class="progress"><i data-w="${Math.round((subDone / subTot) * 100)}%"></i></div>` : ""}
        <ul class="subtasks">${(t.subtasks || []).map((s) => html`
          <li class="${s.done ? "done" : ""}" data-sub="${s.id}">
            <button class="check sm ${s.done ? "is-done" : ""}" data-subtoggle aria-label="Toggle subtask">${icon("check", 11)}</button>
            <span class="sub-title">${s.title}</span>
            <button class="icon-btn sm" data-subdel aria-label="Delete subtask">${icon("x", 14)}</button></li>`)}
        </ul>
        ${readOnly ? "" : html`<form class="add-sub"><span>${icon("plus", 15)}</span><input placeholder="Add a subtask and press Enter" maxlength="200" aria-label="Add subtask"></form>`}
      </section>

      <section class="d-sec">
        <header><h4>${icon("message", 16)}Comments</h4><span class="muted small">${(t.comments || []).length}</span></header>
        <ul class="comments">${(t.comments || []).map((c) => html`
          <li data-comment="${c.id}">${avatar(c.author, 28)}
            <div class="c-body"><div class="c-head"><b>${c.author?.display_name || c.author?.username}</b><span class="muted small">${ago(c.created_at)}</span>
              ${c.author?.id === state.user?.id ? html`<button class="link-btn small" data-cdel>Delete</button>` : ""}</div>
              <p>${c.body}</p></div></li>`)}
        </ul>
        <form class="add-comment">${avatar(state.user, 28)}<textarea rows="1" placeholder="Write a comment…" maxlength="2000" aria-label="Comment"></textarea>
          <button class="btn btn-primary sm">Send</button></form>
      </section>

      <section class="d-sec">
        <header><h4>${icon("activity", 16)}Activity</h4></header>
        <ol class="timeline">${(t.activity || []).slice(0, 25).map((a) => html`
          <li><span class="tl-dot"></span><div><b>${a.actor?.display_name || a.actor?.username || "Someone"}</b> ${actionText(a)}
            <span class="muted small">· ${ago(a.created_at)}</span></div></li>`)}
          ${(t.activity || []).length ? "" : html`<li class="muted small">No activity yet.</li>`}
        </ol>
        <p class="muted small created">Created ${ago(t.created_at)}${t.creator ? html` by ${t.creator.display_name || t.creator.username}` : ""} · Updated ${ago(t.updated_at)}</p>
      </section>
    </div>`);

  if (keepScroll) d.querySelector(".drawer-body").scrollTop = scroll;
  wire(d, t, readOnly);
  autoGrow(d.querySelector(".title-input"));
  autoGrow(d.querySelector(".desc-input"));
}

export function actionText(a) {
  const map = {
    created: "created this task", completed: "completed this task", reopened: "reopened this task",
    updated: "updated", commented: "commented", deleted: "deleted this task", restored: "restored this task",
    moved: "moved this task", assigned: "changed the assignee", subtask_added: "added a subtask",
    subtask_completed: "completed a subtask", duplicated: "duplicated this task", subtask: "updated subtasks", comment_deleted: "deleted a comment",
  };
  const base = map[a.action] || (a.action || "").replace(/_/g, " ");
  return a.detail && a.detail !== a.task?.title ? `${base}: ${a.detail}` : base;
}

function autoGrow(ta) {
  const fit = () => { ta.style.height = "auto"; ta.style.height = `${ta.scrollHeight}px`; };
  ta.addEventListener("input", fit);
  requestAnimationFrame(fit);
}

function wire(d, t, readOnly) {
  const savedEl = d.querySelector("#saved");
  let savedTimer;
  const flash = () => { savedEl.classList.add("show"); clearTimeout(savedTimer); savedTimer = setTimeout(() => savedEl.classList.remove("show"), 1400); };

  const save = async (fields, { repaint = false } = {}) => {
    if (readOnly) return;
    try {
      const res = await patch(`/tasks/${t.id}`, fields);
      Object.assign(t, res.task);
      flash();
      changed();
      if (repaint) paint(d, { ...t, ...res.task, subtasks: t.subtasks, comments: t.comments, activity: t.activity }, { keepScroll: true });
    } catch (e) { toastError(e); }
  };

  const title = d.querySelector(".title-input");
  const desc = d.querySelector(".desc-input");
  const saveTitle = debounce(() => { const v = title.value.trim(); if (v && v !== t.title) save({ title: v }); }, 600);
  const saveDesc = debounce(() => { if (desc.value !== (t.description || "")) save({ description: desc.value }); }, 700);
  title.addEventListener("input", saveTitle);
  title.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); title.blur(); } });
  title.addEventListener("blur", () => { saveTitle.cancel(); const v = title.value.trim(); if (!v) title.value = t.title; else if (v !== t.title) save({ title: v }); });
  desc.addEventListener("input", saveDesc);

  d.querySelectorAll(".segmented [data-status]").forEach((b) => b.addEventListener("click", () => {
    d.querySelectorAll(".segmented button").forEach((x) => { x.classList.toggle("on", x === b); x.setAttribute("aria-checked", x === b); });
    if (b.dataset.status === "done" && t.status !== "done") { completeTask(t, true).then(() => reloadDrawer()); }
    else if (t.status === "done" && b.dataset.status !== "done") { post(`/tasks/${t.id}/complete`, { done: false }).then(() => save({ status: b.dataset.status }, { repaint: true })); }
    else save({ status: b.dataset.status });
  }));

  d.querySelectorAll("[data-prio]").forEach((b) => b.addEventListener("click", () => {
    d.querySelectorAll("[data-prio]").forEach((x) => x.classList.toggle("on", x === b));
    const p = Number(b.dataset.prio);
    const chk = d.querySelector(".title-row .check");
    chk.className = chk.className.replace(/\bp\d\b/, `p${p}`);
    save({ priority: p });
  }));

  const field = (name, conv = (v) => v || null, opts) => d.querySelector(`[name=${name}]`).addEventListener("change", (e) => save({ [name]: conv(e.target.value) }, opts));
  field("due_date", undefined, { repaint: true });
  field("due_time");
  field("recurrence");
  field("estimate_minutes", (v) => (v ? Number(v) : null));
  field("project_id", (v) => (v ? Number(v) : null), { repaint: true });
  field("assignee_id", (v) => (v ? Number(v) : null));

  d.querySelector(".label-pick").addEventListener("click", (e) => {
    const b = e.target.closest("[data-label]");
    if (!b) return;
    b.classList.toggle("on");
    const ids = [...d.querySelectorAll("[data-label].on")].map((x) => Number(x.dataset.label));
    save({ label_ids: ids });
  });
  d.querySelector(".new-label").addEventListener("submit", async (e) => {
    e.preventDefault();
    const inp = e.target.querySelector("input");
    const name = inp.value.trim().replace(/^@/, "").replace(/\s+/g, "-");
    if (!name) return;
    try {
      const { label } = await post("/labels", { name });
      state.labels.push(label);
      await save({ label_ids: [...(t.labels || []).map((l) => l.id), label.id] });
      reloadDrawer();
    } catch (err) { toastError(err); }
  });

  d.querySelector(".drawer-tools").addEventListener("click", async (e) => {
    const b = e.target.closest("[data-do]");
    if (!b) return;
    const act = b.dataset.do;
    if (act === "close") closeDrawer();
    if (act === "focus") { closeDrawer({ fromRouter: true }); location.hash = `#/focus?task=${t.id}`; }
    if (act === "pin") { await save({ pinned: !t.pinned }); toast(t.pinned ? "Pinned to top" : "Unpinned", { timeout: 1500 }); }
    if (act === "dup") {
      try { const { task } = await post(`/tasks/${t.id}/duplicate`); changed(); toast("Duplicated", { type: "success", timeout: 2000 }); location.hash = `#/task/${task.id}`; }
      catch (err) { toastError(err); }
    }
    if (act === "delete") { closeDrawer(); deleteTask(t); }
  });
  d.querySelector("[data-do=toggle]").addEventListener("click", async () => {
    await completeTask(t, t.status !== "done");
    reloadDrawer();
  });

  // subtasks
  const subForm = d.querySelector(".add-sub");
  subForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const inp = subForm.querySelector("input");
    const title = inp.value.trim();
    if (!title) return;
    try { await post(`/tasks/${t.id}/subtasks`, { title }); inp.value = ""; await reloadDrawer(); d.querySelector(".add-sub input")?.focus(); changed(); }
    catch (err) { toastError(err); }
  });
  d.querySelector(".subtasks").addEventListener("click", async (e) => {
    const li = e.target.closest("[data-sub]");
    if (!li) return;
    const id = li.dataset.sub;
    try {
      if (e.target.closest("[data-subtoggle]")) {
        li.classList.toggle("done");
        await patch(`/subtasks/${id}`, { done: li.classList.contains("done") });
      } else if (e.target.closest("[data-subdel]")) {
        await del(`/subtasks/${id}`);
      } else return;
      await reloadDrawer(); changed();
    } catch (err) { toastError(err); }
  });
  d.querySelector(".subtasks").addEventListener("dblclick", async (e) => {
    const span = e.target.closest(".sub-title");
    if (!span || readOnly) return;
    const li = span.closest("[data-sub]");
    const v = window.prompt("Rename subtask", span.textContent);
    if (v && v.trim()) { await patch(`/subtasks/${li.dataset.sub}`, { title: v.trim() }).catch(toastError); reloadDrawer(); }
  });

  // comments
  const cf = d.querySelector(".add-comment");
  const cta = cf.querySelector("textarea");
  autoGrow(cta);
  cta.addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) cf.requestSubmit(); });
  cf.addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = cta.value.trim();
    if (!body) return;
    try { await post(`/tasks/${t.id}/comments`, { body }); cta.value = ""; await reloadDrawer(); changed(); }
    catch (err) { toastError(err); }
  });
  d.querySelector(".comments").addEventListener("click", async (e) => {
    if (!e.target.closest("[data-cdel]")) return;
    const li = e.target.closest("[data-comment]");
    try { await del(`/comments/${li.dataset.comment}`); await reloadDrawer(); changed(); } catch (err) { toastError(err); }
  });
}

export { $ };
