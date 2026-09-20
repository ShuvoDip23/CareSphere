import { API_BASE_URL } from "./config.js";

/** Thin fetch wrapper. Always sends the session cookie. */
export async function apiFetch(path, options = {}) {
  const hasBody = Boolean(options.body);
  return fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    ...options,
    headers: hasBody
      ? { "Content-Type": "application/json", ...(options.headers || {}) }
      : options.headers,
  });
}

/** Fetch and parse JSON, throwing the server's error message on failure. */
export async function getJson(path, options = {}) {
  const response = await apiFetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.error || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return data;
}

export function postJson(path, body) {
  return getJson(path, { method: "POST", body: JSON.stringify(body) });
}

/** Escape untrusted text before it reaches innerHTML. */
export function escapeHtml(value) {
  const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
  return String(value ?? "").replace(/[&<>"']/g, (char) => map[char]);
}

/** Build a query string, dropping empty values. */
export function queryString(params) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") {
      search.set(key, value);
    }
  });
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
}

/** Bangladeshi taka, no decimals. */
export function formatFee(amount) {
  const value = Number(amount || 0);
  return `\u09F3${value.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

/** "09:00" -> "9:00 AM" */
export function formatTime(value) {
  const [rawHour, minute] = String(value || "").split(":");
  const hour = Number(rawHour);
  if (Number.isNaN(hour)) return value;
  const suffix = hour >= 12 ? "PM" : "AM";
  const display = hour % 12 === 0 ? 12 : hour % 12;
  return `${display}:${minute} ${suffix}`;
}
