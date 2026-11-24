import { html, frag } from "./dom.js";
import { icon } from "./icons.js";

const root = () => document.getElementById("toast-root");

/** toast("Saved") or toast("Task deleted", { action: "Undo", onAction: fn, type: "success" }) */
export function toast(message, { action, onAction, type = "info", timeout = 5000 } = {}) {
  const ic = { success: "check", error: "x", info: "sparkles" }[type] || "sparkles";
  const el = frag(html`
    <div class="toast toast-${type}" role="status">
      <span class="toast-ic">${icon(ic, 16)}</span>
      <span class="toast-msg">${message}</span>
      ${action ? html`<button class="toast-action">${action}</button>` : ""}
      <button class="toast-close" aria-label="Dismiss">${icon("x", 14)}</button>
    </div>`);
  root().appendChild(el);
  requestAnimationFrame(() => el.classList.add("in"));
  let timer;
  const close = () => {
    clearTimeout(timer);
    el.classList.remove("in");
    el.classList.add("out");
    setTimeout(() => el.remove(), 220);
  };
  el.querySelector(".toast-close").addEventListener("click", close);
  if (action) {
    el.querySelector(".toast-action").addEventListener("click", async () => {
      close();
      try { await onAction?.(); } catch (e) { toast(e.message, { type: "error" }); }
    });
  }
  timer = setTimeout(close, timeout);
  el.addEventListener("mouseenter", () => clearTimeout(timer));
  el.addEventListener("mouseleave", () => { timer = setTimeout(close, 2000); });
  return close;
}

export const toastError = (e) => toast(e?.message || String(e), { type: "error", timeout: 6000 });
