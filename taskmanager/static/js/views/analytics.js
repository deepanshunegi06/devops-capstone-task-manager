// Productivity analytics dashboard with hand-made SVG charts.
import { html, render, raw, $ } from "../ui/dom.js";
import { icon } from "../ui/icons.js";
import { get } from "../api.js";
import { PRIORITY } from "../store.js";
import { parse, MONTHS, WD } from "../dates.js";
import { toastError } from "../ui/toast.js";

let days = 30;

export async function renderAnalytics(ctx) {
  const { el } = ctx;
  render(el, html`<div class="page analytics">
    <div class="an-head">
      <p class="muted">How your work is flowing. Everything here is computed live from your tasks and focus sessions.</p>
      <div class="segmented sm" id="range">${[7, 30, 90].map((d) => html`<button data-days="${d}" class="${d === days ? "on" : ""}">${d} days</button>`)}</div>
    </div>
    <div id="an-body"><div class="kpis">${Array.from({ length: 6 }, () => html`<div class="kpi sk"></div>`)}</div><div class="panel sk tall"></div></div>
  </div>`);
  $("#range", el).addEventListener("click", (e) => {
    const b = e.target.closest("[data-days]");
    if (!b) return;
    days = Number(b.dataset.days);
    el.querySelectorAll("#range button").forEach((x) => x.classList.toggle("on", x === b));
    load();
  });

  async function load() {
    try {
      const a = await get(`/analytics?days=${days}`);
      paint(a);
    } catch (e) { toastError(e); }
  }

  function paint(a) {
    const T = a.totals || {};
    const body = $("#an-body", el);
    const onTime = a.on_time_rate == null ? "–" : `${Math.round(a.on_time_rate * 100)}%`;
    const totalDone = sum(a.completed_per_day.map((d) => d.count));
    const totalCreated = sum(a.created_per_day.map((d) => d.count));
    ctx.setSub(`${totalDone} completed in the last ${a.days || days} days`);
    render(body, html`
      <div class="kpis">
        ${kpi("Open tasks", T.open ?? 0, "layers", "k-violet", `${T.due_today ?? 0} due today`)}
        ${kpi("Done this week", T.completed_this_week ?? 0, "completed", "k-green", `${T.done ?? 0} all-time`)}
        ${kpi("Overdue", T.overdue ?? 0, "overdue", T.overdue ? "k-red" : "k-gray", T.overdue ? "needs attention" : "all on track")}
        ${kpi("On-time rate", onTime, "target", "k-blue", "of dated tasks")}
        ${kpi("Streak", html`${a.streak?.current ?? 0}<small> days</small>`, "flame", "k-orange", `best ${a.streak?.best ?? 0} days`)}
        ${kpi("Focus time", fmtH(T.focus_minutes ?? 0), "focus", "k-pink", `avg ${a.avg_completion_hours != null ? `${Math.round(a.avg_completion_hours)}h` : "–"} to finish`)}
      </div>
      <div class="an-grid">
        <section class="panel wide">
          <header><h3>Completed vs created</h3><div class="legend"><span class="lg l-done">Completed · ${totalDone}</span><span class="lg l-created">Created · ${totalCreated}</span></div></header>
          <div class="chart-wrap" id="trend">${trendChart(a.completed_per_day, a.created_per_day)}<div class="tip" id="trend-tip"></div></div>
        </section>
        <section class="panel">
          <header><h3>Open by priority</h3></header>
          ${donut(a.by_priority || {})}
        </section>
        <section class="panel">
          <header><h3>Projects</h3></header>
          ${projectBars(a.by_project || [])}
        </section>
        <section class="panel wide">
          <header><h3>When you get things done</h3><span class="muted small">completions by weekday × hour</span></header>
          ${heatmap(a.heatmap || [])}
        </section>
        <section class="panel wide">
          <header><h3>Focus minutes</h3><span class="muted small">${fmtH(sum((a.focus_per_day || []).map((d) => d.minutes)))} in ${a.days || days} days</span></header>
          ${focusBars(a.focus_per_day || [])}
        </section>
        <section class="panel">
          <header><h3>Status</h3></header>
          ${statusStack(a.by_status || {})}
        </section>
      </div>`);
    wireTrend($("#trend", body), a);
  }

  await load();
  return { refresh: load };
}

const sum = (xs) => xs.reduce((s, x) => s + (Number(x) || 0), 0);
const fmtH = (m) => (m >= 60 ? `${(m / 60).toFixed(m >= 600 ? 0 : 1)}h` : `${m}m`);

function kpi(label, value, ic, tone, sub) {
  return html`<div class="kpi ${tone}"><div class="kpi-ic">${icon(ic, 18)}</div><div class="kpi-v">${value}</div><div class="kpi-l">${label}</div><div class="kpi-s">${sub}</div></div>`;
}

const W = 720, H = 220, PADL = 30, PADB = 26, PADT = 12;

function trendChart(done = [], created = []) {
  const n = Math.max(done.length, 1);
  const max = Math.max(4, ...done.map((d) => d.count), ...created.map((d) => d.count));
  const x = (i) => PADL + (i * (W - PADL - 8)) / Math.max(n - 1, 1);
  const y = (v) => PADT + (H - PADT - PADB) * (1 - v / max);
  const line = (arr) => arr.map((d, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(d.count).toFixed(1)}`).join("");
  const smooth = (arr) => {
    if (arr.length < 2) return line(arr);
    let p = `M${x(0)},${y(arr[0].count)}`;
    for (let i = 1; i < arr.length; i++) {
      const x0 = x(i - 1), y0 = y(arr[i - 1].count), x1 = x(i), y1 = y(arr[i].count), cx = (x0 + x1) / 2;
      p += ` C${cx.toFixed(1)},${y0.toFixed(1)} ${cx.toFixed(1)},${y1.toFixed(1)} ${x1.toFixed(1)},${y1.toFixed(1)}`;
    }
    return p;
  };
  const area = done.length ? `${smooth(done)} L${x(done.length - 1)},${H - PADB} L${x(0)},${H - PADB} Z` : "";
  const ticks = [0, Math.round(max / 2), max];
  const every = Math.ceil(n / 7);
  return raw(`<svg viewBox="0 0 ${W} ${H}" class="chart trend-svg" role="img" aria-label="Completed and created tasks per day">
    <defs><linearGradient id="ga" x1="0" x2="0" y1="0" y2="1"><stop offset="0" class="ga-top"/><stop offset="1" class="ga-bot"/></linearGradient></defs>
    ${ticks.map((t) => `<line x1="${PADL}" x2="${W - 8}" y1="${y(t)}" y2="${y(t)}" class="grid"/><text x="${PADL - 8}" y="${y(t) + 4}" class="axis-t" text-anchor="end">${t}</text>`).join("")}
    ${done.map((d, i) => (i % every === 0 || i === n - 1) ? `<text x="${x(i)}" y="${H - 6}" class="axis-t" text-anchor="middle">${lbl(d.date, n)}</text>` : "").join("")}
    <path d="${area}" class="area" fill="url(#ga)"/>
    <path d="${smooth(created)}" class="line l-created"/>
    <path d="${smooth(done)}" class="line l-done draw"/>
    <line class="hover-line" x1="0" x2="0" y1="${PADT}" y2="${H - PADB}"/>
    <circle class="hover-dot" r="4.5" cx="-10" cy="-10"/>
  </svg>`);
}
const lbl = (s, n) => { const d = parse(s); return n <= 8 ? WD[d.getDay()] : `${MONTHS[d.getMonth()]} ${d.getDate()}`; };

function wireTrend(wrap, a) {
  const svg = wrap.querySelector("svg");
  const tip = wrap.querySelector("#trend-tip");
  const hl = svg.querySelector(".hover-line"), dot = svg.querySelector(".hover-dot");
  const done = a.completed_per_day, created = a.created_per_day;
  const n = done.length;
  if (!n) return;
  const max = Math.max(4, ...done.map((d) => d.count), ...created.map((d) => d.count));
  svg.addEventListener("mousemove", (e) => {
    const r = svg.getBoundingClientRect();
    const vx = ((e.clientX - r.left) / r.width) * W;
    const i = Math.max(0, Math.min(n - 1, Math.round(((vx - PADL) / (W - PADL - 8)) * (n - 1))));
    const px = PADL + (i * (W - PADL - 8)) / Math.max(n - 1, 1);
    const py = PADT + (H - PADT - PADB) * (1 - done[i].count / max);
    hl.setAttribute("x1", px); hl.setAttribute("x2", px); dot.setAttribute("cx", px); dot.setAttribute("cy", py);
    const d = parse(done[i].date);
    tip.innerHTML = "";
    const b = document.createElement("b"); b.textContent = `${WD[d.getDay()]}, ${MONTHS[d.getMonth()]} ${d.getDate()}`;
    const l1 = document.createElement("span"); l1.className = "t-done"; l1.textContent = `${done[i].count} completed`;
    const l2 = document.createElement("span"); l2.className = "t-created"; l2.textContent = `${created[i]?.count ?? 0} created`;
    tip.append(b, l1, l2);
    tip.style.left = `${(px / W) * r.width}px`;
    tip.style.top = `${(py / H) * r.height}px`;
    wrap.classList.add("hovering");
  });
  svg.addEventListener("mouseleave", () => wrap.classList.remove("hovering"));
}

function donut(byP) {
  const vals = [1, 2, 3, 4].map((p) => Number(byP[p] ?? byP[String(p)] ?? 0));
  const total = sum(vals);
  const R = 52, C = 2 * Math.PI * R;
  let off = 0;
  const segs = vals.map((v, i) => {
    const len = total ? (v / total) * C : 0;
    const s = `<circle r="${R}" cx="70" cy="70" fill="none" stroke="${PRIORITY[i + 1].color}" stroke-width="18" stroke-dasharray="${len} ${C - len}" stroke-dashoffset="${-off}" transform="rotate(-90 70 70)" class="seg"/>`;
    off += len;
    return s;
  }).join("");
  return html`<div class="donut-wrap">
    ${raw(`<svg viewBox="0 0 140 140" class="donut" role="img" aria-label="Open tasks by priority"><circle r="${R}" cx="70" cy="70" fill="none" class="donut-bg" stroke-width="18"/>${segs}
      <text x="70" y="68" text-anchor="middle" class="donut-v">${total}</text><text x="70" y="86" text-anchor="middle" class="donut-l">open</text></svg>`)}
    <ul class="donut-legend">${vals.map((v, i) => html`<li><i data-c="${PRIORITY[i + 1].color}"></i>${PRIORITY[i + 1].short} ${PRIORITY[i + 1].name}<b>${v}</b></li>`)}</ul>
  </div>`;
}

function projectBars(list) {
  if (!list.length) return html`<p class="muted small empty-panel">No project data yet.</p>`;
  const max = Math.max(1, ...list.map((p) => (p.open || 0) + (p.done || 0)));
  return html`<ul class="pbars">${list.slice(0, 7).map((p) => {
    const tot = (p.open || 0) + (p.done || 0);
    return html`<li><div class="pb-head"><span>${p.icon || (p.id ? "📁" : "📥")} ${p.name || "Inbox"}</span><span class="muted small">${p.done || 0}/${tot}</span></div>
      <div class="pb-track"><i class="pb-done" data-c="${p.color || "#94a3b8"}" data-w="${((p.done || 0) / max) * 100}%"></i><i class="pb-open" data-c="${p.color || "#94a3b8"}" data-w="${((p.open || 0) / max) * 100}%"></i></div></li>`;
  })}</ul>`;
}

function heatmap(rows) {
  const max = Math.max(1, ...rows.flat());
  const names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  return html`<div class="heat">
    <div class="heat-hours"><span></span>${Array.from({ length: 24 }, (_, h) => html`<span>${h % 3 === 0 ? (h === 0 ? "12a" : h < 12 ? `${h}a` : h === 12 ? "12p" : `${h - 12}p`) : ""}</span>`)}</div>
    ${names.map((n, r) => html`<div class="heat-row"><span class="heat-day">${n}</span>${Array.from({ length: 24 }, (_, h) => {
      const v = rows[r]?.[h] || 0;
      return html`<i class="cell ${v ? "" : "zero"}" data-a="${v ? (0.18 + 0.82 * (v / max)).toFixed(2) : 0}" title="${n} ${h}:00 · ${v} completed"></i>`;
    })}</div>`)}
    <div class="heat-legend">Less <i data-a="0.15"></i><i data-a="0.4"></i><i data-a="0.65"></i><i data-a="1"></i> More</div>
  </div>`;
}

function focusBars(list) {
  if (!list.length) return html`<p class="muted small empty-panel">No focus sessions yet.</p>`;
  const max = Math.max(25, ...list.map((d) => d.minutes || 0));
  return html`<div class="fbars">${list.map((d) => html`<div class="fbar" title="${d.date}: ${d.minutes} min"><i data-h="${((d.minutes || 0) / max) * 100}%"></i></div>`)}</div>`;
}

function statusStack(s) {
  const items = [["todo", "To do", "#94a3b8"], ["in_progress", "In progress", "#6d5cff"], ["done", "Done", "#10b981"]];
  const tot = sum(items.map(([k]) => s[k] || 0)) || 1;
  return html`<div class="sstack">${items.map(([k, , c]) => html`<i data-c="${c}" data-w="${((s[k] || 0) / tot) * 100}%"></i>`)}</div>
    <ul class="donut-legend">${items.map(([k, n, c]) => html`<li><i data-c="${c}"></i>${n}<b>${s[k] || 0}</b></li>`)}</ul>`;
}
