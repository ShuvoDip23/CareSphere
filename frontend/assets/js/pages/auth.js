import { apiFetch, postJson } from "../api.js";
import { homeFor, renderChrome } from "../ui/nav.js";
import { toast } from "../ui/toast.js";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

const MIN_PASSWORD = 8;

/** Where to land after signing in, when the page was reached from a booking.
 *
 * Only a bare same-origin page name is accepted. An absolute URL, a
 * protocol-relative `//evil.test` or a traversal is discarded and the role's
 * own home is used instead, so `?next=` cannot bounce a freshly signed-in
 * user off the site.
 */
function safeNext(raw) {
  return /^[a-z0-9-]+\.html(\?[^#]*)?$/i.test(String(raw || "")) ? raw : null;
}

function setAlert(message, variant = "error") {
  const box = document.getElementById("formAlert");
  if (!box) return;
  box.className = `alert alert-${variant} is-visible`;
  box.textContent = message;
}

/** Show the first field error inline and the rest in the alert box. */
function setFieldErrors(fields, fallback) {
  const entries = Object.entries(fields || {});
  if (!entries.length) {
    setAlert(fallback);
    return;
  }
  setAlert(entries.map(([, message]) => message).join(" "));
  const first = document.getElementById(entries[0][0]);
  first?.focus();
}

function clearAlert() {
  const box = document.getElementById("formAlert");
  if (box) box.className = "alert";
}

function busy(button, isBusy, label) {
  button.disabled = isBusy;
  button.setAttribute("aria-busy", String(isBusy));
  button.textContent = label;
}

function wireLogin() {
  const form = document.getElementById("loginForm");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearAlert();

    const button = document.getElementById("submitButton");
    const payload = {
      email: document.getElementById("email").value.trim(),
      password: document.getElementById("password").value,
    };

    busy(button, true, "Signing in\u2026");
    try {
      const data = await postJson("/login", payload);
      toast("Signed in. Redirecting\u2026", "success");
      // The server's role decides the destination - the form never claims one.
      const next = safeNext(new URLSearchParams(window.location.search).get("next"));
      setTimeout(() => {
        window.location.href = next || homeFor(data.user);
      }, 500);
    } catch (error) {
      setAlert(error.message);
      busy(button, false, "Sign in");
    }
  });
}

function availabilityEditor() {
  const node = document.getElementById("availabilityEditor");
  if (!node) return;

  node.innerHTML = DAYS.map(
    (name, index) => `
      <div class="availability-day is-wrapped">
        <label>
          <input type="checkbox" data-day="${index}" />
          ${name}
        </label>
        <div class="day-times">
          <input type="time" data-start="${index}" value="09:00" disabled />
          <input type="time" data-end="${index}" value="13:00" disabled />
        </div>
      </div>`
  ).join("");

  node.addEventListener("change", (event) => {
    const box = event.target.closest('input[type="checkbox"][data-day]');
    if (!box) return;
    ["start", "end"].forEach((key) => {
      node.querySelector(`[data-${key}="${box.dataset.day}"]`).disabled = !box.checked;
    });
  });
}

function collectAvailability() {
  const node = document.getElementById("availabilityEditor");
  if (!node) return [];
  return [...node.querySelectorAll('input[type="checkbox"][data-day]')]
    .filter((box) => box.checked)
    .map((box) => ({
      day_of_week: Number(box.dataset.day),
      start_time: node.querySelector(`[data-start="${box.dataset.day}"]`).value,
      end_time: node.querySelector(`[data-end="${box.dataset.day}"]`).value,
    }));
}

function selectedRole() {
  return document.querySelector('input[name="accountType"]:checked')?.value || "patient";
}

function wireRoleChoice() {
  const group = document.querySelector(".role-choice");
  if (!group) return;

  const apply = () => {
    const isDoctor = selectedRole() === "doctor";
    document.getElementById("doctorFields").hidden = !isDoctor;
    document.getElementById("submitButton").textContent = isDoctor
      ? "Submit application"
      : "Create account";
    group.querySelectorAll(".role-option").forEach((option) => {
      option.classList.toggle("is-selected", option.querySelector("input").checked);
    });
  };

  group.addEventListener("change", apply);
  apply();
}

function value(id) {
  return document.getElementById(id).value.trim();
}

function wireRegister() {
  const form = document.getElementById("registerForm");
  if (!form) return;

  wireRoleChoice();
  availabilityEditor();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearAlert();

    const password = document.getElementById("password").value;
    const confirm = document.getElementById("confirmPassword").value;

    if (password.length < MIN_PASSWORD) {
      setAlert(`Password must be at least ${MIN_PASSWORD} characters.`);
      return;
    }
    if (password !== confirm) {
      setAlert("The two passwords do not match.");
      return;
    }

    const isDoctor = selectedRole() === "doctor";
    const button = document.getElementById("submitButton");
    busy(button, true, isDoctor ? "Submitting\u2026" : "Creating account\u2026");

    const payload = {
      name: value("name"),
      email: value("email"),
      password,
    };
    if (isDoctor) {
      Object.assign(payload, {
        specialty: value("specialty"),
        qualification: value("qualification"),
        hospital: value("hospital"),
        location: value("location"),
        phone: value("phone"),
        fee: value("fee"),
        experience_years: value("experienceYears") || 0,
        availability: collectAvailability(),
      });
    }

    const response = await apiFetch(isDoctor ? "/register/doctor" : "/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      // The application endpoint reports every bad field at once; the patient
      // endpoint returns a single message.
      setFieldErrors(data.fields, data.error || "Could not create the account.");
      busy(button, false, isDoctor ? "Submit application" : "Create account");
      return;
    }

    toast(
      isDoctor
        ? "Application submitted. An administrator will review it."
        : "Account created. Welcome to CareSphere.",
      "success"
    );
    setTimeout(() => {
      window.location.href = isDoctor ? "doctor-dashboard.html" : "doctors.html";
    }, 700);
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  const user = await renderChrome();
  if (user) {
    window.location.replace(homeFor(user));
    return;
  }
  wireLogin();
  wireRegister();
});
