import { apiFetch, getJson, escapeHtml, formatFee, formatTime, queryString } from "../api.js";
import { icon } from "../icons.js";
import { renderChrome } from "../ui/nav.js";
import { toast } from "../ui/toast.js";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const STATUS_VARIANT = { approved: "ok", pending: "warn", rejected: "danger" };

const state = { q: "", status: "", doctors: [], editingId: null };

const $ = (id) => document.getElementById(id);

/* ------------------------------------------------------------------ stats */

async function loadStats() {
  try {
    const stats = await getJson("/admin/stats");
    $("statRow").innerHTML = [
      ["Total doctors", stats.total],
      ["Approved", stats.approved],
      ["Pending", stats.pending],
      ["Specialties", stats.specialties],
    ]
      .map(([label, value]) => `<dl class="stat"><dt>${label}</dt><dd>${value}</dd></dl>`)
      .join("");
  } catch {
    $("statRow").innerHTML = "";
  }
}

/* ------------------------------------------------------------------ table */

function summariseAvailability(windows) {
  if (!windows?.length) return "Not set";
  const days = [...new Set(windows.map((w) => DAYS[w.day_of_week].slice(0, 3)))];
  return `${days.join(", ")} · ${formatTime(windows[0].start_time)}`;
}

function row(doctor) {
  const status = doctor.approval_status || "pending";
  return `
    <tr data-id="${doctor.id}">
      <td>
        <div class="cell-person">
          <span class="avatar">${escapeHtml(doctor.initials)}</span>
          <div>
            <strong>${escapeHtml(doctor.name)}</strong>
            <span>${escapeHtml(doctor.specialty?.name || "No specialty")}</span>
          </div>
        </div>
      </td>
      <td>
        <div>${escapeHtml(doctor.hospital)}</div>
        <span style="font-size:var(--text-xs);color:var(--text-soft)">${escapeHtml(doctor.location)}</span>
      </td>
      <td>${escapeHtml(summariseAvailability(doctor.availability))}</td>
      <td>${formatFee(doctor.fee)}</td>
      <td><span class="badge badge-${STATUS_VARIANT[status] || "neutral"}">${escapeHtml(status)}</span></td>
      <td>
        <div class="row-actions">
          ${
            status !== "approved"
              ? `<button class="btn btn-secondary btn-sm" data-action="approve" data-id="${doctor.id}">Approve</button>`
              : ""
          }
          <button class="btn btn-secondary btn-sm" data-action="edit" data-id="${doctor.id}">Edit</button>
          <button class="btn btn-ghost btn-sm" data-action="delete" data-id="${doctor.id}"
                  style="color:var(--danger-fg)">Delete</button>
        </div>
      </td>
    </tr>`;
}

async function loadDoctors() {
  const body = $("doctorRows");
  body.innerHTML = `<tr><td colspan="6" style="padding:var(--space-6)">
      <div class="skeleton skeleton-line" style="width:60%"></div>
      <div class="skeleton skeleton-line" style="width:45%"></div>
    </td></tr>`;

  try {
    state.doctors = await getJson(
      `/admin/doctors${queryString({ q: state.q, status: state.status })}`
    );
    if (!state.doctors.length) {
      body.innerHTML = `<tr><td colspan="6">
        <div class="empty-state" style="border:none;background:transparent">
          ${icon("inbox")}
          <h3>No doctors here yet</h3>
          <p>Use “Add doctor” to create the first profile.</p>
        </div></td></tr>`;
      return;
    }
    body.innerHTML = state.doctors.map(row).join("");
  } catch (error) {
    body.innerHTML = `<tr><td colspan="6">
      <div class="empty-state" style="border:none;background:transparent">
        ${icon("shield")}<h3>Could not load doctors</h3><p>${escapeHtml(error.message)}</p>
      </div></td></tr>`;
  }
}

async function refresh() {
  await Promise.all([loadStats(), loadDoctors()]);
}

/* ------------------------------------------------------------------ modal */

function availabilityEditor(windows = []) {
  const byDay = new Map(windows.map((w) => [w.day_of_week, w]));
  return DAYS.map((name, index) => {
    const w = byDay.get(index);
    return `
      <div class="availability-day">
        <label>
          <input type="checkbox" data-day="${index}" ${w ? "checked" : ""} />
          ${name}
        </label>
        <input type="time" data-start="${index}" value="${w?.start_time || "09:00"}" ${w ? "" : "disabled"} />
        <input type="time" data-end="${index}" value="${w?.end_time || "13:00"}" ${w ? "" : "disabled"} />
      </div>`;
  }).join("");
}

function openModal(doctor = null) {
  state.editingId = doctor?.id ?? null;
  $("modalTitle").textContent = doctor ? `Edit ${doctor.name}` : "Add a doctor";
  $("formAlert").className = "alert";

  const set = (id, value) => {
    $(id).value = value ?? "";
  };
  set("fName", doctor?.name);
  set("fSpecialty", doctor?.specialty?.name);
  set("fHospital", doctor?.hospital);
  set("fLocation", doctor?.location);
  set("fPhone", doctor?.phone);
  set("fFee", doctor?.fee);
  set("fExperience", doctor?.experience_years ?? 0);
  set("fQualification", doctor?.qualification);
  set("fBio", doctor?.bio);
  $("fStatus").value = doctor?.approval_status || "approved";

  $("availabilityEditor").innerHTML = availabilityEditor(doctor?.availability || []);
  $("availabilityEditor")
    .querySelectorAll('input[type="checkbox"]')
    .forEach((box) => {
      box.addEventListener("change", () => {
        const day = box.dataset.day;
        $("availabilityEditor").querySelector(`[data-start="${day}"]`).disabled = !box.checked;
        $("availabilityEditor").querySelector(`[data-end="${day}"]`).disabled = !box.checked;
      });
    });

  $("doctorModal").hidden = false;
  $("fName").focus();
}

function closeModal() {
  $("doctorModal").hidden = true;
  state.editingId = null;
  document.querySelectorAll(".field-error").forEach((n) => n.classList.remove("field-error"));
}

function collectAvailability() {
  const rows = [];
  $("availabilityEditor")
    .querySelectorAll('input[type="checkbox"]:checked')
    .forEach((box) => {
      const day = Number(box.dataset.day);
      rows.push({
        day_of_week: day,
        start_time: $("availabilityEditor").querySelector(`[data-start="${day}"]`).value,
        end_time: $("availabilityEditor").querySelector(`[data-end="${day}"]`).value,
      });
    });
  return rows;
}

function collectPayload() {
  return {
    name: $("fName").value.trim(),
    specialty: $("fSpecialty").value.trim(),
    hospital: $("fHospital").value.trim(),
    location: $("fLocation").value.trim(),
    phone: $("fPhone").value.trim(),
    fee: $("fFee").value,
    experience_years: $("fExperience").value || 0,
    qualification: $("fQualification").value.trim(),
    bio: $("fBio").value.trim(),
    approval_status: $("fStatus").value,
    availability: collectAvailability(),
  };
}

function showFieldErrors(fields) {
  document.querySelectorAll(".field-error").forEach((n) => n.classList.remove("field-error"));
  const map = {
    name: "fName",
    specialty: "fSpecialty",
    hospital: "fHospital",
    location: "fLocation",
    phone: "fPhone",
    fee: "fFee",
    experience_years: "fExperience",
  };
  Object.keys(fields || {}).forEach((key) => {
    $(map[key])?.closest(".field")?.classList.add("field-error");
  });
}

const REQUIRED = {
  fName: "Full name",
  fSpecialty: "Specialty",
  fHospital: "Hospital or clinic",
  fLocation: "Area",
  fPhone: "Phone",
  fFee: "Consultation fee",
};

/** Client-side pre-check. The server validates again and is the authority. */
function firstMissingField() {
  return Object.entries(REQUIRED).find(([id]) => !$(id).value.trim());
}

async function save(event) {
  event.preventDefault();

  const missing = firstMissingField();
  if (missing) {
    const [id, label] = missing;
    showFieldErrors({ [id]: true });
    $(id).closest(".field").classList.add("field-error");
    $("formAlert").className = "alert alert-error is-visible";
    $("formAlert").textContent = `${label} is required.`;
    $(id).focus();
    return;
  }

  const button = $("saveButton");
  button.disabled = true;
  button.textContent = "Saving\u2026";

  const editing = state.editingId;
  try {
    const response = await apiFetch(editing ? `/admin/doctors/${editing}` : "/admin/doctors", {
      method: editing ? "PUT" : "POST",
      body: JSON.stringify(collectPayload()),
    });
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      showFieldErrors(data.fields);
      $("formAlert").className = "alert alert-error is-visible";
      $("formAlert").textContent = data.error || `Could not save the doctor (${response.status})`;
      return;
    }

    closeModal();
    toast(editing ? "Doctor updated." : "Doctor added.", "success");
    await refresh();
  } catch (error) {
    $("formAlert").className = "alert alert-error is-visible";
    $("formAlert").textContent = error.message;
  } finally {
    button.disabled = false;
    button.textContent = "Save doctor";
  }
}

/* ----------------------------------------------------------------- actions */

async function approve(id) {
  try {
    await getJson(`/admin/doctors/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ approval_status: "approved" }),
    });
    toast("Doctor approved and published.", "success");
    await refresh();
  } catch (error) {
    toast(error.message, "error");
  }
}

async function remove(id) {
  const doctor = state.doctors.find((item) => item.id === id);
  if (!window.confirm(`Remove ${doctor?.name || "this doctor"} permanently?`)) return;
  try {
    await getJson(`/admin/doctors/${id}`, { method: "DELETE" });
    toast("Doctor removed.", "success");
    await refresh();
  } catch (error) {
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

/* -------------------------------------------------------------------- boot */

document.addEventListener("DOMContentLoaded", async () => {
  const user = await renderChrome();

  if (!user) {
    window.location.replace("login.html");
    return;
  }
  if (user.role !== "admin") {
    // The API enforces this too; this only avoids showing a console that
    // would fail every request.
    $("adminRoot").innerHTML = `
      <div class="empty-state">${icon("shield")}
        <h3>Administrators only</h3>
        <p>Your account does not have access to the admin console.</p>
        <a class="btn btn-secondary btn-sm" href="doctors.html"
           style="margin-top:var(--space-3)">Back to the directory</a>
      </div>`;
    return;
  }

  $("addButton").addEventListener("click", () => openModal());
  $("closeModal").addEventListener("click", closeModal);
  $("cancelModal").addEventListener("click", closeModal);
  $("doctorForm").addEventListener("submit", save);

  $("doctorModal").addEventListener("click", (event) => {
    if (event.target === $("doctorModal")) closeModal();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !$("doctorModal").hidden) closeModal();
  });

  $("adminSearch").addEventListener(
    "input",
    debounce(() => {
      state.q = $("adminSearch").value.trim();
      loadDoctors();
    })
  );
  $("statusFilter").addEventListener("change", () => {
    state.status = $("statusFilter").value;
    loadDoctors();
  });

  $("doctorRows").addEventListener("click", (event) => {
    const button = event.target.closest("[data-action]");
    if (!button) return;
    const id = Number(button.dataset.id);
    const action = button.dataset.action;
    if (action === "edit") openModal(state.doctors.find((item) => item.id === id));
    if (action === "approve") approve(id);
    if (action === "delete") remove(id);
  });

  await refresh();
});
