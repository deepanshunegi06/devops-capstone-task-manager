// REST client. Session cookie auth + X-CSRF-Token for mutating requests.
const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || "";

export class ApiError extends Error {
  constructor(message, status, data) { super(message); this.status = status; this.data = data; }
}

export async function api(path, { method = "GET", body, signal } = {}) {
  const opts = { method, credentials: "same-origin", headers: { Accept: "application/json" }, signal };
  if (method !== "GET") {
    opts.headers["Content-Type"] = "application/json";
    opts.headers["X-CSRF-Token"] = csrf();
    if (body !== undefined) opts.body = JSON.stringify(body);
  }
  const res = await fetch(`/api${path}`, opts);
  if (res.status === 401) {
    window.location.href = `/login?next=${encodeURIComponent("/app" + window.location.hash)}`;
    throw new ApiError("Not logged in", 401, {});
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const fields = data.fields ? Object.values(data.fields).join(" ") : "";
    throw new ApiError(fields || data.message || data.error || `Request failed (${res.status})`, res.status, data);
  }
  return data;
}

export const get = (p, o) => api(p, o);
export const post = (p, body) => api(p, { method: "POST", body: body ?? {} });
export const patch = (p, body) => api(p, { method: "PATCH", body });
export const del = (p) => api(p, { method: "DELETE" });

export const qs = (obj) => {
  const p = new URLSearchParams();
  Object.entries(obj).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") p.set(k, v); });
  const s = p.toString();
  return s ? `?${s}` : "";
};
