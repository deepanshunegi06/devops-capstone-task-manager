// Natural-language quick add with live parsing preview chips.
import { html, render, debounce } from "./ui/dom.js";
import { icon } from "./ui/icons.js";
import { post, patch } from "./api.js";
import { toast, toastError } from "./ui/toast.js";
import { changed, PRIORITY } from "./store.js";
import { relDay, time12 } from "./dates.js";
import { fmtMin, avatar } from "./ui/task-ui.js";

const HINTS = [
  "Pay rent every month p1 #Home",
  "Demo prep tomorrow 5pm #Capstone @video ~45m",
  "Standup weekdays 9:30am @work",
  "Read chapter 4 friday p3 @study",
  "Review PR in 2 days +alice",
];

export function chipsFor(p) {
  if (!p) return "";
  const chips = [];
  if (p.project) chips.push(html`<span class="qa-chip c-proj" data-c="${p.project.color}">${p.project.icon || "#"} ${p.project.name}</span>`);
  (p.labels || []).forEach((l) => chips.push(html`<span class="qa-chip c-label">@${l.name || l}</span>`));
  if (p.priority && p.priority !== 4) chips.push(html`<span class="qa-chip c-prio" data-c="${PRIORITY[p.priority].color}">${icon("flag", 12)}${PRIORITY[p.priority].short}</span>`);
  if (p.due_date) chips.push(html`<span class="qa-chip c-date">${icon("today", 12)}${relDay(p.due_date)}</span>`);
  if (p.due_time) chips.push(html`<span class="qa-chip c-date">${icon("clock", 12)}${time12(p.due_time)}</span>`);
  if (p.recurrence) chips.push(html`<span class="qa-chip c-rec">${icon("repeat", 12)}${p.recurrence}</span>`);
  if (p.estimate_minutes) chips.push(html`<span class="qa-chip c-est">~${fmtMin(p.estimate_minutes)}</span>`);
  if (p.assignee) chips.push(html`<span class="qa-chip c-user">${avatar(p.assignee, 16)}${p.assignee.display_name || p.assignee.username}</span>`);
  return chips;
}

/**
 * mountQuickAdd(el, { projectId, defaultDate, defaultStatus, placeholder, onCreated, compact })
 */
export function mountQuickAdd(el, opts = {}) {
  const hint = HINTS[Math.floor(Math.random() * HINTS.length)];
  render(el, html`
    <form class="quickadd ${opts.compact ? "compact" : ""}" autocomplete="off">
      <span class="qa-plus">${icon("plus", 18)}</span>
      <input class="qa-input" name="q" placeholder="${opts.placeholder || `Add a task… e.g. “${hint}”`}" aria-label="Quick add task" maxlength="300">
      <button class="qa-submit btn btn-primary sm" type="submit" disabled>Add</button>
      <div class="qa-preview" aria-live="polite"></div>
    </form>
    ${opts.compact ? "" : html`<div class="qa-help">${icon("bolt", 13)}<span><b>#</b>project <b>@</b>label <b>p1–p4</b> priority <b>tomorrow 5pm</b> date <b>every week</b> repeat <b>~30m</b> estimate <b>+user</b> assign</span><kbd>Q</kbd></div>`}`);
  const form = el.querySelector("form");
  const input = el.querySelector(".qa-input");
  const btn = el.querySelector(".qa-submit");
  const preview = el.querySelector(".qa-preview");
  let seq = 0;

  const doParse = debounce(async () => {
    const text = input.value.trim();
    if (!text) { render(preview, ""); form.classList.remove("has-preview"); return; }
    const my = ++seq;
    try {
      const { parsed } = await post("/tasks/parse", { text });
      if (my !== seq) return;
      const chips = chipsFor(parsed);
      render(preview, chips.length ? html`<span class="qa-title">${icon("sparkles", 13)}${parsed.title || "…"}</span>${chips}` : "");
      form.classList.toggle("has-preview", chips.length > 0);
    } catch { /* preview is best-effort */ }
  }, 180);

  input.addEventListener("input", () => { btn.disabled = !input.value.trim(); doParse(); });
  input.addEventListener("keydown", (e) => { if (e.key === "Escape") { input.value = ""; render(preview, ""); form.classList.remove("has-preview"); input.blur(); } });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    btn.disabled = true;
    try {
      const body = { text };
      if (opts.projectId) body.project_id = Number(opts.projectId);
      const res = await post("/tasks/quick", body);
      let task = res.task;
      const extra = {};
      if (opts.defaultDate && !task.due_date) extra.due_date = opts.defaultDate;
      if (opts.defaultStatus && opts.defaultStatus !== task.status) extra.status = opts.defaultStatus;
      if (opts.labelId && !(task.labels || []).some((l) => String(l.id) === String(opts.labelId))) {
        extra.label_ids = [...(task.labels || []).map((l) => l.id), Number(opts.labelId)];
      }
      if (Object.keys(extra).length) task = (await patch(`/tasks/${task.id}`, extra)).task;
      input.value = "";
      render(preview, "");
      form.classList.remove("has-preview");
      toast(html`Added <b>${task.title}</b>${task.due_date ? html` · ${relDay(task.due_date)}` : ""}`, { type: "success", timeout: 2500 });
      opts.onCreated?.(task);
      changed();
    } catch (err) { toastError(err); }
    finally { btn.disabled = !input.value.trim(); input.focus(); }
  });
  if (opts.autofocus) setTimeout(() => input.focus(), 30);
  return { focus: () => input.focus(), input };
}
