import { escapeHtml } from "../api.js";
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

const DEMO_DONORS = [
  {
    id: "BD-101",
    blood_group: "O+",
    area: "Laxmipur, Rajshahi",
    hospital_near: "Rajshahi Medical College Hospital",
    last_donation: "14 May 2026",
    days_ago: 129,
    donations_count: 7,
    status: "available",
    status_label: "Available Now",
    badge_class: "badge-ok",
  },
  {
    id: "BD-102",
    blood_group: "A+",
    area: "Kazla, Rajshahi",
    hospital_near: "RUET Medical Centre area",
    last_donation: "20 Jun 2026",
    days_ago: 92,
    donations_count: 4,
    status: "available",
    status_label: "Available Now",
    badge_class: "badge-ok",
  },
  {
    id: "BD-103",
    blood_group: "B+",
    area: "Talaimari, Rajshahi",
    hospital_near: "Barind Specialised Clinic",
    last_donation: "18 Aug 2026",
    days_ago: 33,
    donations_count: 9,
    status: "eligible_soon",
    status_label: "Eligible in 57 days",
    badge_class: "badge-warn",
  },
  {
    id: "BD-104",
    blood_group: "O-",
    area: "Upashahar, Rajshahi",
    hospital_near: "Padma Heart Centre",
    last_donation: "05 Feb 2026",
    days_ago: 227,
    donations_count: 5,
    status: "available",
    status_label: "Available Now",
    badge_class: "badge-ok",
  },
  {
    id: "BD-105",
    blood_group: "AB+",
    area: "Binodpur, Rajshahi",
    hospital_near: "Kazla Family Health",
    last_donation: "12 Apr 2026",
    days_ago: 161,
    donations_count: 3,
    status: "available",
    status_label: "Available Now",
    badge_class: "badge-ok",
  },
  {
    id: "BD-106",
    blood_group: "B-",
    area: "Shaheb Bazar, Rajshahi",
    hospital_near: "Rajshahi Central Medical",
    last_donation: "01 Sep 2026",
    days_ago: 19,
    donations_count: 6,
    status: "eligible_soon",
    status_label: "Eligible in 71 days",
    badge_class: "badge-warn",
  },
  {
    id: "BD-107",
    blood_group: "A-",
    area: "Vodra, Rajshahi",
    hospital_near: "Barind Orthopedic Centre",
    last_donation: "First-time donor",
    days_ago: null,
    donations_count: 0,
    status: "available",
    status_label: "Available (New)",
    badge_class: "badge-ok",
  },
  {
    id: "BD-108",
    blood_group: "AB-",
    area: "Court, Rajshahi",
    hospital_near: "Padma General Hospital",
    last_donation: "10 Mar 2026",
    days_ago: 194,
    donations_count: 8,
    status: "available",
    status_label: "Available Now",
    badge_class: "badge-ok",
  },
];

let selectedGroup = "";
let selectedStatus = "";
let searchKeyword = "";

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
      renderDonors();
    });
  });
}

function donorCard(donor) {
  return `
    <article class="donor-card" data-id="${escapeHtml(donor.id)}">
      <div class="donor-card-head">
        <div class="donor-identity">
          <span class="donor-avatar">${escapeHtml(donor.blood_group)}</span>
          <div>
            <h3 style="margin:0 0 var(--space-1);font-size:var(--text-base)">Donor #${escapeHtml(donor.id)}</h3>
            <span class="badge ${donor.badge_class}">${escapeHtml(donor.status_label)}</span>
          </div>
        </div>
        <span class="blood-type-pill">${escapeHtml(donor.blood_group)}</span>
      </div>

      <ul class="donor-meta">
        <li>
          ${icon("pin")}
          <span>${escapeHtml(donor.area)}</span>
        </li>
        <li>
          ${icon("hospital")}
          <span>Near ${escapeHtml(donor.hospital_near)}</span>
        </li>
        <li>
          ${icon("calendar")}
          <span>Last donated: <strong>${escapeHtml(donor.last_donation)}</strong></span>
        </li>
        <li>
          ${icon("heart")}
          <span>Total: <strong>${donor.donations_count} lifetime donation${donor.donations_count === 1 ? "" : "s"}</strong></span>
        </li>
      </ul>

      <div class="privacy-notice-box">
        ${icon("lock")}
        <span>Phone number protected for donor privacy</span>
      </div>

      <div class="donor-card-foot">
        <span style="font-size:var(--text-xs);color:var(--text-faint)">Rajshahi Verified</span>
        <button class="btn btn-primary btn-sm request-btn" type="button" data-id="${escapeHtml(donor.id)}" data-group="${escapeHtml(donor.blood_group)}">
          ${icon("phone")}
          Request Contact
        </button>
      </div>
    </article>
  `;
}

function renderDonors() {
  const grid = document.getElementById("donorGrid");
  const summary = document.getElementById("resultSummary");
  if (!grid) return;

  const filtered = DEMO_DONORS.filter((donor) => {
    if (selectedGroup && donor.blood_group !== selectedGroup) return false;
    if (selectedStatus && donor.status !== selectedStatus) return false;
    if (searchKeyword) {
      const q = searchKeyword.toLowerCase();
      const match =
        donor.id.toLowerCase().includes(q) ||
        donor.area.toLowerCase().includes(q) ||
        donor.hospital_near.toLowerCase().includes(q) ||
        donor.blood_group.toLowerCase().includes(q);
      if (!match) return false;
    }
    return true;
  });

  if (summary) {
    summary.textContent = `Showing ${filtered.length} donor${filtered.length === 1 ? "" : "s"} in Rajshahi`;
  }

  if (!filtered.length) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        ${icon("inbox")}
        <h3>No donors matched your filter</h3>
        <p>Try clearing your search keyword or selecting "All groups".</p>
      </div>
    `;
    return;
  }

  grid.innerHTML = filtered.map(donorCard).join("");

  grid.querySelectorAll(".request-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-id");
      const group = btn.getAttribute("data-group");
      openRequestModal(id, group);
    });
  });
}

function openRequestModal(donorId, group) {
  const modal = document.getElementById("requestModal");
  if (!modal) return;
  document.getElementById("modalDonorId").textContent = `Donor #${donorId} (${group})`;
  modal.hidden = false;
}

function closeRequestModal() {
  const modal = document.getElementById("requestModal");
  if (modal) modal.hidden = true;
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

  form?.addEventListener("submit", (e) => {
    e.preventDefault();
    const donorCode = document.getElementById("modalDonorId").textContent;
    closeRequestModal();
    showToast(
      `Secure contact request dispatched to ${donorCode}. The donor will be notified via SMS/App.`,
      "success"
    );
    form.reset();
  });
}

function setupRegistrationForm() {
  const form = document.getElementById("donorRegForm");
  form?.addEventListener("submit", (e) => {
    e.preventDefault();
    const name = document.getElementById("regName").value || "Donor";
    showToast(
      `Thank you, ${name}! Your voluntary donor profile has been registered (Preview).`,
      "success"
    );
    form.reset();
  });
}

function setupFilters() {
  const searchInput = document.getElementById("donorSearchInput");
  const groupSelect = document.getElementById("bloodGroupFilter");
  const statusSelect = document.getElementById("statusFilter");

  searchInput?.addEventListener("input", (e) => {
    searchKeyword = e.target.value.trim();
    renderDonors();
  });

  groupSelect?.addEventListener("change", (e) => {
    selectedGroup = e.target.value;
    renderChips();
    renderDonors();
  });

  statusSelect?.addEventListener("change", (e) => {
    selectedStatus = e.target.value;
    renderDonors();
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
  renderDonors();
  renderCompatibilityTable();
  setupFilters();
  setupModal();
  setupRegistrationForm();
});
