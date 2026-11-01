import { getJson, apiFetch, escapeHtml } from "../api.js";
import { renderChrome } from "../ui/nav.js";
import { toast } from "../ui/toast.js";

const $ = (id) => document.getElementById(id);
let notified = new Set();

async function load(showBrowserAlerts = false) {
  // Evaluate today's reminder slots while the app is open; the server records due/missed alerts once.
  await getJson("/reminders/today").catch(() => {});
  const data = await getJson("/notifications");
  $("notifications").innerHTML = data.notifications.length
    ? data.notifications
        .map(
          (
            n
          ) => `<article style="padding:1rem 0;border-bottom:1px solid var(--color-border);${n.read ? "opacity:.7" : ""}">
    <div class="section-head"><strong>${escapeHtml(n.title)}</strong><span class="badge">${n.read ? "Read" : "Unread"}</span></div>
    <p>${escapeHtml(n.message)}</p><small>${new Date(n.created_at).toLocaleString()}</small>
    <div style="margin-top:.5rem"><button class="btn btn-ghost btn-sm" data-read="${n.id}">Mark read</button>
    <button class="btn btn-ghost btn-sm" data-delete="${n.id}">Delete</button></div></article>`
        )
        .join("")
    : "<p>You have no notifications.</p>";
  if (showBrowserAlerts && "Notification" in window && Notification.permission === "granted") {
    data.notifications
      .filter((n) => !n.read && !notified.has(n.id))
      .forEach((n) => {
        new Notification(n.title, { body: n.message, tag: `caresphere-${n.id}` });
        notified.add(n.id);
      });
  }
}
$("enableBrowser").addEventListener("click", async () => {
  if (!("Notification" in window)) {
    $("permissionStatus").textContent =
      "This browser does not support browser notifications. In-app notifications remain available.";
    return;
  }
  const permission = await Notification.requestPermission();
  $("permissionStatus").textContent =
    permission === "granted"
      ? "Browser alerts enabled while CareSphere is open."
      : "Browser permission was not granted. In-app notifications remain available.";
  if (permission === "granted") await load(true);
});
$("readAll").addEventListener("click", async () => {
  try {
    await apiFetch("/notifications/read-all", { method: "POST" });
    await load();
  } catch (e) {
    toast(e.message, "error");
  }
});
document.addEventListener("click", async (event) => {
  const read = event.target.closest("[data-read]"),
    del = event.target.closest("[data-delete]");
  try {
    if (read) await apiFetch(`/notifications/${read.dataset.read}/read`, { method: "PATCH" });
    if (del) await apiFetch(`/notifications/${del.dataset.delete}`, { method: "DELETE" });
    await load();
  } catch (e) {
    toast(e.message, "error");
  }
});
document.addEventListener("DOMContentLoaded", async () => {
  const user = await renderChrome();
  if (!user) {
    location.href = "login.html";
    return;
  }
  try {
    await load();
  } catch (e) {
    $("notifications").textContent = e.message;
  }
  // Foreground polling only: background delivery requires a separately configured push service.
  window.setInterval(() => load(true).catch(() => {}), 60000);
});
