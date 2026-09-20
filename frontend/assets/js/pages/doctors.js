import { getJson, escapeHtml, queryString, formatFee } from "../api.js";
import { icon, stars } from "../icons.js";
import { renderChrome } from "../ui/nav.js";
import { toast } from "../ui/toast.js";

const state = { q: "", specialty: "", sort: "rating", page: 1 };
let specialties = [];

const grid = () => document.getElementById("doctorGrid");

function readUrl() {
  const params = new URLSearchParams(window.location.search);
  state.q = params.get("q") || "";
  state.specialty = params.get("specialty") || "";
  state.sort = params.get("sort") || "rating";
  state.page = Number(params.get("page")) || 1;
}

function writeUrl() {
  const search = queryString({
    q: state.q,
    specialty: state.specialty,
    sort: state.sort === "rating" ? "" : state.sort,
    page: state.page > 1 ? state.page : "",
  });
  window.history.replaceState({}, "", `${window.location.pathname}${search}`);
}

function skeletonCards(count = 6) {
  return Array.from(
    { length: count },
    () => `
      <div class="doctor-card" aria-hidden="true">
        <div class="doctor-card-head">
          <div class="skeleton" style="width:48px;height:48px;border-radius:var(--radius-md)"></div>
          <div style="flex:1">
            <div class="skeleton skeleton-line" style="width:60%"></div>
            <div class="skeleton skeleton-line" style="width:35%"></div>
          </div>
        </div>
        <div>
          <div class="skeleton skeleton-line" style="width:85%"></div>
          <div class="skeleton skeleton-line" style="width:70%"></div>
          <div class="skeleton skeleton-line" style="width:50%"></div>
        </div>
        <div class="doctor-card-foot">
          <div class="skeleton skeleton-line" style="width:6rem"></div>
          <div class="skeleton skeleton-line" style="width:4rem"></div>
        </div>
      </div>`
  ).join("");
}

function card(doctor) {
  const specialty = doctor.specialty?.name || "Specialist";
  return `
    <a class="doctor-card" href="doctor.html?id=${doctor.id}">
      <div class="doctor-card-head">
        <span class="avatar">${escapeHtml(doctor.initials)}</span>
        <div style="flex:1;min-width:0">
          <h3>${escapeHtml(doctor.name)}</h3>
          <span class="badge badge-accent">${escapeHtml(specialty)}</span>
        </div>
      </div>
      <ul class="plain doctor-meta">
        <li>${icon("hospital")}<span>${escapeHtml(doctor.hospital)}</span></li>
        <li>${icon("pin")}<span>${escapeHtml(doctor.location)}</span></li>
        <li>${icon("calendar")}<span>${
          doctor.experience_years > 0
            ? `${doctor.experience_years} years experience`
            : "Experience not listed"
        }</span></li>
      </ul>
      <div class="doctor-card-foot">
        <span class="rating-inline">
          ${stars(doctor.rating)}
          <b>${doctor.rating.toFixed(1)}</b>
          <span>(${doctor.review_count})</span>
        </span>
        <span class="fee-pill">${formatFee(doctor.fee)}<small>consultation</small></span>
      </div>
    </a>`;
}

function renderChips() {
  const row = document.getElementById("chipRow");
  if (!row) return;
  const all = [{ slug: "", name: "All specialties" }, ...specialties];
  row.innerHTML = all
    .map(
      (item) =>
        `<button class="chip" type="button" data-slug="${escapeHtml(item.slug)}"
          aria-pressed="${item.slug === state.specialty}">${escapeHtml(item.name)}</button>`
    )
    .join("");

  row.querySelectorAll("[data-slug]").forEach((button) => {
    button.addEventListener("click", () => {
      state.specialty = button.dataset.slug;
      state.page = 1;
      document.getElementById("specialtyFilter").value = state.specialty;
      load();
    });
  });
}

function renderPagination(meta) {
  const target = document.getElementById("pagination");
  if (!target) return;
  if (meta.pages <= 1) {
    target.innerHTML = "";
    return;
  }
  target.innerHTML = `
    <button class="btn btn-secondary btn-sm" type="button" id="prevPage" ${
      meta.has_prev ? "" : "disabled"
    }>Previous</button>
    <span>Page ${meta.page} of ${meta.pages}</span>
    <button class="btn btn-secondary btn-sm" type="button" id="nextPage" ${
      meta.has_next ? "" : "disabled"
    }>Next</button>`;

  document.getElementById("prevPage")?.addEventListener("click", () => {
    state.page -= 1;
    load();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
  document.getElementById("nextPage")?.addEventListener("click", () => {
    state.page += 1;
    load();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
}

async function load() {
  const target = grid();
  const summary = document.getElementById("resultSummary");
  if (!target) return;

  writeUrl();
  target.innerHTML = skeletonCards();
  if (summary) summary.textContent = "Searching\u2026";

  try {
    const data = await getJson(
      `/doctors${queryString({
        q: state.q,
        specialty: state.specialty,
        sort: state.sort,
        page: state.page,
      })}`
    );

    document.querySelectorAll("#chipRow .chip").forEach((chip) => {
      chip.setAttribute("aria-pressed", String(chip.dataset.slug === state.specialty));
    });

    if (!data.items.length) {
      target.innerHTML = `
        <div class="empty-state" style="grid-column:1/-1">
          ${icon("search")}
          <h3>No doctors match your search</h3>
          <p>Try a different specialty, or clear the search box to see everyone.</p>
          <button class="btn btn-secondary btn-sm" type="button" id="clearFilters"
                  style="margin-top:var(--space-3)">Clear filters</button>
        </div>`;
      document.getElementById("clearFilters")?.addEventListener("click", () => {
        state.q = "";
        state.specialty = "";
        state.page = 1;
        document.getElementById("searchInput").value = "";
        document.getElementById("specialtyFilter").value = "";
        load();
      });
      if (summary) summary.textContent = "No results";
      renderPagination(data);
      return;
    }

    target.innerHTML = data.items.map(card).join("");
    if (summary) {
      summary.textContent = `${data.total} doctor${data.total === 1 ? "" : "s"} found`;
    }
    renderPagination(data);
  } catch (error) {
    target.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        ${icon("shield")}
        <h3>Could not load the directory</h3>
        <p>Check that the backend is running, then try again.</p>
      </div>`;
    if (summary) summary.textContent = "";
    toast(error.message, "error");
  }
}

function debounce(fn, wait = 280) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

document.addEventListener("DOMContentLoaded", async () => {
  await renderChrome();
  readUrl();

  const search = document.getElementById("searchInput");
  const filter = document.getElementById("specialtyFilter");
  const sort = document.getElementById("sortSelect");

  search.value = state.q;
  sort.value = state.sort;

  try {
    specialties = await getJson("/specialties");
    filter.innerHTML =
      '<option value="">All specialties</option>' +
      specialties
        .map(
          (item) =>
            `<option value="${escapeHtml(item.slug)}">${escapeHtml(item.name)} (${item.doctor_count})</option>`
        )
        .join("");
    filter.value = state.specialty;
    renderChips();
  } catch {
    /* the directory still works without the filter list */
  }

  search.addEventListener(
    "input",
    debounce(() => {
      state.q = search.value.trim();
      state.page = 1;
      load();
    })
  );

  filter.addEventListener("change", () => {
    state.specialty = filter.value;
    state.page = 1;
    load();
  });

  sort.addEventListener("change", () => {
    state.sort = sort.value;
    state.page = 1;
    load();
  });

  load();
});
