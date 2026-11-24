// Project & label create/edit modals and menus.
import { html } from "../ui/dom.js";
import { icon } from "../ui/icons.js";
import { post, patch, del } from "../api.js";
import { openModal, confirmDialog } from "../ui/modal.js";
import { openMenu } from "../ui/menu.js";
import { toast, toastError } from "../ui/toast.js";
import { changed, bootstrap, COLORS, EMOJIS } from "../store.js";

export function projectModal(project = null) {
  let color = project?.color || COLORS[Math.floor(Math.random() * COLORS.length)];
  let emoji = project?.icon || "🚀";
  openModal({
    title: project ? "Edit project" : "New project",
    body: html`<form class="form" id="proj-form">
      <div class="proj-preview"><span class="proj-icon lg" id="pp-icon">${emoji}</span>
        <input class="input lg" name="name" required maxlength="60" placeholder="Project name" value="${project?.name || ""}"></div>
      <div class="field-label">Color</div>
      <div class="swatches">${COLORS.map((c) => html`<button type="button" class="swatch ${c === color ? "on" : ""}" data-color="${c}" data-c="${c}" aria-label="Color ${c}"></button>`)}</div>
      <div class="field-label">Icon</div>
      <div class="emoji-grid">${EMOJIS.map((e) => html`<button type="button" class="emoji ${e === emoji ? "on" : ""}" data-emoji="${e}">${e}</button>`)}</div>
      <div class="modal-actions"><button type="button" class="btn btn-ghost" data-cancel>Cancel</button>
        <button class="btn btn-primary">${project ? "Save" : "Create project"}</button></div>
    </form>`,
    onMount(el, close) {
      const form = el.querySelector("form");
      const preview = el.querySelector("#pp-icon");
      preview.style.setProperty("--c", color);
      el.querySelector("[data-cancel]").addEventListener("click", close);
      el.addEventListener("click", (e) => {
        const s = e.target.closest(".swatch");
        if (s) { color = s.dataset.color; el.querySelectorAll(".swatch").forEach((x) => x.classList.toggle("on", x === s)); preview.style.setProperty("--c", color); }
        const em = e.target.closest(".emoji");
        if (em) { emoji = em.dataset.emoji; el.querySelectorAll(".emoji").forEach((x) => x.classList.toggle("on", x === em)); preview.textContent = emoji; }
      });
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const name = form.name.value.trim();
        if (!name) return;
        try {
          if (project) {
            await patch(`/projects/${project.id}`, { name, color, icon: emoji });
            toast("Project updated", { type: "success", timeout: 2000 });
          } else {
            const res = await post("/projects", { name, color, icon: emoji });
            toast(`Project “${name}” created`, { type: "success", timeout: 2500 });
            await bootstrap();
            location.hash = `#/project/${res.project.id}`;
          }
          close();
          changed();
        } catch (err) { toastError(err); }
      });
    },
  });
}

export function projectMenu(anchor, project) {
  const owner = project.role === "owner" || !project.role;
  openMenu(anchor, [
    { label: "Edit project", icon: "edit", onClick: () => projectModal(project) },
    { label: "Share & members", icon: "users", onClick: () => { location.hash = `#/settings?project=${project.id}`; } },
    { label: "Open board", icon: "board", onClick: () => { location.hash = `#/project/${project.id}?mode=board`; } },
    ...(owner ? [{ sep: true }, {
      label: "Delete project", icon: "trash", danger: true,
      onClick: async () => {
        if (!(await confirmDialog(`“${project.name}” and all of its tasks will be deleted permanently.`, { title: "Delete project?" }))) return;
        try { await del(`/projects/${project.id}`); toast("Project deleted"); location.hash = "#/today"; changed(); }
        catch (e) { toastError(e); }
      },
    }] : []),
  ], { align: "right" });
}

export function labelModal(label = null) {
  let color = label?.color || COLORS[(Math.random() * COLORS.length) | 0];
  openModal({
    title: label ? "Edit label" : "New label",
    body: html`<form class="form"><input class="input" name="name" required maxlength="40" placeholder="Label name (no spaces)" value="${label?.name || ""}">
      <div class="field-label">Color</div>
      <div class="swatches">${COLORS.map((c) => html`<button type="button" class="swatch ${c === color ? "on" : ""}" data-color="${c}" data-c="${c}"></button>`)}</div>
      <div class="modal-actions"><button type="button" class="btn btn-ghost" data-cancel>Cancel</button><button class="btn btn-primary">${label ? "Save" : "Create label"}</button></div></form>`,
    onMount(el, close) {
      const form = el.querySelector("form");
      el.querySelector("[data-cancel]").addEventListener("click", close);
      el.addEventListener("click", (e) => {
        const s = e.target.closest(".swatch");
        if (s) { color = s.dataset.color; el.querySelectorAll(".swatch").forEach((x) => x.classList.toggle("on", x === s)); }
      });
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const name = form.name.value.trim().replace(/^@/, "").replace(/\s+/g, "-");
        if (!name) return;
        try {
          if (label) await patch(`/labels/${label.id}`, { name, color });
          else await post("/labels", { name, color });
          close(); changed();
        } catch (err) { toastError(err); }
      });
    },
  });
}

export { icon };
