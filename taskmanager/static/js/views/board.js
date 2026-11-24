// Kanban board: To do / In progress / Done with drag & drop.
import { html, render, $ } from "../ui/dom.js";
import { icon } from "../ui/icons.js";
import { get, post, qs } from "../api.js";
import { changed, projectById } from "../store.js";
import { taskCard, bindTaskEvents, sortTasks } from "../ui/task-ui.js";
import { sortable } from "../ui/dnd.js";
import { toast, toastError } from "../ui/toast.js";
import { queryFor } from "./list.js";

const COLS = [
  { status: "todo", title: "To do", tone: "c-todo" },
  { status: "in_progress", title: "In progress", tone: "c-prog" },
  { status: "done", title: "Done", tone: "c-done" },
];

export async function renderBoard(ctx) {
  const { el, route, params, openTask } = ctx;
  let tasks = [];
  const byId = (id) => tasks.find((t) => String(t.id) === String(id));
  const project = route === "project" ? projectById(params.id) : null;
  const query = { ...(route === "board" ? { view: "all" } : queryFor(route, params)), include_done: 1 };
  if (query.view === "completed") delete query.view;

  render(el, html`<div class="board" id="board">${COLS.map((c) => html`
    <section class="col ${c.tone}">
      <header class="col-head"><span class="col-dot"></span><h3>${c.title}</h3><span class="count" data-count="${c.status}">·</span></header>
      <div class="col-body" data-status="${c.status}"><div class="sk-card"></div><div class="sk-card"></div></div>
      ${project?.role === "viewer" ? "" : html`<form class="col-add" data-status="${c.status}">
        <span>${icon("plus", 16)}</span><input placeholder="Add a card…" aria-label="Add card to ${c.title}" maxlength="300"></form>`}
    </section>`)}</div>`);
  const board = $("#board", el);
  bindTaskEvents(board, byId, { openTask });

  sortable(board, {
    item: ".card", list: ".col-body",
    onDrop: async ({ id, list, ids }) => {
      const t = byId(id);
      const status = list.dataset.status;
      try {
        await post("/tasks/reorder", { ids, status });
        if (t && t.status !== status && status === "done") toast("Moved to Done 🎉", { type: "success", timeout: 2000 });
        changed();
      } catch (err) { toastError(err); changed(); }
    },
  });

  board.addEventListener("submit", async (e) => {
    const f = e.target.closest(".col-add");
    if (!f) return;
    e.preventDefault();
    const input = f.querySelector("input");
    const text = input.value.trim();
    if (!text) return;
    try {
      const body = { text };
      if (project) body.project_id = project.id;
      const res = await post("/tasks/quick", body);
      if (f.dataset.status !== "todo") await post("/tasks/reorder", { ids: [res.task.id], status: f.dataset.status });
      input.value = "";
      changed();
    } catch (err) { toastError(err); }
  });

  async function load() {
    try {
      tasks = (await get(`/tasks${qs(query)}`)).tasks || [];
      paint();
    } catch (e) { toastError(e); }
  }

  function paint() {
    COLS.forEach((c) => {
      const list = sortTasks(tasks.filter((t) => t.status === c.status));
      const body = board.querySelector(`.col-body[data-status="${c.status}"]`);
      render(body, list.length ? html`${list.map((t) => taskCard(t))}` : html`<div class="col-empty">${c.status === "done" ? "Drop finished work here" : "No cards"}</div>`);
      board.querySelector(`[data-count="${c.status}"]`).textContent = list.length;
    });
    const open = tasks.filter((t) => t.status !== "done").length;
    ctx.setSub(`${open} open · ${tasks.length - open} done`);
  }

  await load();
  return { refresh: load };
}
