// Date helpers. ISO "YYYY-MM-DD" strings are treated as local calendar dates.
const pad = (n) => String(n).padStart(2, "0");
export const iso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
export const parse = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
export const today = () => { const d = new Date(); d.setHours(0, 0, 0, 0); return d; };
export const todayISO = () => iso(today());
export const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
export const diffDays = (a, b) => Math.round((a - b) / 86400000);
export const WD = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const MONTHS_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

export const shortDate = (d) => `${MONTHS[d.getMonth()]} ${d.getDate()}`;

/** "Today", "Tomorrow", "Yesterday", "Mon", "Nov 28", "Overdue 2d" */
export function relDay(s, { overdueStyle = false } = {}) {
  if (!s) return "";
  const d = parse(s);
  const n = diffDays(d, today());
  if (n === 0) return "Today";
  if (n === 1) return "Tomorrow";
  if (n === -1) return overdueStyle ? "Yesterday" : "Yesterday";
  if (n < -1) return overdueStyle ? `Overdue ${-n}d` : shortDate(d);
  if (n < 7) return WD[d.getDay()];
  return d.getFullYear() === today().getFullYear() ? shortDate(d) : `${shortDate(d)}, ${d.getFullYear()}`;
}

export function dayHeader(s) {
  const d = parse(s);
  const n = diffDays(d, today());
  const name = n === 0 ? "Today" : n === 1 ? "Tomorrow" : ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][d.getDay()];
  return { name, sub: `${MONTHS_LONG[d.getMonth()]} ${d.getDate()}` };
}

export function time12(t) {
  if (!t) return "";
  const [h, m] = t.split(":").map(Number);
  const ap = h >= 12 ? "PM" : "AM";
  const hh = h % 12 || 12;
  return m ? `${hh}:${pad(m)} ${ap}` : `${hh} ${ap}`;
}

export function ago(ts) {
  if (!ts) return "";
  const t = new Date(ts.endsWith("Z") || ts.includes("+") ? ts : ts + "Z");
  const s = Math.max(1, Math.round((Date.now() - t.getTime()) / 1000));
  if (s < 60) return "just now";
  const m = Math.round(s / 60); if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60); if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24); if (d < 7) return `${d}d ago`;
  return shortDate(t);
}

export const greeting = () => {
  const h = new Date().getHours();
  return h < 5 ? "Working late" : h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
};
