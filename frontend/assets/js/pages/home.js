import { getJson, escapeHtml } from "../api.js";
import { icon, specialtyIcon } from "../icons.js";
import { renderChrome } from "../ui/nav.js";

function tile(specialty) {
  return `
    <a class="specialty-tile" href="doctors.html?specialty=${encodeURIComponent(specialty.slug)}">
      <span class="tile-icon">${specialtyIcon(specialty.slug)}</span>
      <strong>${escapeHtml(specialty.name)}</strong>
      <span>${specialty.doctor_count} doctor${specialty.doctor_count === 1 ? "" : "s"} available</span>
    </a>`;
}

async function loadSpecialties() {
  const target = document.getElementById("specialtyGrid");
  if (!target) return;
  try {
    const specialties = await getJson("/specialties");
    if (!specialties.length) {
      target.innerHTML = `
        <div class="empty-state" style="grid-column:1/-1">
          ${icon("inbox")}
          <h3>No specialties yet</h3>
          <p>Run <code>flask --app wsgi seed</code> in the backend folder to load demo data.</p>
        </div>`;
      return;
    }
    target.innerHTML = specialties.map(tile).join("");
  } catch {
    target.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        ${icon("shield")}
        <h3>Cannot reach the API</h3>
        <p>Start the backend with <code>flask --app wsgi run --port 5000</code> and reload.</p>
      </div>`;
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  await renderChrome();
  loadSpecialties();
});
