import { html, frag, raw } from "./dom.js";
import { icon } from "./icons.js";

const stack = [];

/** Opens a modal. Returns close(). onMount(el, close) wires behaviour. */
export function openModal({ title, body, onMount, wide = false, className = "" }) {
  const prevFocus = document.activeElement;
  const el = frag(html`
    <div class="modal-backdrop">
      <div class="modal ${wide ? "modal-wide" : ""} ${className}" role="dialog" aria-modal="true" aria-label="${title || "Dialog"}">
        ${title ? html`<header class="modal-head"><h2>${title}</h2>
          <button class="icon-btn modal-x" aria-label="Close">${icon("x", 18)}</button></header>` : ""}
        <div class="modal-body">${body instanceof Object ? body : raw(body || "")}</div>
      </div>
    </div>`);
  document.getElementById("modal-root").appendChild(el);
  requestAnimationFrame(() => el.classList.add("in"));
  const close = () => {
    const i = stack.indexOf(close);
    if (i >= 0) stack.splice(i, 1);
    el.classList.remove("in");
    setTimeout(() => el.remove(), 180);
    prevFocus?.focus?.();
  };
  stack.push(close);
  el.addEventListener("mousedown", (e) => { if (e.target === el) close(); });
  el.querySelector(".modal-x")?.addEventListener("click", close);
  onMount?.(el.querySelector(".modal"), close);
  setTimeout(() => el.querySelector("input:not([type=hidden]), textarea, select, button.btn")?.focus(), 30);
  return close;
}

export function closeTopModal() {
  const c = stack[stack.length - 1];
  if (c) { c(); return true; }
  return false;
}

export function confirmDialog(message, { title = "Are you sure?", ok = "Delete", danger = true } = {}) {
  return new Promise((resolve) => {
    openModal({
      title,
      body: html`<p class="modal-text">${message}</p>
        <div class="modal-actions"><button class="btn btn-ghost" data-act="no">Cancel</button>
        <button class="btn ${danger ? "btn-danger" : "btn-primary"}" data-act="yes">${ok}</button></div>`,
      onMount(el, close) {
        el.querySelector("[data-act=no]").addEventListener("click", () => { close(); resolve(false); });
        el.querySelector("[data-act=yes]").addEventListener("click", () => { close(); resolve(true); });
        setTimeout(() => el.querySelector("[data-act=yes]").focus(), 40);
      },
    });
  });
}
