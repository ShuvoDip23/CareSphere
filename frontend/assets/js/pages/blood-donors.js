import { escapeHtml, getJson, postJson, queryString } from "../api.js";
import { icon } from "../icons.js";
import { renderChrome } from "../ui/nav.js";
import { toast as showToast } from "../ui/toast.js";

const BLOOD_COMPATIBILITY = {
  "O-": {
    give: ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],
    receive: ["O-"],
    note: "Universal Red Cell Donor",
  },
  "O+": {
    give: ["O+", "A+", "B+", "AB+"],
    receive: ["O+", "O-"],
    note: "Most commonly needed blood group",
  },
  "A-": {
    give: ["A-", "A+", "AB-", "AB+"],
    receive: ["A-", "O-"],
    note: "Rare Rh-negative blood type",
  },
  "A+": {
    give: ["A+", "AB+"],
    receive: ["A+", "A-", "O+", "O-"],
    note: "Second most common blood group",
  },
  "B-": {
    give: ["B-", "B+", "AB-", "AB+"],
    receive: ["B-", "O-"],
    note: "Rare Rh-negative blood type",
  },
  "B+": {
    give: ["B+", "AB+"],
    receive: ["B+", "B-", "O+", "O-"],
    note: "Highly prevalent in Bangladesh",
  },
  "AB-": {
    give: ["AB-", "AB+"],
    receive: ["AB-", "A-", "B-", "O-"],
    note: "Very rare blood type",
  },
  "AB+": {
    give: ["AB+"],
    receive: ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],
    note: "Universal Red Cell Recipient",
  },
};

let selectedGroup = "";
let selectedStatus = "";
let searchKeyword = "";
let currentRequestDonor = null;
let debounceTimer = null;

function renderChips() {
  const container = document.getElementById("bloodChipRow");
  if (!container) return;

  const groups = ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];
  container.innerHTML = groups
    .map((grp) => {
      const active = selectedGroup === grp;
      const label = grp ? grp : "All groups";
      return `<button class="chip" type="button" data-group="${escapeHtml(grp)}" aria-pressed="${active}">${escapeHtml(label)}</button>`;
    })
    .join("");

  container.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => {
      selectedGroup = btn.getAttribute("data-group") || "";
      const select = document.getElementById("bloodGroupFilter");
      if (select) select.value = selectedGroup;
      renderChips();
      fetchDonors();
    });
  });
}

function donorCard(donor) {
  const displayId = donor.display_id || `BD-${donor.id}`;
  const hospitalInfo = donor.hospital_near
    ? `<li>${icon("hospital")}<span>Near ${escapeHtml(donor.hospital_near)}</span></li>`
    : "";

  return `
    <article class="donor-card" data-id="${escapeHtml(donor.id)}">
      <div class="donor-card-head">
        <div class="donor-identity">
          <span class="donor-avatar">${escapeHtml(donor.blood_group)}</span>
          <div>
            <h3 style="margin:0 0 var(--space-1);font-size:var(--text-base)">Donor #${escapeHtml(displayId)}</h3>
            <span class="badge ${escapeHtml(donor.badge_class || "badge-ok")}">${escapeHtml(donor.status_label || "Available")}</span>
          </div>
        </div>
        <span class="blood-type-pill">${escapeHtml(donor.blood_group)}</span>
      </div>

      <ul class="donor-meta">
        <li>
          ${icon("pin")}
          <span>${escapeHtml(donor.area)}</span>
        </li>
        ${hospitalInfo}
        <li>
          ${icon("calendar")}
          <span>Last donated: <strong>${escapeHtml(donor.last_donation || "First-time donor")}</strong></span>
        </li>
        <li>
          ${icon("heart")}
          <span>Total: <strong>${donor.donations_count || 0} lifetime donation${donor.donations_count === 1 ? "" : "s"}</strong></span>
        </li>
      </ul>

      <div class="privacy-notice-box">
        ${icon("lock")}
        <span>Phone number protected for donor privacy</span>
      </div>

      <div class="donor-card-foot">
        <span style="font-size:var(--text-xs);color:var(--text-faint)">Rajshahi Verified</span>
        <button class="btn btn-primary btn-sm request-btn" type="button" data-id="${escapeHtml(donor.id)}" data-display-id="${escapeHtml(displayId)}" data-group="${escapeHtml(donor.blood_group)}">
          ${icon("phone")}
          Request Contact
        </button>
      </div>
    </article>
  `;
}

async function fetchDonors() {
  const grid = document.getElementById("donorGrid");
  const summary = document.getElementById("resultSummary");
  if (!grid) return;

  if (summary) {
    summary.textContent = "Loading donors in Rajshahi…";
  }

  const params = {};
  if (selectedGroup) params.blood_group = selectedGroup;
  if (selectedStatus) params.status = selectedStatus;
  if (searchKeyword) params.q = searchKeyword;

  try {
    const data = await getJson("/donors" + queryString(params));
    const items = data.items || [];

    if (summary) {
      summary.textContent = `Showing ${items.length} voluntary donor${items.length === 1 ? "" : "s"} in Rajshahi`;
    }

    if (!items.length) {
      grid.innerHTML = `
        <div class="empty-state" style="grid-column:1/-1">
          ${icon("inbox")}
          <h3>No donors matched your filter</h3>
          <p>Try clearing your search keyword or selecting "All blood groups".</p>
          <button class="btn btn-secondary btn-sm" id="clearFiltersBtn" type="button" style="margin-top:var(--space-2)">
            Clear Filters
          </button>
        </div>
      `;
      document.getElementById("clearFiltersBtn")?.addEventListener("click", () => {
        selectedGroup = "";
        selectedStatus = "";
        searchKeyword = "";
        const searchInput = document.getElementById("donorSearchInput");
        const groupSelect = document.getElementById("bloodGroupFilter");
        const statusSelect = document.getElementById("statusFilter");
        if (searchInput) searchInput.value = "";
        if (groupSelect) groupSelect.value = "";
        if (statusSelect) statusSelect.value = "";
        renderChips();
        fetchDonors();
      });
      return;
    }

    grid.innerHTML = items.map(donorCard).join("");

    grid.querySelectorAll(".request-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-id");
        const displayId = btn.getAttribute("data-display-id");
        const group = btn.getAttribute("data-group");
        openRequestModal(id, displayId, group);
      });
    });
  } catch (err) {
    console.error("Failed to load blood donors:", err);
    if (summary) {
      summary.textContent = "Failed to load donors";
    }
    grid.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        ${icon("inbox")}
        <h3>Unable to load donor registry</h3>
        <p style="color:var(--text-soft)">${escapeHtml(err.message || "Network error. Please make sure the backend server is running.")}</p>
        <button class="btn btn-secondary btn-sm" id="retryDonorsBtn" type="button" style="margin-top:var(--space-3)">
          Retry Search
        </button>
      </div>
    `;
    document.getElementById("retryDonorsBtn")?.addEventListener("click", () => fetchDonors());
  }
}

function openRequestModal(donorId, displayId, group) {
  currentRequestDonor = { id: donorId, displayId, group };
  const modal = document.getElementById("requestModal");
  if (!modal) return;
  const donorLabel = document.getElementById("modalDonorId");
  if (donorLabel) {
    donorLabel.textContent = `Donor #${displayId} (${group})`;
  }
  modal.hidden = false;
}

function closeRequestModal() {
  const modal = document.getElementById("requestModal");
  if (modal) modal.hidden = true;
  currentRequestDonor = null;
}

function setupModal() {
  const modal = document.getElementById("requestModal");
  const closeBtn = document.getElementById("modalCloseBtn");
  const cancelBtn = document.getElementById("modalCancelBtn");
  const form = document.getElementById("requestForm");

  closeBtn?.addEventListener("click", closeRequestModal);
  cancelBtn?.addEventListener("click", closeRequestModal);

  modal?.addEventListener("click", (e) => {
    if (e.target === modal) closeRequestModal();
  });

  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!currentRequestDonor) return;

    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn ? submitBtn.innerHTML : "Send Secure Request";

    const payload = {
      patient_name: document.getElementById("reqPatientName").value.trim(),
      hospital: document.getElementById("reqHospital").value.trim(),
      units: parseInt(document.getElementById("reqUnits").value, 10) || 1,
      urgency: document.getElementById("reqUrgency").value,
      requester_phone: document.getElementById("reqPhone").value.trim(),
      notes: document.getElementById("reqNotes").value.trim() || undefined,
    };

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.setAttribute("aria-busy", "true");
      submitBtn.textContent = "Dispatching request…";
    }

    try {
      const res = await postJson(`/donors/${currentRequestDonor.id}/requests`, payload);
      const donorDisplay = currentRequestDonor.displayId;
      closeRequestModal();
      showToast(
        res.message || `Secure contact request dispatched to Donor #${donorDisplay}.`,
        "success"
      );
      form.reset();
    } catch (err) {
      showToast(err.message || "Failed to dispatch request. Please check required fields.", "error");
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.removeAttribute("aria-busy");
        submitBtn.innerHTML = originalText;
      }
    }
  });
}

function setupRegistrationForm() {
  const form = document.getElementById("donorRegForm");
  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn ? submitBtn.innerHTML : "Register as Donor";

    const payload = {
      name: document.getElementById("regName").value.trim(),
      blood_group: document.getElementById("regBloodGroup").value,
      area: document.getElementById("regArea").value,
      phone: document.getElementById("regPhone").value.trim(),
      hospital_near: document.getElementById("regHospitalNear").value.trim() || undefined,
      last_donation_date: document.getElementById("regLastDate").value || undefined,
      is_available: document.getElementById("regAvailable").checked,
    };

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.setAttribute("aria-busy", "true");
      submitBtn.textContent = "Registering profile…";
    }

    try {
      const res = await postJson("/donors", payload);
      const donorCode = res.donor?.display_id ? `(#${res.donor.display_id}) ` : "";
      showToast(
        res.message || `Thank you! Your voluntary donor profile ${donorCode}has been registered.`,
        "success"
      );
      form.reset();
      // Refresh donor list immediately so new donor is shown
      await fetchDonors();
    } catch (err) {
      showToast(err.message || "Registration failed. Please check your inputs.", "error");
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.removeAttribute("aria-busy");
        submitBtn.innerHTML = originalText;
      }
    }
  });
}

function setupFilters() {
  const searchInput = document.getElementById("donorSearchInput");
  const groupSelect = document.getElementById("bloodGroupFilter");
  const statusSelect = document.getElementById("statusFilter");

  searchInput?.addEventListener("input", (e) => {
    clearTimeout(debounceTimer);
    searchKeyword = e.target.value.trim();
    debounceTimer = setTimeout(() => {
      fetchDonors();
    }, 250);
  });

  groupSelect?.addEventListener("change", (e) => {
    selectedGroup = e.target.value;
    renderChips();
    fetchDonors();
  });

  statusSelect?.addEventListener("change", (e) => {
    selectedStatus = e.target.value;
    fetchDonors();
  });
}

function renderCompatibilityTable() {
  const tbody = document.getElementById("compatTableBody");
  if (!tbody) return;

  const rows = Object.entries(BLOOD_COMPATIBILITY)
    .map(([group, info]) => {
      const giveBadges = info.give
        .map((g) => `<span class="compat-tag">${escapeHtml(g)}</span>`)
        .join(" ");
      const receiveBadges = info.receive
        .map((r) => `<span class="compat-tag is-match">${escapeHtml(r)}</span>`)
        .join(" ");

      return `
        <tr>
          <td><span class="blood-type-pill">${escapeHtml(group)}</span></td>
          <td><div class="compat-tags">${giveBadges}</div></td>
          <td><div class="compat-tags">${receiveBadges}</div></td>
          <td style="color:var(--text-soft);font-size:var(--text-xs)">${escapeHtml(info.note)}</td>
        </tr>
      `;
    })
    .join("");

  tbody.innerHTML = rows;
}

document.addEventListener("DOMContentLoaded", async () => {
  await renderChrome();
  renderChips();
  renderCompatibilityTable();
  setupFilters();
  setupModal();
  setupRegistrationForm();
  await fetchDonors();
});
