// Theme handling: "light" | "dark" | "system". Mirrored to localStorage for flash-free loads.
const mq = window.matchMedia("(prefers-color-scheme: dark)");

export function themePref() {
  return document.documentElement.getAttribute("data-theme-pref") || localStorage.getItem("orbit-theme") || "system";
}

export function applyTheme(pref) {
  const p = ["light", "dark", "system"].includes(pref) ? pref : "system";
  const dark = p === "dark" || (p === "system" && mq.matches);
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  document.documentElement.setAttribute("data-theme-pref", p);
  try { localStorage.setItem("orbit-theme", p); } catch { /* private mode */ }
  document.dispatchEvent(new CustomEvent("themechange", { detail: { pref: p, dark } }));
}

export const isDark = () => document.documentElement.getAttribute("data-theme") === "dark";

mq.addEventListener?.("change", () => { if (themePref() === "system") applyTheme("system"); });
