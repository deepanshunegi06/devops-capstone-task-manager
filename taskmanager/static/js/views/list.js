// List views: Today, Inbox, Upcoming, Overdue, Completed, Assigned, Project, Label.
import { html, render, $ } from "../ui/dom.js";
import { icon } from "../ui/icons.js";
import { get, post, qs } from "../api.js";
import { state, projectById, labelById, changed, STATUS } from "../store.js";
import { mountQuickAdd } from "../quickadd.js";
import { taskRow, bindTaskEvents, sortTasks, emptyState, avatar, updateTask } from "../ui/task-ui.js";
import { sortable } from "../ui/dnd.js";
import { toastError } from "../ui/toast.js";
import { today, todayISO, iso, addDays, parse, diffDays, dayHeader, greeting, MONTHS_LONG, WD } from "../dates.js";
import { projectMenu } from "./projects.js";

const collapsed = new Set(["done"]);

export function queryFor(route, params) {
  switch (route) {
    case "today": return { view: "today" };
    case "inbox": return { view: "inbox", include_done: 1 };
    case "upcoming": return { view: "upcoming" };
    case "overdue": return { view: "overdue" };
    case "completed": return { view: "completed" };
    case "assigned": return { view: "assigned", include_done: 1 };
    case "project": return { project_id: params.id, include_done: 1 };
    case "label": return { label_id: params.id, include_done: 1 };
    default: return { view: "all" };
  }
}

export async function renderList(ctx) {
  const { el, route, params, openTask } = ctx;
  let tasks = [];
  const byId = (id) => tasks.find((t) => String(t.id) === String(id));

  render(el, html`<div class="page list-page">
      <div class="page-head" id="page-head"></div>
      <div id="qa"></div>
      <div id="groups" class="groups">${skeletonRows(5)}</div>
    </div>`);

  const project = route === "project" ? projectById(params.id) : null;
  const label = route === "label" ? labelById(params.id) : null;
  renderHead($("#page-head", el), route, project, label);

  if (route !== "completed" && !(project && project.role === "viewer")) {
    mountQuickAdd($("#qa", el), {
      projectId: project?.id,
      labelId: label?.id,
      defaultDate: route === "today" ? todayISO() : route === "upcoming" ? iso(addDays(today(), 1)) : null,
    });
  }

  const groupsEl = $("#groups", el);
  bindTaskEvents(groupsEl, byId, { openTask });
  groupsEl.addEventListener("click", (e) => {
    const h = e.target.closest("[data-collapse]");
    if (!h) return;
    const k = h.dataset.collapse;
    collapsed.has(k) ? collapsed.delete(k) : collapsed.add(k);
    h.closest(".group").classList.toggle("collapsed");
  });

  sortable(groupsEl, {
    item: ".task-row", list: ".task-list",
    onDrop: async ({ id, list, ids }) => {
      const body = { ids };
      const t = byId(id);
      if (list.dataset.status && t && list.dataset.status !== t.status) body.status = list.dataset.status;
      try {
        if (list.dataset.date && t && list.dataset.date !== t.due_date) await updateTask(id, { due_date: list.dataset.date });
        await post("/tasks/reorder", body);
        changed();
      } catch (err) { toastError(err); changed(); }
    },
  });

  async function load() {
    try {
      const data = await get(`/tasks${qs(queryFor(route, params))}`);
      tasks = data.tasks || [];
      paint();
    } catch (e) {
      render(groupsEl, emptyState("Couldn’t load tasks", e.message, "search"));
    }
  }

  function paint() {
    const groups = groupTasks(route, tasks);
    const total = tasks.filter((t) => t.status !== "done").length;
    ctx.setSub(route === "completed" ? `${tasks.length} completed` : `${total} open task${total === 1 ? "" : "s"}`);
    if (route === "today") renderTodayHero($("#page-head", el), tasks);
    if (!groups.some((g) => g.tasks.length) && route !== "upcoming") {
      render(groupsEl, emptyFor(route));
      return;
    }
    render(groupsEl, html`${groups.map((g) => (g.tasks.length || g.keepEmpty) ? html`
      <section class="group ${collapsed.has(g.key) ? "collapsed" : ""} ${g.tone || ""}">
        <header class="group-head" data-collapse="${g.key}">
          <span class="caret">${icon("down", 14)}</span>
          <h3>${g.title}</h3>${g.sub ? html`<span class="group-sub">${g.sub}</span>` : ""}
          <span class="count">${g.tasks.length}</span>
        </header>
        <ul class="task-list" data-status="${g.status || ""}" data-date="${g.date || ""}">
          ${sortTasks(g.tasks).map((t) => taskRow(t, { showProject: route !== "project" }))}
          ${!g.tasks.length ? html`<li class="drop-hint">Nothing planned · drag a task here</li>` : ""}
        </ul>
      </section>` : "")}`);
  }

  await load();
  return { refresh: load };
}

function groupTasks(route, tasks) {
  const t0 = today();
  const open = tasks.filter((t) => t.status !== "done");
  const due = (t) => (t.due_date ? diffDays(parse(t.due_date), t0) : null);
  if (route === "today") {
    return [
      { key: "overdue", title: "Overdue", tone: "tone-danger", tasks: open.filter((t) => due(t) !== null && due(t) < 0) },
      { key: "today", title: "Today", sub: `${WD[t0.getDay()]}, ${MONTHS_LONG[t0.getMonth()]} ${t0.getDate()}`, tasks: open.filter((t) => due(t) === 0 || due(t) === null) },
      { key: "done-today", title: "Completed today", tasks: tasks.filter((t) => t.status === "done") },
    ];
  }
  if (route === "upcoming") {
    const out = [{ key: "overdue", title: "Overdue", tone: "tone-danger", tasks: open.filter((t) => due(t) !== null && due(t) < 0) }];
    for (let i = 0; i < 7; i++) {
      const d = iso(addDays(t0, i));
      const h = dayHeader(d);
      out.push({ key: `d${d}`, title: h.name, sub: h.sub, date: d, keepEmpty: true, tasks: open.filter((t) => t.due_date === d) });
    }
    const later = open.filter((t) => due(t) !== null && due(t) >= 7);
    out.push({ key: "later", title: "Later", tasks: later });
    return out;
  }
  if (route === "overdue") return [{ key: "overdue", title: "Overdue", tone: "tone-danger", tasks: open }];
  if (route === "completed") {
    const map = new Map();
    tasks.forEach((t) => {
      const d = (t.completed_at || t.updated_at || "").slice(0, 10) || "earlier";
      if (!map.has(d)) map.set(d, []);
      map.get(d).push(t);
    });
    return [...map.entries()].sort((a, b) => (a[0] < b[0] ? 1 : -1)).map(([d, ts]) => {
      const h = d === "earlier" ? { name: "Earlier", sub: "" } : dayHeader(d);
      const n = d === "earlier" ? 0 : diffDays(parse(d), t0);
      return { key: `c${d}`, title: n === 0 ? "Today" : n === -1 ? "Yesterday" : h.sub, sub: n > -2 ? h.sub : WD[parse(d).getDay()], tasks: ts };
    });
  }
  return [
    { key: "in_progress", title: STATUS.in_progress, status: "in_progress", tone: "tone-accent", tasks: tasks.filter((t) => t.status === "in_progress") },
    { key: "todo", title: STATUS.todo, status: "todo", keepEmpty: true, tasks: tasks.filter((t) => t.status === "todo") },
    { key: "done", title: STATUS.done, status: "done", tasks: tasks.filter((t) => t.status === "done") },
  ];
}

function renderHead(el, route, project, label) {
  if (project) {
    render(el, html`<div class="proj-head" data-c="${project.color}">
      <span class="proj-icon">${project.icon || "📁"}</span>
      <div class="proj-info">
        <div class="proj-stats"><b>${project.open_count ?? 0}</b> open · <b>${project.done_count ?? 0}</b> done
          ${project.role && project.role !== "owner" ? html`<span class="role-badge">${project.role}</span>` : ""}</div>
        <div class="proj-progress"><i data-w="${pct(project)}%"></i></div>
      </div>
      <div class="avatar-stack">${(project.members || []).slice(0, 5).map((m) => avatar(m.user, 26))}</div>
      <button class="btn btn-ghost sm" id="share-btn">${icon("users", 15)}Share</button>
      <button class="icon-btn" id="proj-more" aria-label="Project options">${icon("dots", 18)}</button>
    </div>`);
    el.querySelector("#share-btn").addEventListener("click", () => { location.hash = `#/settings?project=${project.id}`; });
    el.querySelector("#proj-more").addEventListener("click", (e) => projectMenu(e.currentTarget, project));
  } else if (label) {
    render(el, html`<div class="label-head" data-c="${label.color}"><span class="pill big">@${label.name}</span></div>`);
  } else render(el, "");
}

const pct = (p) => { const tot = (p.open_count || 0) + (p.done_count || 0); return tot ? Math.round((p.done_count / tot) * 100) : 0; };

function renderTodayHero(el, tasks) {
  const doneToday = (state.counts.completed_today ?? tasks.filter((t) => t.status === "done").length) || 0;
  const open = tasks.filter((t) => t.status !== "done").length;
  const total = open + doneToday;
  const p = total ? doneToday / total : 0;
  const C = 2 * Math.PI * 26;
  const name = (state.user?.display_name || state.user?.username || "").split(" ")[0];
  render(el, html`<div class="hero">
    <div class="hero-text">
      <h2>${greeting()}${name ? html`, ${name}` : ""} 👋</h2>
      <p>${open ? html`You have <b>${open}</b> task${open === 1 ? "" : "s"} on your plate today${state.counts.overdue ? html` and <b class="txt-danger">${state.counts.overdue} overdue</b>` : ""}.` : "Nothing left for today. Enjoy the calm ✨"}</p>
    </div>
    <div class="hero-ring" title="${doneToday} of ${total} done today">
      <svg viewBox="0 0 64 64" width="64" height="64"><circle cx="32" cy="32" r="26" class="ring-bg"/>
        <circle cx="32" cy="32" r="26" class="ring-fg" stroke-dasharray="${C}" stroke-dashoffset="${C * (1 - p)}" transform="rotate(-90 32 32)"/></svg>
      <span><b>${doneToday}</b>/${total}</span>
    </div>
  </div>`);
}

function emptyFor(route) {
  const m = {
    today: ["All clear for today", "Add something with the quick-add bar, or enjoy the free time."],
    inbox: ["Inbox zero", "Capture anything on your mind. Sort it into projects later."],
    overdue: ["Nothing overdue", "You’re fully on schedule. Nice work."],
    completed: ["No completed tasks yet", "Finish a task and it will show up here."],
    assigned: ["Nothing assigned to you", "Tasks assigned to you in shared projects appear here."],
  }[route] || ["No tasks here yet", "Use the quick-add bar above to create the first one."];
  return emptyState(m[0], m[1]);
}

export function skeletonRows(n = 4) {
  return html`<div class="skeleton-list">${Array.from({ length: n }, (_, i) => html`<div class="sk-row"><i class="sk-c"></i><div><i class="sk-l w${(i % 3) + 1}"></i><i class="sk-s"></i></div></div>`)}</div>`;
}
