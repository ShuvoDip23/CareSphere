import { getJson, apiFetch, escapeHtml, formatFee, formatTime } from "../api.js";
import { icon } from "../icons.js";
import { renderChrome } from "../ui/nav.js";
import { toast } from "../ui/toast.js";

const STATUS_LABELS = {
  pending_payment: { text: "Slot held", badge: "badge-warn" },
  confirmed: { text: "Confirmed", badge: "badge-ok" },
  cancelled: { text: "Cancelled", badge: "badge-neutral" },
  completed: { text: "Completed", badge: "badge-info" },
};

let cache = [];

function statusBadge(appointment) {
  const label = STATUS_LABELS[appointment.status] || {
    text: appointment.status,
    badge: "badge-neutral",
  };
  return `<span class="badge ${label.badge}">${escapeHtml(label.text)}</span>`;
}

function longDate(value) {
  return new Date(value).toLocaleDateString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function card(appointment) {
  const doctor = appointment.doctor || {};
  const cancelled = appointment.status === "cancelled";

  return `
    <article class="appointment-card${cancelled ? " is-cancelled" : ""}">
      <div class="appointment-when">
        <strong>${escapeHtml(formatTime(appointment.time))}</strong>
        <span>${escapeHtml(longDate(appointment.scheduled_for))}</span>
      </div>

      <div class="appointment-body">
        <div class="cluster" style="gap: var(--space-2); align-items: center">
          <span class="avatar">${escapeHtml(doctor.initials || "DR")}</span>
          <div>
            <h3>${escapeHtml(doctor.name || "Doctor")}</h3>
            <p>${escapeHtml(doctor.specialty || "Specialist")} · ${escapeHtml(
              doctor.hospital || ""
            )}</p>
          </div>
        </div>
        <p class="appointment-reason">${escapeHtml(appointment.reason)}</p>
      </div>

      <div class="appointment-side">
        ${statusBadge(appointment)}
        <span class="appointment-fee">${formatFee(appointment.fee)}</span>
        ${
          appointment.can_cancel
            ? `<button class="btn btn-ghost btn-sm" type="button"
                 data-cancel="${appointment.id}">Cancel</button>`
            : ""
        }
      </div>
    </article>`;
}

function section(title, items, emptyText) {
  if (!items.length) {
    return `<section class="appointment-section">
      <h2>${escapeHtml(title)}</h2>
      <p class="text-soft" style="font-size: var(--text-sm)">${escapeHtml(emptyText)}</p>
    </section>`;
  }
  return `<section class="appointment-section">
    <h2>${escapeHtml(title)} <span class="count">${items.length}</span></h2>
    <div class="appointment-list">${items.map(card).join("")}</div>
  </section>`;
}

function render(appointments) {
  const root = document.getElementById("appointmentsRoot");

  if (!appointments.length) {
    root.innerHTML = `
      <div class="empty-state">
        ${icon("calendar")}
        <h3>No appointments yet</h3>
        <p>Find a specialist and book a consultation to see it here.</p>
        <a class="btn btn-primary btn-sm" href="doctors.html"
           style="margin-top: var(--space-3)">Browse doctors</a>
      </div>`;
    return;
  }

  // Cancelled bookings are listed separately rather than mixed into "past",
  // so a patient can tell "this did not happen" from "this already happened".
  const upcoming = appointments.filter((item) => !item.is_past && item.status !== "cancelled");
  const past = appointments.filter((item) => item.is_past && item.status !== "cancelled");
  const cancelled = appointments.filter((item) => item.status === "cancelled");

  upcoming.sort((a, b) => a.scheduled_for.localeCompare(b.scheduled_for));

  root.innerHTML = [
    section("Upcoming", upcoming, "Nothing booked yet."),
    past.length ? section("Past", past, "") : "",
    cancelled.length ? section("Cancelled", cancelled, "") : "",
  ].join("");
}

function renderSignedOut() {
  document.getElementById("appointmentsRoot").innerHTML = `
    <div class="empty-state">
      ${icon("lock")}
      <h3>Sign in to see your appointments</h3>
      <p>Your bookings are private to your account.</p>
      <a class="btn btn-primary btn-sm" href="login.html?next=appointments.html"
         style="margin-top: var(--space-3)">Sign in</a>
    </div>`;
}

async function cancel(id, button) {
  button.disabled = true;
  button.textContent = "Cancelling…";

  const response = await apiFetch(`/appointments/${encodeURIComponent(id)}/cancel`, {
    method: "POST",
  });
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    toast(data.error || "Could not cancel this appointment.", "error");
    button.disabled = false;
    button.textContent = "Cancel";
    return;
  }

  cache = cache.map((item) => (item.id === data.id ? data : item));
  render(cache);
  toast("Appointment cancelled. The slot is open again.", "success");
}

document.addEventListener("DOMContentLoaded", async () => {
  const user = await renderChrome();
  if (!user) {
    renderSignedOut();
    return;
  }

  try {
    cache = await getJson("/appointments");
    render(cache);
  } catch (error) {
    document.getElementById("appointmentsRoot").innerHTML = `
      <div class="empty-state">
        ${icon("info")}
        <h3>Could not load your appointments</h3>
        <p>${escapeHtml(error.message)}</p>
      </div>`;
    return;
  }

  // Delegated, because the list is re-rendered after every cancellation.
  document.getElementById("appointmentsRoot").addEventListener("click", (event) => {
    const button = event.target.closest("[data-cancel]");
    if (button) cancel(button.dataset.cancel, button);
  });
});
