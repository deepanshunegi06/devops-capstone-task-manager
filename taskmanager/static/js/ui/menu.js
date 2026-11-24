// Popover menus anchored to an element.
import { html, frag } from "./dom.js";
import { icon } from "./icons.js";

let current = null;

export function closeMenu() {
  if (current) { current.remove(); current = null; document.removeEventListener("mousedown", outside, true); }
}
function outside(e) { if (current && !current.contains(e.target)) closeMenu(); }

/**
 * items: [{ label, icon, color, hint, checked, danger, onClick } | { sep: true } | { header: "Title" }]
 */
export function openMenu(anchor, items, { align = "left", width } = {}) {
  closeMenu();
  const el = frag(html`
    <div class="menu" role="menu">
      ${items.map((it, i) => it.sep ? html`<div class="menu-sep"></div>`
        : it.header ? html`<div class="menu-header">${it.header}</div>`
        : html`<button class="menu-item ${it.danger ? "danger" : ""} ${it.checked ? "checked" : ""}" role="menuitem" data-i="${i}">
            ${it.color ? html`<span class="menu-dot" data-c="${it.color}"></span>` : it.icon ? icon(it.icon, 16) : ""}
            <span class="menu-label">${it.label}</span>
            ${it.hint ? html`<span class="menu-hint">${it.hint}</span>` : ""}
            ${it.checked ? icon("check", 15, "menu-check") : ""}
          </button>`)}
    </div>`);
  document.getElementById("menu-root").appendChild(el);
  if (width) el.style.width = `${width}px`;
  const r = anchor.getBoundingClientRect();
  const mw = el.offsetWidth, mh = el.offsetHeight;
  let left = align === "right" ? r.right - mw : r.left;
  let top = r.bottom + 6;
  left = Math.max(8, Math.min(left, window.innerWidth - mw - 8));
  if (top + mh > window.innerHeight - 8) top = Math.max(8, r.top - mh - 6);
  el.style.left = `${left}px`;
  el.style.top = `${top}px`;
  el.addEventListener("click", (e) => {
    const b = e.target.closest(".menu-item");
    if (!b) return;
    const it = items[Number(b.dataset.i)];
    closeMenu();
    it.onClick?.();
  });
  el.addEventListener("keydown", (e) => {
    const btns = [...el.querySelectorAll(".menu-item")];
    const i = btns.indexOf(document.activeElement);
    if (e.key === "ArrowDown") { e.preventDefault(); btns[(i + 1) % btns.length]?.focus(); }
    if (e.key === "ArrowUp") { e.preventDefault(); btns[(i - 1 + btns.length) % btns.length]?.focus(); }
    if (e.key === "Escape") { e.stopPropagation(); closeMenu(); anchor.focus?.(); }
  });
  current = el;
  setTimeout(() => document.addEventListener("mousedown", outside, true), 0);
  el.querySelector(".menu-item")?.focus({ preventScroll: true });
  return el;
}
