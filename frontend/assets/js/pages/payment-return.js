/* Where SSLCommerz sends the patient back.

   This page reports an outcome the server has already decided. It never
   decides one itself: the query string here came back through the patient's
   browser, so it is a claim, not evidence. `?status=` only chooses which
   message to show — the appointment is then re-fetched from the API, and
   that answer is what the page displays. */

import { getJson, escapeHtml, formatFee, formatTime } from "../api.js";
import { icon } from "../icons.js";
import { renderChrome } from "../ui/nav.js";

const OUTCOMES = {
  paid: {
    icon: "check",
    tone: "ok",
    title: "Payment received",
    body: "Your appointment is confirmed. The doctor can now see it on their schedule.",
  },
  failed: {
    icon: "alert",
    tone: "bad",
    title: "Payment could not be confirmed",
    body: "Nothing has been charged to your card. You can try again from your appointments.",
  },
  cancel: {
    icon: "close",
    tone: "warn",
    title: "Payment cancelled",
    body: "You stopped before paying. Your slot is still held for a short while.",
  },
  fail: {
    icon: "alert",
    tone: "bad",
    title: "Payment failed",
    body: "Your bank or card issuer declined the payment. Nothing has been charged.",
  },
};

function card(outcome, detail, appointment) {
  const when = appointment
    ? new Date(appointment.scheduled_for).toLocaleDateString(undefined, {
        weekday: "long",
        day: "numeric",
        month: "long",
      })
    : null;

  return `
    <div class="result-card result-${outcome.tone}">
      <span class="result-mark">${icon(outcome.icon)}</span>
      <h1>${escapeHtml(outcome.title)}</h1>
      <p>${escapeHtml(detail || outcome.body)}</p>

      ${
        appointment
          ? `<dl class="result-facts">
               <div><dt>Doctor</dt><dd>${escapeHtml(
                 appointment.doctor?.name || "Your doctor"
               )}</dd></div>
               <div><dt>When</dt><dd>${escapeHtml(when)} at ${escapeHtml(
                 formatTime(appointment.time)
               )}</dd></div>
               <div><dt>Fee</dt><dd>${formatFee(appointment.fee)}</dd></div>
               <div><dt>Status</dt><dd>${escapeHtml(
                 appointment.payment_status === "paid" ? "Paid" : "Not paid"
               )}</dd></div>
             </dl>`
          : ""
      }

      <div class="result-actions">
        <a class="btn btn-primary" href="appointments.html">Go to my appointments</a>
        <a class="btn btn-ghost" href="doctors.html">Find another doctor</a>
      </div>
    </div>`;
}

document.addEventListener("DOMContentLoaded", async () => {
  await renderChrome();

  const params = new URLSearchParams(window.location.search);
  const claimed = params.get("status") || "failed";
  const outcome = OUTCOMES[claimed] || OUTCOMES.failed;
  const detail = params.get("message");
  const id = params.get("appointment");

  let appointment = null;
  if (id) {
    try {
      appointment = await getJson(`/appointments/${encodeURIComponent(id)}`);
    } catch {
      // Signed out, or not their appointment. The outcome message still
      // stands on its own.
    }
  }

  // The server's record wins over the query string in both directions: a
  // browser claiming success for an unpaid appointment is corrected here,
  // and so is a redirect that lost its parameters after a real payment.
  let resolved = outcome;
  if (appointment) {
    if (appointment.payment_status === "paid" && claimed !== "paid") {
      resolved = OUTCOMES.paid;
    } else if (appointment.payment_status !== "paid" && claimed === "paid") {
      resolved = OUTCOMES.failed;
    }
  }

  document.getElementById("resultRoot").innerHTML = card(
    resolved,
    resolved === outcome ? detail : null,
    appointment
  );
});
