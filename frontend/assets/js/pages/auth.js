import { postJson } from "../api.js";
import { homeFor, renderChrome } from "../ui/nav.js";
import { toast } from "../ui/toast.js";

const MIN_PASSWORD = 8;

function setAlert(message, variant = "error") {
  const box = document.getElementById("formAlert");
  if (!box) return;
  box.className = `alert alert-${variant} is-visible`;
  box.textContent = message;
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
      setTimeout(() => {
        window.location.href = homeFor(data.user);
      }, 500);
    } catch (error) {
      setAlert(error.message);
      busy(button, false, "Sign in");
    }
  });
}

function wireRegister() {
  const form = document.getElementById("registerForm");
  if (!form) return;

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

    const button = document.getElementById("submitButton");
    busy(button, true, "Creating account\u2026");
    try {
      await postJson("/register", {
        name: document.getElementById("name").value.trim(),
        email: document.getElementById("email").value.trim(),
        password,
      });
      toast("Account created. Welcome to CareSphere.", "success");
      setTimeout(() => {
        window.location.href = "doctors.html";
      }, 600);
    } catch (error) {
      setAlert(error.message);
      busy(button, false, "Create account");
    }
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
