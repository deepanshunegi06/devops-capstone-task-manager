// Global activity feed.
import { html, render } from "../ui/dom.js";
import { icon } from "../ui/icons.js";
import { get } from "../api.js";
import { avatar, emptyState } from "../ui/task-ui.js";
import { actionText } from "../ui/drawer.js";
import { ago, dayHeader } from "../dates.js";
import { toastError } from "../ui/toast.js";

const ACT_IC = { created: "plus", completed: "completed", reopened: "reset", commented: "message", deleted: "trash", restored: "reset", updated: "edit", assigned: "assigned", duplicated: "copy" };

export async function renderActivity(ctx) {
  const { el, openTask } = ctx;
  render(el, html`<div class="page activity-page"><div id="feed" class="feed"><div class="skeleton-list"><div class="sk-row"></div><div class="sk-row"></div><div class="sk-row"></div></div></div></div>`);
  const feed = el.querySelector("#feed");
  feed.addEventListener("click", (e) => { const a = e.target.closest("[data-task]"); if (a) { e.preventDefault(); openTask(a.dataset.task); } });

  async function load() {
    try {
      const { activity } = await get("/activity?limit=80");
      ctx.setSub(`${activity.length} recent events`);
      if (!activity.length) { render(feed, emptyState("No activity yet", "Create, complete or comment on tasks and the story appears here.")); return; }
      const groups = new Map();
      activity.forEach((a) => {
        const d = (a.created_at || "").slice(0, 10);
        if (!groups.has(d)) groups.set(d, []);
        groups.get(d).push(a);
      });
      render(feed, html`${[...groups.entries()].map(([d, items]) => html`
        <section class="feed-day"><h3>${d ? `${dayHeader(d).name === "Today" || dayHeader(d).name === "Tomorrow" ? dayHeader(d).name : dayHeader(d).sub}` : "Earlier"}</h3>
          <ol class="feed-list">${items.map((a) => html`<li class="feed-item a-${a.action}">
            <span class="feed-ic">${icon(ACT_IC[a.action] || "activity", 14)}</span>
            ${avatar(a.actor, 28)}
            <div class="feed-text"><b>${a.actor?.display_name || a.actor?.username || "Someone"}</b> ${actionText({ ...a, detail: null }).replace(" this task", "")}
              ${a.task ? html` <a href="#/task/${a.task.id}" data-task="${a.task.id}" class="feed-task">${a.task.title}</a>` : ""}
              ${a.detail && a.detail !== a.task?.title ? html`<div class="feed-detail">${a.detail}</div>` : ""}</div>
            <time class="muted small">${ago(a.created_at)}</time></li>`)}</ol></section>`)}`);
    } catch (e) { toastError(e); }
  }
  await load();
  return { refresh: load };
}
