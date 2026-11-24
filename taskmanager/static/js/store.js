// Global client state (user, projects, labels, counts) + a tiny event bus.
import { get } from "./api.js";

const listeners = new Map();
export const state = { user: null, projects: [], labels: [], counts: {}, loaded: false };

export function on(evt, fn) {
  if (!listeners.has(evt)) listeners.set(evt, new Set());
  listeners.get(evt).add(fn);
  return () => listeners.get(evt).delete(fn);
}
export function emit(evt, data) { (listeners.get(evt) || []).forEach((fn) => fn(data)); }

export async function bootstrap() {
  const data = await get("/bootstrap");
  state.user = data.user;
  state.projects = data.projects || [];
  state.labels = data.labels || [];
  state.counts = data.counts || {};
  state.loaded = true;
  emit("bootstrap", state);
  return state;
}

let pending = null;
/** Re-fetch sidebar data and tell the current view to refresh (coalesced). */
export function changed({ view = true } = {}) {
  clearTimeout(pending);
  pending = setTimeout(async () => {
    try { await bootstrap(); } catch (e) { /* surfaced elsewhere */ }
    if (view) emit("refresh");
  }, 60);
}

export const projectById = (id) => state.projects.find((p) => String(p.id) === String(id));
export const labelById = (id) => state.labels.find((l) => String(l.id) === String(id));

export const PRIORITY = {
  1: { name: "Urgent", short: "P1", color: "#ef4444" },
  2: { name: "High", short: "P2", color: "#f59e0b" },
  3: { name: "Medium", short: "P3", color: "#3b82f6" },
  4: { name: "None", short: "P4", color: "#94a3b8" },
};
export const STATUS = { todo: "To do", in_progress: "In progress", done: "Done" };
export const COLORS = ["#6d5cff", "#3b82f6", "#06b6d4", "#10b981", "#84cc16", "#f59e0b", "#f97316", "#ef4444", "#ec4899", "#a855f7", "#64748b", "#14b8a6"];
export const EMOJIS = ["🚀", "📁", "💼", "🏠", "📚", "🎯", "💡", "🛠️", "🎨", "🧪", "📈", "🏋️", "✈️", "🛒", "🎓", "💰", "🧠", "🌱", "🎮", "📝", "⚙️", "🔥", "⭐", "🎵"];
