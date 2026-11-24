// Pomodoro focus timer. Timer state lives at module level so it keeps running across views.
import { html, render, $ } from "../ui/dom.js";
import { icon } from "../ui/icons.js";
import { get, post, qs } from "../api.js";
import { changed } from "../store.js";
import { toast, toastError } from "../ui/toast.js";

const PRESETS = { classic: { focus: 25, brk: 5, label: "25 / 5" }, deep: { focus: 50, brk: 10, label: "50 / 10" }, sprint: { focus: 15, brk: 3, label: "15 / 3" } };
const T = {
  preset: "classic", phase: "focus", remaining: 25 * 60, total: 25 * 60, running: false,
  taskId: "", interval: null, endAt: 0, sessions: 0, todayMinutes: null, view: null,
};
const baseTitle = "Focus · Orbit";

function tick() {
  T.remaining = Math.max(0, Math.round((T.endAt - Date.now()) / 1000));
  if (T.remaining <= 0) return finishPhase();
  document.title = `${fmt(T.remaining)} · ${T.phase === "focus" ? "Focus" : "Break"} · Orbit`;
  paintTimer();
}

async function finishPhase() {
  clearInterval(T.interval); T.interval = null; T.running = false;
  beep();
  if (T.phase === "focus") {
    const minutes = Math.round(T.total / 60);
    try {
      const body = { minutes };
      if (T.taskId) body.task_id = Number(T.taskId);
      const res = await post("/focus", body);
      T.todayMinutes = res.today_minutes ?? (T.todayMinutes || 0) + minutes;
      T.sessions += 1;
      toast(`Focus session complete: ${minutes} min logged 🎯`, { type: "success" });
      changed({ view: false });
    } catch (e) { toastError(e); }
    setPhase("break");
    notify("Focus session done", "Time for a short break.");
  } else {
    setPhase("focus");
    notify("Break over", "Ready for the next focus session?");
  }
  document.title = baseTitle;
  paintAll();
}

function setPhase(phase) {
  const p = PRESETS[T.preset];
  T.phase = phase;
  T.total = (phase === "focus" ? p.focus : p.brk) * 60;
  T.remaining = T.total;
}

function start() {
  if (T.running) return;
  T.running = true;
  T.endAt = Date.now() + T.remaining * 1000;
  T.interval = setInterval(tick, 250);
  if ("Notification" in window && Notification.permission === "default") Notification.requestPermission().catch(() => {});
  paintAll();
}
function pause() {
  if (!T.running) return;
  clearInterval(T.interval); T.interval = null; T.running = false;
  T.remaining = Math.max(0, Math.round((T.endAt - Date.now()) / 1000));
  document.title = baseTitle;
  paintAll();
}
function reset() { pause(); setPhase(T.phase); paintAll(); }

const fmt = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [0, 0.25, 0.5].forEach((t, i) => {
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.frequency.value = [660, 880, 990][i];
      g.gain.setValueAtTime(0.0001, ctx.currentTime + t);
      g.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + t + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + t + 0.22);
      o.connect(g).connect(ctx.destination); o.start(ctx.currentTime + t); o.stop(ctx.currentTime + t + 0.25);
    });
  } catch { /* audio not available */ }
}
function notify(title, body) {
  try { if ("Notification" in window && Notification.permission === "granted" && document.hidden) new Notification(title, { body, icon: "/static/img/orbit.svg" }); } catch { /* ignore */ }
}

const R = 130, C = 2 * Math.PI * R;
function paintTimer() {
  const v = T.view;
  if (!v || !document.body.contains(v)) return;
  v.querySelector(".ring-fg").setAttribute("stroke-dashoffset", String(C * (1 - (T.total - T.remaining) / T.total)));
  v.querySelector(".timer-time").textContent = fmt(T.remaining);
}

function paintAll() {
  const v = T.view;
  if (!v || !document.body.contains(v)) return;
  v.classList.toggle("is-break", T.phase === "break");
  v.classList.toggle("is-running", T.running);
  v.querySelector(".timer-phase").textContent = T.phase === "focus" ? "Focus" : "Break";
  const play = v.querySelector("[data-t=toggle]");
  render(play, html`${icon(T.running ? "pause" : "play", 22)}<span>${T.running ? "Pause" : T.remaining < T.total ? "Resume" : "Start"}</span>`);
  v.querySelectorAll("[data-preset]").forEach((b) => b.classList.toggle("on", b.dataset.preset === T.preset));
  v.querySelector("#today-min").textContent = T.todayMinutes == null ? "–" : `${T.todayMinutes} min`;
  v.querySelector("#sessions").textContent = T.sessions;
  paintTimer();
}

export async function renderFocus(ctx) {
  const { el } = ctx;
  if (ctx.query.task) T.taskId = ctx.query.task;
  render(el, html`<div class="page focus-page" id="focus">
    <div class="focus-card">
      <div class="presets segmented">${Object.entries(PRESETS).map(([k, p]) => html`<button data-preset="${k}">${p.label}</button>`)}</div>
      <div class="timer">
        <svg viewBox="0 0 300 300" class="timer-svg" aria-hidden="true">
          <defs><linearGradient id="tg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" class="tg1"/><stop offset="1" class="tg2"/></linearGradient></defs>
          <circle cx="150" cy="150" r="${R}" class="ring-bg"/>
          <circle cx="150" cy="150" r="${R}" class="ring-fg" stroke="url(#tg)" stroke-dasharray="${C}" stroke-dashoffset="${C}" transform="rotate(-90 150 150)"/>
        </svg>
        <div class="timer-center"><span class="timer-phase">Focus</span><span class="timer-time" role="timer" aria-live="off">25:00</span>
          <span class="timer-task" id="timer-task"></span></div>
      </div>
      <div class="timer-controls">
        <button class="icon-btn lg" data-t="reset" aria-label="Reset">${icon("reset", 20)}</button>
        <button class="btn btn-primary xl" data-t="toggle"></button>
        <button class="icon-btn lg" data-t="skip" aria-label="Skip phase">${icon("right", 20)}</button>
      </div>
      <label class="focus-task"><span>Working on</span>
        <select class="select" id="focus-task"><option value="">No specific task</option></select></label>
    </div>
    <aside class="focus-side">
      <div class="kpi k-pink"><div class="kpi-ic">${icon("focus", 18)}</div><div class="kpi-v" id="today-min">–</div><div class="kpi-l">Focused today</div></div>
      <div class="kpi k-violet"><div class="kpi-ic">${icon("target", 18)}</div><div class="kpi-v" id="sessions">0</div><div class="kpi-l">Sessions this visit</div></div>
      <div class="focus-tips"><h4>${icon("sparkles", 15)}How it works</h4>
        <ol><li>Pick a task (optional) and a rhythm.</li><li>Work until the ring completes. No switching!</li><li>Take the break. The session is logged to your analytics automatically.</li></ol>
        <p class="muted small">Tip: the countdown also shows in the browser tab, so you can switch windows.</p></div>
    </aside>
  </div>`);
  const v = $("#focus", el);
  T.view = v;
  v.addEventListener("click", (e) => {
    const p = e.target.closest("[data-preset]");
    if (p) { if (T.running && !confirm("Switching rhythm resets the current timer. Continue?")) return; pause(); T.preset = p.dataset.preset; setPhase("focus"); paintAll(); }
    const b = e.target.closest("[data-t]");
    if (!b) return;
    if (b.dataset.t === "toggle") T.running ? pause() : start();
    if (b.dataset.t === "reset") reset();
    if (b.dataset.t === "skip") { pause(); setPhase(T.phase === "focus" ? "break" : "focus"); paintAll(); }
  });
  const sel = $("#focus-task", el);
  sel.addEventListener("change", () => { T.taskId = sel.value; paintTaskName(sel); });
  paintAll();
  ctx.setSub(T.running ? "Timer running" : "Deep work, one session at a time");

  try {
    const [{ tasks }, an] = await Promise.all([get(`/tasks${qs({ view: "all" })}`), get("/analytics?days=7").catch(() => null)]);
    tasks.filter((t) => t.status !== "done").forEach((t) => {
      const o = document.createElement("option");
      o.value = t.id; o.textContent = `${t.title}${t.project ? ` · ${t.project.name}` : ""}`;
      sel.appendChild(o);
    });
    if (T.taskId && ![...sel.options].some((o) => o.value === String(T.taskId))) {
      try { const { task } = await get(`/tasks/${T.taskId}`); const o = document.createElement("option"); o.value = task.id; o.textContent = task.title; sel.appendChild(o); } catch { T.taskId = ""; }
    }
    sel.value = T.taskId || "";
    paintTaskName(sel);
    if (an && T.todayMinutes == null) {
      const last = (an.focus_per_day || []).slice(-1)[0];
      T.todayMinutes = last ? last.minutes : 0;
    }
    paintAll();
  } catch (e) { toastError(e); }
  return { refresh: () => {} };
}

function paintTaskName(sel) {
  const o = sel.selectedOptions[0];
  const el = document.getElementById("timer-task");
  if (el) el.textContent = sel.value && o ? o.textContent.split(" · ")[0] : "";
}

export const focusRunning = () => T.running;
