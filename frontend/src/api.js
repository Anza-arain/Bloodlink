// Small API client: attaches the JWT and turns errors into readable messages.
const TOKEN_KEY = "bloodlink_token";

export const auth = {
  get token() { try { return localStorage.getItem(TOKEN_KEY); } catch { return null; } },
  set(token) { try { localStorage.setItem(TOKEN_KEY, token); } catch { /* storage blocked */ } },
  clear() { try { localStorage.removeItem(TOKEN_KEY); } catch { /* storage blocked */ } },
};

export async function api(path, { method = "GET", body, params } = {}) {
  let url = "/api" + path;
  if (params) {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null));
    if ([...qs].length) url += "?" + qs;
  }
  const headers = { "Content-Type": "application/json" };
  if (auth.token) headers.Authorization = "Bearer " + auth.token;
  let res;
  try {
    res = await fetch(url, { method, headers, body: body ? JSON.stringify(body) : undefined });
  } catch {
    throw new Error("Cannot reach the server. Is the backend running?");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 401 && auth.token) { auth.clear(); window.location.reload(); }
    let msg = data.detail || `Request failed (${res.status})`;
    if (Array.isArray(msg)) msg = msg.map((e) => `${e.loc?.slice(-1)[0]}: ${e.msg}`).join(", ");
    throw new Error(msg);
  }
  return data;
}

// ---------- formatting helpers ----------
export const fmtDate = (iso) => (iso ? new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "—");
export function timeLeft(iso) {
  const ms = new Date(iso) - new Date();
  if (ms <= 0) return "overdue";
  const h = Math.floor(ms / 3.6e6), m = Math.floor((ms % 3.6e6) / 6e4);
  return h >= 48 ? `${Math.round(h / 24)} days left` : h ? `${h}h ${m}m left` : `${m}m left`;
}
export function ago(iso) {
  const s = (new Date() - new Date(iso)) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}
export const label = (s) => (s || "").replaceAll("_", " ").replace(/^\w/, (c) => c.toUpperCase());
// local datetime-local value -> ISO string with timezone
export const localToIso = (v) => new Date(v).toISOString();
export function isoToLocalInput(d) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}
