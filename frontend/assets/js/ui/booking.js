/* Booking panel for the doctor profile page.
   Kept out of doctor-detail.js so the profile module stays a renderer and the
   booking flow - which has state, network calls and failure paths - is
   testable and movable on its own. */

import { getJson, postJson, escapeHtml, formatFee, formatTime } from "../api.js";
import { icon } from "../icons.js";
import { toast } from "./toast.js";

const HORIZON_DAYS = 60;

/** `2026-11-03`, in the browser's own timezone rather than UTC. */
function isoDate(date) {
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 10);
}

function dateBounds() {
  const today = new Date();
  const last = new Date(today);
  last.setDate(last.getDate() + HORIZON_DAYS);
  return { min: isoDate(today), max: isoDate(last) };
}

function slotButton(slot) {
  const label = formatTime(slot.time);
  if (slot.is_available) {
    return `<button class="slot" type="button" data-time="${slot.time}">${label}</button>`;
  }
  const why = slot.is_booked ? "Already booked" : "This time has passed";
  return `<button class="slot" type="button" disabled title="${why}" aria-label="${label} — ${why}">${label}</button>`;
}

function slotsMarkup(payload) {
  if (!payload.bookable || !payload.slots.length) {
    return `<p class="slot-empty">${escapeHtml(
      payload.message || "No consulting hours on this day."
    )}</p>`;
  }
  const open = payload.slots.filter((slot) => slot.is_available).length;
  return `
    <div class="slot-grid">${payload.slots.map(slotButton).join("")}</div>
    <p class="slot-count">${open} of ${payload.slots.length} slots open</p>`;
}

function panelMarkup(doctor) {
  const { min, max } = dateBounds();
  return `
    <div class="booking-fee">
      <span class="text-soft" style="font-size: var(--text-sm)">Consultation fee</span>
      <b>${formatFee(doctor.fee)}</b>
    </div>

    <form id="bookingForm" novalidate>
      <div class="field">
        <label for="bookingDate">Choose a date</label>
        <input class="input" type="date" id="bookingDate" min="${min}" max="${max}" required />
      </div>

      <div class="field">
        <span class="field-label">Available times</span>
        <div id="slotArea" class="slot-area">
          <p class="slot-empty">Pick a date to see open slots.</p>
        </div>
      </div>

      <div class="field">
        <label for="bookingReason">Reason for the visit</label>
        <textarea class="input" id="bookingReason" rows="3" maxlength="500"
                  placeholder="Describe your symptoms briefly" required></textarea>
        <p class="field-hint">The doctor sees this before your appointment.</p>
      </div>

      <p class="field-error" id="bookingError" hidden></p>

      <button class="btn btn-primary btn-block btn-lg" type="submit" id="bookingSubmit" disabled>
        ${icon("calendar")} Confirm booking
      </button>
    </form>

    <p class="notice" style="margin-top: var(--space-4)">
      ${icon("info")}
      <span>Your slot is held as soon as you book. Online payment arrives in the
      next milestone — until then settle the fee at the hospital.</span>
    </p>`;
}

function confirmationMarkup(appointment) {
  const when = new Date(appointment.scheduled_for);
  const day = when.toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
  return `
    <div class="booking-done">
      <span class="booking-done-mark">${icon("check")}</span>
      <h3>Slot held</h3>
      <p><b>${escapeHtml(day)}</b> at <b>${formatTime(appointment.time)}</b></p>
      <p class="text-soft" style="font-size: var(--text-sm)">
        with ${escapeHtml(appointment.doctor?.name || "your doctor")}
      </p>
      <a class="btn btn-primary btn-block" href="appointments.html"
         style="margin-top: var(--space-4)">View my appointments</a>
      <button class="btn btn-ghost btn-block btn-sm" type="button" id="bookAnother"
              style="margin-top: var(--space-2)">Book another time</button>
    </div>`;
}

export function mountBooking(root, doctor, { onSignedOut }) {
  let selectedTime = null;

  root.innerHTML = panelMarkup(doctor);

  const form = root.querySelector("#bookingForm");
  const dateInput = root.querySelector("#bookingDate");
  const slotArea = root.querySelector("#slotArea");
  const reason = root.querySelector("#bookingReason");
  const submit = root.querySelector("#bookingSubmit");
  const errorLine = root.querySelector("#bookingError");

  function showError(message) {
    errorLine.textContent = message;
    errorLine.hidden = !message;
  }

  function refreshSubmit() {
    submit.disabled = !(selectedTime && reason.value.trim());
  }

  async function loadSlots(value) {
    selectedTime = null;
    refreshSubmit();
    slotArea.innerHTML = `<p class="slot-empty">Checking availability…</p>`;

    try {
      const payload = await getJson(
        `/doctors/${encodeURIComponent(doctor.id)}/slots?date=${encodeURIComponent(value)}`
      );
      slotArea.innerHTML = slotsMarkup(payload);
    } catch (error) {
      slotArea.innerHTML = `<p class="slot-empty">${escapeHtml(error.message)}</p>`;
    }
  }

  dateInput.addEventListener("change", () => {
    showError("");
    if (dateInput.value) loadSlots(dateInput.value);
  });

  // One delegated listener: the slot buttons are replaced on every date change.
  slotArea.addEventListener("click", (event) => {
    const button = event.target.closest(".slot");
    if (!button || button.disabled) return;
    slotArea.querySelectorAll(".slot").forEach((node) => node.classList.remove("is-selected"));
    button.classList.add("is-selected");
    selectedTime = button.dataset.time;
    showError("");
    refreshSubmit();
  });

  reason.addEventListener("input", refreshSubmit);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!selectedTime) return showError("Choose a time first.");

    submit.disabled = true;
    submit.textContent = "Booking…";
    showError("");

    try {
      const appointment = await postJson("/appointments", {
        doctor_id: doctor.id,
        date: dateInput.value,
        time: selectedTime,
        reason: reason.value.trim(),
      });
      root.innerHTML = confirmationMarkup(appointment);
      root
        .querySelector("#bookAnother")
        ?.addEventListener("click", () => mountBooking(root, doctor, { onSignedOut }));
      toast("Appointment booked.", "success");
      return;
    } catch (error) {
      if (error.status === 401) return onSignedOut();
      // 409 means someone took the slot between the grid loading and the
      // submit, so the grid on screen is stale and has to be refetched.
      if (error.status === 409 && dateInput.value) loadSlots(dateInput.value);
      showError(error.message);
    }

    submit.innerHTML = `${icon("calendar")} Confirm booking`;
    refreshSubmit();
  });
}

export function mountSignInPrompt(root, doctor) {
  const next = encodeURIComponent(`doctor.html?id=${doctor.id}`);
  root.innerHTML = `
    <div class="booking-fee">
      <span class="text-soft" style="font-size: var(--text-sm)">Consultation fee</span>
      <b>${formatFee(doctor.fee)}</b>
    </div>
    <p class="text-soft" style="margin: 0 0 var(--space-4); font-size: var(--text-sm)">
      Sign in to see open slots and book with ${escapeHtml(doctor.name)}.
    </p>
    <a class="btn btn-primary btn-block btn-lg" href="login.html?next=${next}">Sign in to book</a>
    <a class="btn btn-ghost btn-block btn-sm" href="register.html"
       style="margin-top: var(--space-2)">Create an account</a>`;
}
