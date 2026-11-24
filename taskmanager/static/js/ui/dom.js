// Tiny DOM helpers. All interpolations in html`` are HTML-escaped unless wrapped in raw().
// CSP forbids style="" attributes, so dynamic colours/sizes are passed as data-* and applied by hydrate().

const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ESC[c]);

class Raw { constructor(s) { this.s = s; } toString() { return this.s; } }
export const raw = (s) => new Raw(String(s ?? ""));

function fmt(v) {
  if (v === null || v === undefined || v === false) return "";
  if (v instanceof Raw) return v.s;
  if (Array.isArray(v)) return v.map(fmt).join("");
  return esc(v);
}

export function html(strings, ...vals) {
  let out = "";
  strings.forEach((s, i) => { out += s; if (i < vals.length) out += fmt(vals[i]); });
  return new Raw(out);
}

/** Apply data-c (colour), data-w (width %), data-h (height %), data-a (alpha) attributes as inline styles. */
export function hydrate(root) {
  root.querySelectorAll("[data-c]").forEach((e) => e.style.setProperty("--c", e.dataset.c));
  root.querySelectorAll("[data-w]").forEach((e) => { e.style.width = e.dataset.w; });
  root.querySelectorAll("[data-h]").forEach((e) => { e.style.height = e.dataset.h; });
  root.querySelectorAll("[data-a]").forEach((e) => e.style.setProperty("--a", e.dataset.a));
  return root;
}

export function render(el, tpl) {
  el.innerHTML = String(tpl);
  return hydrate(el);
}

export function frag(tpl) {
  const t = document.createElement("template");
  t.innerHTML = String(tpl).trim();
  hydrate(t.content);
  return t.content.firstElementChild;
}

export const $ = (s, r = document) => r.querySelector(s);
export const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

/** Delegated event listener. */
export function on(root, type, selector, handler, opts) {
  const fn = (e) => {
    const t = e.target.closest(selector);
    if (t && root.contains(t)) handler(e, t);
  };
  root.addEventListener(type, fn, opts);
  return () => root.removeEventListener(type, fn, opts);
}

export function debounce(fn, ms = 250) {
  let t;
  const d = (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
  d.cancel = () => clearTimeout(t);
  return d;
}

export const isTyping = (e) => {
  const t = e.target;
  return t && (t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName));
};

export const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
