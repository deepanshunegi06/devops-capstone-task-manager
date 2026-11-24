// Settings: profile, theme, project sharing, labels.
import { html, render, $ } from "../ui/dom.js";
import { icon } from "../ui/icons.js";
import { post, patch, del } from "../api.js";
import { state, changed, bootstrap, COLORS } from "../store.js";
import { avatar } from "../ui/task-ui.js";
import { toast, toastError } from "../ui/toast.js";
import { applyTheme, themePref } from "../theme.js";
import { projectModal, labelModal } from "./projects.js";
import { confirmDialog } from "../ui/modal.js";

export async function renderSettings(ctx) {
  const { el } = ctx;
  const focusProject = ctx.query.project;

  function paint() {
    const u = state.user || {};
    const pref = themePref();
    ctx.setSub("Profile, appearance, sharing & labels");
    render(el, html`<div class="page settings">
      <section class="panel s-card">
        <header><h3>${icon("assigned", 17)}Profile</h3></header>
        <form id="profile" class="s-profile">
          <div class="s-avatar">${avatar(u, 64, "xl")}</div>
          <div class="s-fields">
            <label class="lbl">Display name<input class="input" name="display_name" maxlength="80" value="${u.display_name || ""}" placeholder="${u.username}"></label>
            <div class="lbl">Avatar color<div class="swatches">${COLORS.map((c) => html`<button type="button" class="swatch ${c === u.avatar_color ? "on" : ""}" data-color="${c}" data-c="${c}" aria-label="${c}"></button>`)}</div></div>
            <div class="muted small">Signed in as <b>@${u.username}</b></div>
            <div><button class="btn btn-primary sm">Save profile</button></div>
          </div>
        </form>
      </section>

      <section class="panel s-card">
        <header><h3>${icon("sun", 17)}Appearance</h3></header>
        <div class="theme-cards" role="radiogroup" aria-label="Theme">
          ${[["light", "Light"], ["dark", "Dark"], ["system", "System"]].map(([k, n]) => html`
            <button class="theme-card ${pref === k ? "on" : ""}" data-theme-opt="${k}" role="radio" aria-checked="${pref === k}">
              <span class="tc-prev tc-${k}"><i></i><i></i><i></i></span><span>${n}</span></button>`)}
        </div>
      </section>

      <section class="panel s-card wide">
        <header><h3>${icon("users", 17)}Projects & sharing</h3><button class="btn btn-ghost sm" id="new-proj">${icon("plus", 15)}New project</button></header>
        ${state.projects.length ? html`<ul class="s-projects">${state.projects.map((p) => html`
          <li class="s-proj ${String(p.id) === String(focusProject) ? "highlight" : ""}" data-pid="${p.id}" id="proj-${p.id}">
            <div class="s-proj-head"><span class="proj-icon" data-c="${p.color}">${p.icon || "📁"}</span>
              <div><b>${p.name}</b><div class="muted small">${p.open_count ?? 0} open · ${p.done_count ?? 0} done · you are <b>${p.role || "owner"}</b></div></div>
              <span class="spacer"></span>
              ${p.role === "viewer" ? "" : html`<button class="icon-btn sm" data-edit="${p.id}" aria-label="Edit project">${icon("edit", 15)}</button>`}
            </div>
            <ul class="members">${(p.members || []).map((m) => html`<li>${avatar(m.user, 26)}<span>${m.user.display_name || m.user.username} <span class="muted small">@${m.user.username}</span></span>
              <span class="role-badge r-${m.role}">${m.role}</span>
              ${p.role === "owner" && m.role !== "owner" ? html`<button class="link-btn small danger" data-remove="${m.user.id}">Remove</button>` : ""}</li>`)}</ul>
            ${p.role === "owner" || !p.role ? html`<form class="invite" data-invite="${p.id}">
              <input class="input sm" name="username" placeholder="Invite by username" required>
              <select class="select sm" name="role"><option value="editor">Editor</option><option value="viewer">Viewer</option></select>
              <button class="btn btn-primary sm">${icon("plus", 14)}Add</button></form>` : ""}
          </li>`)}</ul>` : html`<p class="muted">No projects yet. Create one to share it with teammates.</p>`}
      </section>

      <section class="panel s-card">
        <header><h3>${icon("tag", 17)}Labels</h3><button class="btn btn-ghost sm" id="new-label">${icon("plus", 15)}New label</button></header>
        ${state.labels.length ? html`<ul class="s-labels">${state.labels.map((l) => html`<li data-lid="${l.id}"><span class="pill" data-c="${l.color}">@${l.name}</span>
          <span class="muted small">${l.open_count ?? 0} open</span><span class="spacer"></span>
          <button class="icon-btn sm" data-ledit="${l.id}" aria-label="Edit label">${icon("edit", 15)}</button>
          <button class="icon-btn sm danger" data-ldel="${l.id}" aria-label="Delete label">${icon("trash", 15)}</button></li>`)}</ul>`
          : html`<p class="muted">Labels are created automatically when you type <b>@something</b> in quick add.</p>`}
      </section>

      <section class="panel s-card">
        <header><h3>${icon("download", 17)}Your data</h3></header>
        <p class="muted small">Download everything: tasks, projects, labels, subtasks and comments.</p>
        <div class="row gap"><a class="btn btn-ghost sm" href="/api/export.json" download>${icon("download", 15)}Export JSON</a>
          <a class="btn btn-ghost sm" href="/api/export.csv" download>${icon("download", 15)}Export CSV</a></div>
      </section>
    </div>`);
    wire();
    if (focusProject) setTimeout(() => document.getElementById(`proj-${focusProject}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 80);
  }

  function wire() {
    let color = state.user?.avatar_color;
    const prof = $("#profile", el);
    prof.addEventListener("click", (e) => {
      const s = e.target.closest(".swatch");
      if (!s) return;
      color = s.dataset.color;
      prof.querySelectorAll(".swatch").forEach((x) => x.classList.toggle("on", x === s));
      prof.querySelector(".avatar").style.setProperty("--c", color);
    });
    prof.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const { user } = await patch("/me", { display_name: prof.display_name.value.trim(), avatar_color: color });
        state.user = user; toast("Profile saved", { type: "success", timeout: 2000 }); changed({ view: false });
      } catch (err) { toastError(err); }
    });
    el.querySelectorAll("[data-theme-opt]").forEach((b) => b.addEventListener("click", async () => {
      const p = b.dataset.themeOpt;
      applyTheme(p);
      el.querySelectorAll("[data-theme-opt]").forEach((x) => { x.classList.toggle("on", x === b); x.setAttribute("aria-checked", x === b); });
      try { await patch("/me", { theme: p }); } catch (err) { toastError(err); }
    }));
    $("#new-proj", el).addEventListener("click", () => projectModal());
    $("#new-label", el).addEventListener("click", () => labelModal());
    el.querySelectorAll("[data-invite]").forEach((f) => f.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await post(`/projects/${f.dataset.invite}/members`, { username: f.username.value.trim(), role: f.role.value });
        toast(`Added @${f.username.value.trim()}`, { type: "success", timeout: 2000 });
        await bootstrap(); paint();
      } catch (err) { toastError(err); }
    }));
  }

  // delegated once (paint() re-renders the content)
  el.addEventListener("click", async (e) => {
    const ed = e.target.closest("[data-edit]");
    if (ed) projectModal(state.projects.find((p) => String(p.id) === ed.dataset.edit));
    const rm = e.target.closest("[data-remove]");
    if (rm) {
      const pid = rm.closest("[data-pid]").dataset.pid;
      try { await del(`/projects/${pid}/members/${rm.dataset.remove}`); toast("Member removed"); await bootstrap(); paint(); } catch (err) { toastError(err); }
    }
    const le = e.target.closest("[data-ledit]");
    if (le) labelModal(state.labels.find((l) => String(l.id) === le.dataset.ledit));
    const ld = e.target.closest("[data-ldel]");
    if (ld) {
      const l = state.labels.find((x) => String(x.id) === ld.dataset.ldel);
      if (await confirmDialog(`Delete label “@${l?.name}”? It will be removed from all tasks.`, { title: "Delete label?" })) {
        try { await del(`/labels/${ld.dataset.ldel}`); changed(); } catch (err) { toastError(err); }
      }
    }
  });
  paint();
  return { refresh: paint };
}
