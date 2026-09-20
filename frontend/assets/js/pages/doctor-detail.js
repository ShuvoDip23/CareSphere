import { getJson, escapeHtml, formatFee, formatTime } from "../api.js";
import { icon, stars } from "../icons.js";
import { renderChrome } from "../ui/nav.js";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function scheduleRows(availability) {
  const byDay = new Map();
  availability.forEach((slot) => {
    if (!byDay.has(slot.day_of_week)) byDay.set(slot.day_of_week, []);
    byDay.get(slot.day_of_week).push(slot);
  });

  return DAYS.map((name, index) => {
    const windows = byDay.get(index) || [];
    if (!windows.length) {
      return `<div class="schedule-row is-off"><strong>${name}</strong><span>Not consulting</span></div>`;
    }
    const text = windows
      .map((slot) => `${formatTime(slot.start_time)} \u2013 ${formatTime(slot.end_time)}`)
      .join(", ");
    return `<div class="schedule-row"><strong>${name}</strong><span>${escapeHtml(text)}</span></div>`;
  }).join("");
}

function render(doctor) {
  const root = document.getElementById("doctorDetail");
  const specialty = doctor.specialty?.name || "Specialist";
  document.title = `${doctor.name} — CareSphere`;

  root.innerHTML = `
    <div>
      <article class="card">
        <div class="detail-header">
          <span class="avatar avatar-lg">${escapeHtml(doctor.initials)}</span>
          <div style="flex:1;min-width:14rem">
            <h1>${escapeHtml(doctor.name)}</h1>
            <div class="cluster" style="gap:var(--space-2)">
              <span class="badge badge-accent">${escapeHtml(specialty)}</span>
              <span class="rating-inline">${stars(doctor.rating)}
                <b>${doctor.rating.toFixed(1)}</b>
                <span>(${doctor.review_count} reviews)</span>
              </span>
            </div>
            ${
              doctor.qualification
                ? `<p class="text-soft" style="margin:var(--space-3) 0 0;font-size:var(--text-sm)">${escapeHtml(
                    doctor.qualification
                  )}</p>`
                : ""
            }
          </div>
        </div>

        <dl class="fact-grid">
          <div class="fact"><dt>Hospital</dt><dd>${escapeHtml(doctor.hospital)}</dd></div>
          <div class="fact"><dt>Location</dt><dd>${escapeHtml(doctor.location)}</dd></div>
          <div class="fact"><dt>Experience</dt><dd>${
            doctor.experience_years > 0 ? `${doctor.experience_years} years` : "Not listed"
          }</dd></div>
          <div class="fact"><dt>Contact</dt><dd>${escapeHtml(doctor.phone)}</dd></div>
        </dl>
      </article>

      ${
        doctor.bio
          ? `<article class="card" style="margin-top:var(--space-5)">
               <h2 style="font-size:var(--text-lg)">About</h2>
               <p class="text-soft" style="margin:0">${escapeHtml(doctor.bio)}</p>
             </article>`
          : ""
      }

      <article class="card" style="margin-top:var(--space-5)">
        <h2 style="font-size:var(--text-lg)">Weekly consulting hours</h2>
        <div class="schedule">${scheduleRows(doctor.availability || [])}</div>
      </article>
    </div>

    <aside class="card booking-card">
      <div class="booking-fee">
        <span class="text-soft" style="font-size:var(--text-sm)">Consultation fee</span>
        <b>${formatFee(doctor.fee)}</b>
      </div>
      <button class="btn btn-primary btn-block btn-lg" type="button" disabled>
        ${icon("calendar")} Book appointment
      </button>
      <p class="notice" style="margin-top:var(--space-4)">
        ${icon("info")}
        <span>Online booking and payment arrive in the next milestone. Until then,
        contact the hospital directly using the number above.</span>
      </p>
    </aside>`;
}

function renderMissing(message) {
  document.getElementById("doctorDetail").innerHTML = `
    <div class="empty-state" style="grid-column:1/-1">
      ${icon("search")}
      <h3>Doctor profile unavailable</h3>
      <p>${escapeHtml(message)}</p>
      <a class="btn btn-secondary btn-sm" href="doctors.html" style="margin-top:var(--space-3)">
        Back to directory
      </a>
    </div>`;
}

document.addEventListener("DOMContentLoaded", async () => {
  await renderChrome();

  const id = new URLSearchParams(window.location.search).get("id");
  if (!id) {
    window.location.replace("doctors.html");
    return;
  }

  try {
    render(await getJson(`/doctors/${encodeURIComponent(id)}`));
  } catch (error) {
    renderMissing(
      error.status === 404
        ? "This profile may still be awaiting approval, or it no longer exists."
        : error.message
    );
  }
});
