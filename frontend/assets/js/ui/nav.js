/* Shared site chrome. Rendered from one module so the header and footer
   cannot drift between pages, which is what happened in the prototype. */

import { apiFetch, getJson, escapeHtml } from "../api.js";
import { icon } from "../icons.js";

const LINKS = [
  { href: "index.html", label: "Home" },
  { href: "doctors.html", label: "Find doctors" },
  { href: "admin.html", label: "Admin", roles: ["admin"] },
];

/** Where a user belongs immediately after signing in. */
export function homeFor(user) {
  if (user?.role === "admin") return "admin.html";
  return "doctors.html";
}

function visibleLinks(user) {
  return LINKS.filter((link) => !link.roles || link.roles.includes(user?.role));
}

let cachedUser;

/** Resolve the signed-in user once per page load. */
export async function loadCurrentUser() {
  if (cachedUser !== undefined) return cachedUser;
  try {
    const data = await getJson("/me");
    cachedUser = data.authenticated ? data.user : null;
  } catch {
    cachedUser = null;
  }
  return cachedUser;
}

export async function logout() {
  try {
    await apiFetch("/logout", { method: "POST" });
  } finally {
    window.location.href = "index.html";
  }
}

function initials(name) {
  const parts = String(name || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (!parts.length) return "CS";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function actionsMarkup(user) {
  if (!user) {
    return `
      <a class="btn btn-ghost btn-sm" href="login.html">Sign in</a>
      <a class="btn btn-primary btn-sm" href="register.html">Create account</a>`;
  }
  return `
    <span class="user-chip">
      <span class="avatar">${escapeHtml(initials(user.name))}</span>
      <span>${escapeHtml(user.name)}</span>
    </span>
    <button class="btn btn-ghost btn-sm" type="button" id="navLogout">Sign out</button>`;
}

export async function renderChrome() {
  const header = document.getElementById("siteHeader");
  const footer = document.getElementById("siteFooter");
  const current = window.location.pathname.split("/").pop() || "index.html";

  if (header) {
    header.className = "site-header";
    header.innerHTML = `
      <div class="container nav">
        <a class="brand" href="index.html">
          <span class="brand-mark">${icon("logo")}</span>
          CareSphere
        </a>
        <button class="nav-toggle" type="button" id="navToggle"
                aria-expanded="false" aria-controls="navDrawer" aria-label="Toggle navigation">
          ${icon("menu")}
        </button>
        <div class="nav-drawer" id="navDrawer">
          <ul class="nav-links" id="navLinkList"></ul>
          <div class="nav-actions" id="navActions"></div>
        </div>
      </div>`;

    const toggle = document.getElementById("navToggle");
    const links = document.getElementById("navDrawer");
    toggle?.addEventListener("click", () => {
      const open = links.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", String(open));
    });
  }

  if (footer) {
    footer.className = "site-footer";
    footer.innerHTML = `
      <div class="container">
        <div class="footer-grid">
          <div>
            <a class="brand" href="index.html">
              <span class="brand-mark">${icon("logo")}</span> CareSphere
            </a>
            <p style="margin-top:var(--space-3);max-width:36ch">
              Smart healthcare through AI. Find the right specialist, book with
              confidence, and keep your health information in one place.
            </p>
          </div>
          <div>
            <strong style="color:var(--text)">Project</strong>
            <ul class="plain" style="margin-top:var(--space-2);display:grid;gap:var(--space-1)">
              <li>CSE 3200 &mdash; Software Development Project II</li>
              <li>Department of Computer Science &amp; Engineering</li>
              <li>Rajshahi University of Engineering &amp; Technology</li>
            </ul>
          </div>
        </div>
        <p class="footer-note">
          CareSphere does not provide medical diagnosis. In an emergency, contact
          local emergency services or go to the nearest emergency department.
          Doctor records shown here are placeholder data for academic demonstration.
        </p>
      </div>`;
  }

  const user = await loadCurrentUser();

  const linkList = document.getElementById("navLinkList");
  if (linkList) {
    linkList.innerHTML = visibleLinks(user)
      .map(
        (link) =>
          `<li><a href="${link.href}"${
            link.href === current ? ' aria-current="page"' : ""
          }>${link.label}</a></li>`
      )
      .join("");
  }

  const actions = document.getElementById("navActions");
  if (actions) {
    actions.innerHTML = actionsMarkup(user);
    document.getElementById("navLogout")?.addEventListener("click", logout);
  }
  return user;
}
