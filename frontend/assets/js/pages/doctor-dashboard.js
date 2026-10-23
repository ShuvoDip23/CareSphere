import { getJson, postJson, apiFetch, escapeHtml, formatFee, formatTime } from "../api.js";
import { icon } from "../icons.js";
import { renderChrome } from "../ui/nav.js";
import { toast } from "../ui/toast.js";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const SLOT_CHOICES = [15, 20, 30, 45, 60];

const STATUS_BADGES = {
  pending_payment: { text: "Unpaid", badge: "badge-warn" },
  confirmed: { text: "Confirmed", badge: "badge-ok" },
  completed: { text: "Completed", badge: "badge-info" },
  no_show: { text: "No-show", badge: "badge-danger" },
  cancelled: { text: "Cancelled", badge: "badge-neutral" },
};

const state = { scope: "today", profile: null };

const $ = (id) => document.getElementById(id);

/* ------------------------------------------------------------ profile */

function approvalBanner(doctor) {
  if (doctor.approval_status === "approved") return "";

  const rejected = doctor.approval_status === "rejected";
  return `
    <div class="alert ${rejected ? "alert-error" : "alert-info"} is-visible">
      <strong>${rejected ? "Profile not approved" : "Awaiting approval"}</strong>
      <p style="margin: var(--space-2) 0 0">
        ${
          rejected
            ? "An administrator has asked for changes before your profile goes live."
            : "Your profile is not yet visible in the directory, so patients cannot book you."
        }
      </p>
      ${
        doctor.rejection_note
          ? `<p class="rejection-note">${escapeHtml(doctor.rejection_note)}</p>`
          : ""
      }
    </div>`;
}

function renderProfile(doctor) {
  $("profileHead").innerHTML = `
    ${approvalBanner(doctor)}
    <div class="dash-head">
      <span class="avatar avatar-lg">${escapeHtml(doctor.initials)}</span>
      <div>
        <h1>${escapeHtml(doctor.name)}</h1>
        <p class="text-soft">
          ${escapeHtml(doctor.specialty?.name || "Specialist")} ·
          ${escapeHtml(doctor.hospital)}
        </p>
      </div>
      <span class="dash-fee">
        <small>Consultation fee</small>
        <b>${formatFee(doctor.fee)}</b>
      </span>
    </div>`;
}

/* ------------------------------------------------------- appointments */

function appointmentRow(item) {
  const label = STATUS_BADGES[item.status] || { text: item.status, badge: "badge-neutral" };
  const when = new Date(item.scheduled_for).toLocaleDateString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
  });

  return `
    <article class="visit-row">
      <div class="visit-when">
        <strong>${escapeHtml(formatTime(item.time))}</strong>
        <span>${escapeHtml(when)}</span>
      </div>

      <div class="visit-who">
        <h3>${escapeHtml(item.patient.name)}</h3>
        <p>${escapeHtml(item.reason)}</p>
      </div>

      <div class="visit-side">
        <span class="badge ${label.badge}">${escapeHtml(label.text)}</span>
        <span class="visit-fee">${formatFee(item.fee)}</span>
        ${
          item.can_set_outcome
            ? `<div class="visit-actions">
                 <button class="btn btn-secondary btn-sm" data-outcome="completed"
                         data-id="${item.id}">${icon("check")} Seen</button>
                 <button class="btn btn-ghost btn-sm" data-outcome="no_show"
                         data-id="${item.id}">No-show</button>
               </div>`
            : ""
        }
      </div>
    </article>`;
}

const EMPTY_TEXT = {
  today: "Nothing booked for today.",
  upcoming: "No upcoming appointments.",
  past: "No past appointments yet.",
  all: "No appointments yet.",
};

function renderAppointments(payload) {
  const root = $("visitList");
  if (!payload.items.length) {
    root.innerHTML = `
      <div class="empty-state">
        ${icon("calendar")}
        <h3>${escapeHtml(EMPTY_TEXT[payload.scope] || EMPTY_TEXT.all)}</h3>
        <p>Patients who book you will appear here.</p>
      </div>`;
    return;
  }
  root.innerHTML = payload.items.map(appointmentRow).join("");
}

async function loadAppointments() {
  $("visitList").innerHTML = `<div class="skeleton skeleton-line" style="width:60%"></div>`;
  try {
    renderAppointments(await getJson(`/doctor/appointments?scope=${state.scope}`));
  } catch (error) {
    $("visitList").innerHTML = `
      <div class="empty-state">${icon("info")}<h3>Could not load appointments</h3>
      <p>${escapeHtml(error.message)}</p></div>`;
  }
}

async function setOutcome(id, status, button) {
  const siblings = button.parentElement.querySelectorAll("button");
  siblings.forEach((node) => (node.disabled = true));

  try {
    await postJson(`/doctor/appointments/${encodeURIComponent(id)}/outcome`, { status });
    toast(status === "completed" ? "Marked as seen." : "Marked as a no-show.", "success");
    await loadAppointments();
  } catch (error) {
    toast(error.message, "error");
    siblings.forEach((node) => (node.disabled = false));
  }
}

/* -------------------------------------------------------- availability */

function slotOptions(selected) {
  return SLOT_CHOICES.map(
    (value) =>
      `<option value="${value}"${value === selected ? " selected" : ""}>${value} min</option>`
  ).join("");
}

function renderAvailability(windows) {
  const byDay = new Map(windows.map((w) => [w.day_of_week, w]));

  $("availabilityEditor").innerHTML = DAYS.map((name, index) => {
    const w = byDay.get(index);
    const off = w ? "" : " disabled";
    return `
      <div class="availability-day">
        <label>
          <input type="checkbox" data-day="${index}"${w ? " checked" : ""} />
          ${name}
        </label>
        <div class="day-times">
          <input type="time" data-start="${index}" value="${w?.start_time || "09:00"}"${off} />
          <input type="time" data-end="${index}" value="${w?.end_time || "13:00"}"${off} />
          <select data-slot="${index}"${off}>${slotOptions(w?.slot_minutes || 30)}</select>
        </div>
      </div>`;
  }).join("");

  // One delegated listener rather than seven: the rows are re-rendered on
  // every save, and per-row listeners would leak on each pass.
  $("availabilityEditor").addEventListener("change", (event) => {
    const box = event.target.closest('input[type="checkbox"][data-day]');
    if (!box) return;
    const day = box.dataset.day;
    ["start", "end", "slot"].forEach((key) => {
      $("availabilityEditor").querySelector(`[data-${key}="${day}"]`).disabled = !box.checked;
    });
  });
}

function collectAvailability() {
  const editor = $("availabilityEditor");
  return [...editor.querySelectorAll('input[type="checkbox"][data-day]')]
    .filter((box) => box.checked)
    .map((box) => {
      const day = Number(box.dataset.day);
      return {
        day_of_week: day,
        start_time: editor.querySelector(`[data-start="${day}"]`).value,
        end_time: editor.querySelector(`[data-end="${day}"]`).value,
        slot_minutes: Number(editor.querySelector(`[data-slot="${day}"]`).value),
      };
    });
}

async function saveAvailability(button) {
  button.disabled = true;
  button.textContent = "Saving…";
  $("availabilityError").hidden = true;

  const response = await apiFetch("/doctor/availability", {
    method: "PUT",
    body: JSON.stringify({ availability: collectAvailability() }),
  });
  const data = await response.json().catch(() => ({}));

  if (response.ok) {
    renderAvailability(data);
    toast("Consulting hours updated.", "success");
  } else {
    // The server keys errors by `availability.<index>`; show them together
    // rather than guessing which row the index refers to after a re-render.
    const detail = Object.values(data.fields || {}).join(" ");
    $("availabilityError").textContent = detail || data.error || "Could not save.";
    $("availabilityError").hidden = false;
  }

  button.disabled = false;
  button.textContent = "Save consulting hours";
}

/* ---------------------------------------------------------------- init */

function wireScopes() {
  $("scopeBar").addEventListener("click", (event) => {
    const button = event.target.closest("[data-scope]");
    if (!button || button.dataset.scope === state.scope) return;

    state.scope = button.dataset.scope;
    $("scopeBar")
      .querySelectorAll("[data-scope]")
      .forEach((node) => node.setAttribute("aria-pressed", String(node === button)));
    loadAppointments();
  });

  $("visitList").addEventListener("click", (event) => {
    const button = event.target.closest("[data-outcome]");
    if (button) setOutcome(button.dataset.id, button.dataset.outcome, button);
  });

  $("saveAvailability").addEventListener("click", (event) => saveAvailability(event.currentTarget));
}

function renderNotADoctor(message) {
  $("dashRoot").innerHTML = `
    <div class="empty-state">
      ${icon("lock")}
      <h3>This page is for doctors</h3>
      <p>${escapeHtml(message)}</p>
      <a class="btn btn-primary btn-sm" href="index.html" style="margin-top: var(--space-3)">
        Back to CareSphere
      </a>
    </div>`;
}

document.addEventListener("DOMContentLoaded", async () => {
  const user = await renderChrome();
  if (!user) {
    window.location.replace("login.html?next=doctor-dashboard.html");
    return;
  }

  try {
    state.profile = await getJson("/doctor/me");
  } catch (error) {
    renderNotADoctor(
      error.status === 403
        ? "Your account is not a doctor account."
        : error.message || "Your profile could not be loaded."
    );
    return;
  }

  renderProfile(state.profile);
  renderAvailability(state.profile.availability || []);
  wireScopes();
  await loadAppointments();
});
