import { getJson, apiFetch, escapeHtml } from "../api.js";
import { icon } from "../icons.js";
import { renderChrome } from "../ui/nav.js";
import { toast } from "../ui/toast.js";

const URGENCY = {
  low: { label: "Lower risk", variant: "ok" },
  medium: { label: "Should be seen", variant: "warn" },
  high: { label: "Needs attention soon", variant: "danger" },
  emergency: { label: "Emergency", variant: "danger" },
};

const state = { sessionId: null, busy: false, complete: false };

const $ = (id) => document.getElementById(id);
const log = () => $("chatLog");

/* ------------------------------------------------------------- rendering */

function scrollDown() {
  requestAnimationFrame(() => {
    log().scrollTop = log().scrollHeight;
  });
}

function userBubble(text) {
  return `
    <div class="bubble-row is-user">
      <div class="bubble bubble-user">${escapeHtml(text)}</div>
    </div>`;
}

function conditionsBlock(conditions) {
  if (!conditions?.length) return "";
  return `
    <div class="chat-block">
      <h4>Possible causes being considered</h4>
      ${conditions
        .map(
          (c) => `
        <div class="condition-row">
          <span>${escapeHtml(c.name)}</span>
          <span class="badge badge-neutral">${escapeHtml(c.likelihood)}</span>
        </div>`
        )
        .join("")}
    </div>`;
}

function listBlock(title, items) {
  if (!items?.length) return "";
  return `
    <div class="chat-block">
      <h4>${escapeHtml(title)}</h4>
      <ul>${items.map((i) => `<li>${escapeHtml(i)}</li>`).join("")}</ul>
    </div>`;
}

function degradedNote(data) {
  if (!data?.degraded) return "";
  return `
    <div class="chat-block">
      <h4>Limited mode</h4>
      <p style="margin:0;font-size:var(--text-sm);color:var(--text-soft)">
        The AI assistant is unavailable right now, so this is general guidance only.
      </p>
    </div>`;
}

function questionBody(data) {
  return `
    ${conditionsBlock(data.possible_conditions)}
    ${listBlock("Warning signs I am checking for", data.red_flags)}
    <div class="chat-question">${escapeHtml(data.question)}</div>
    ${degradedNote(data)}
    ${
      data.progress
        ? `<div class="chat-progress">Question ${data.progress.asked} of up to ${data.progress.max}</div>`
        : ""
    }`;
}

function recommendationBody(data) {
  const urgency = URGENCY[data.urgency] || URGENCY.medium;
  return `
    <div class="cluster" style="gap:var(--space-2);margin-bottom:var(--space-2)">
      <span class="badge badge-accent">${escapeHtml(data.specialty)}</span>
      <span class="badge badge-${urgency.variant}">${escapeHtml(urgency.label)}</span>
    </div>
    <p style="margin:0">${escapeHtml(data.summary)}</p>
    ${conditionsBlock(data.possible_conditions)}
    ${listBlock("Warning signs to watch for", data.red_flags)}
    ${listBlock("Next steps", data.next_steps)}
    ${degradedNote(data)}
    <div class="chat-actions">
      <a class="btn btn-primary btn-sm"
         href="doctors.html?specialty=${encodeURIComponent(data.specialty_slug)}">
        Browse ${escapeHtml(data.specialty)}s
      </a>
      <button class="btn btn-secondary btn-sm" type="button" data-action="restart">
        Start a new assessment
      </button>
    </div>
    <div class="chat-block">
      <p style="margin:0;font-size:var(--text-xs);color:var(--text-faint)">
        ${escapeHtml(data.disclaimer || "")}
      </p>
    </div>`;
}

function emergencyBody(data) {
  return `
    <div class="emergency-card">
      <h3>${icon("alert")} Seek medical help now</h3>
      <p style="margin:0">${escapeHtml(data.reason)}</p>
      <ul>${(data.actions || []).map((a) => `<li>${escapeHtml(a)}</li>`).join("")}</ul>
    </div>
    <div class="chat-actions">
      <button class="btn btn-secondary btn-sm" type="button" data-action="restart">
        Start a new assessment
      </button>
    </div>
    <div class="chat-block">
      <p style="margin:0;font-size:var(--text-xs);color:var(--text-faint)">
        ${escapeHtml(data.disclaimer || "")}
      </p>
    </div>`;
}

function botBubble(message) {
  const data = message.data || {};
  let body;
  if (message.kind === "question") body = questionBody(data);
  else if (message.kind === "recommendation") body = recommendationBody(data);
  else if (message.kind === "emergency") body = emergencyBody(data);
  else body = `<p style="margin:0">${escapeHtml(message.text)}</p>`;

  return `
    <div class="bubble-row">
      <span class="bubble-icon">${icon("sparkles")}</span>
      <div class="bubble bubble-bot">${body}</div>
    </div>`;
}

function append(html) {
  log().insertAdjacentHTML("beforeend", html);
  scrollDown();
}

function showTyping() {
  append(`
    <div class="bubble-row" id="typingRow">
      <span class="bubble-icon">${icon("sparkles")}</span>
      <div class="bubble bubble-bot" style="padding:0">
        <div class="typing" role="status" aria-label="Assistant is thinking">
          <span></span><span></span><span></span>
        </div>
      </div>
    </div>`);
}

function hideTyping() {
  $("typingRow")?.remove();
}

/* ---------------------------------------------------------------- state */

function setBusy(busy) {
  state.busy = busy;
  const input = $("chatInput");
  const send = $("sendButton");
  const disabled = busy || state.complete;
  input.disabled = disabled;
  send.disabled = disabled;
  input.placeholder = state.complete
    ? "This assessment is finished. Start a new one to continue."
    : "Describe how you are feeling...";
}

/* ----------------------------------------------------------- networking */

async function newAssessment() {
  log().innerHTML = "";
  state.complete = false;
  setBusy(true);
  try {
    const session = await getJson("/chat/sessions", { method: "POST" });
    state.sessionId = session.id;
    session.messages.forEach((m) => append(botBubble(m)));
    await loadHistory();
  } catch (error) {
    append(
      `<div class="empty-state">${icon("shield")}<h3>Could not start</h3><p>${escapeHtml(
        error.message
      )}</p></div>`
    );
  } finally {
    setBusy(false);
    $("chatInput").focus();
  }
}

async function openAssessment(id) {
  setBusy(true);
  try {
    const session = await getJson(`/chat/sessions/${encodeURIComponent(id)}`);
    state.sessionId = session.id;
    state.complete = session.is_complete;
    log().innerHTML = "";
    session.messages.forEach((m) =>
      append(m.sender === "user" ? userBubble(m.text) : botBubble(m))
    );
    markActive(id);
  } catch (error) {
    toast(error.message, "error");
  } finally {
    setBusy(false);
  }
}

async function send() {
  const input = $("chatInput");
  const text = input.value.trim();
  if (!text || state.busy || state.complete) return;

  append(userBubble(text));
  input.value = "";
  input.style.height = "auto";
  setBusy(true);
  showTyping();

  try {
    const response = await apiFetch(
      `/chat/sessions/${encodeURIComponent(state.sessionId)}/messages`,
      { method: "POST", body: JSON.stringify({ message: text }) }
    );
    const body = await response.json().catch(() => ({}));
    hideTyping();

    if (!response.ok) {
      toast(body.error || `Request failed (${response.status})`, "error");
      return;
    }

    append(botBubble(body.message));
    state.complete = body.session.is_complete;
    if (state.complete) await loadHistory();
  } catch (error) {
    hideTyping();
    toast(error.message, "error");
  } finally {
    setBusy(false);
    if (!state.complete) $("chatInput").focus();
  }
}

/* ------------------------------------------------------------- history */

function markActive(id) {
  document
    .querySelectorAll(".history-item")
    .forEach((n) => n.setAttribute("aria-current", String(n.dataset.id === id)));
}

async function loadHistory() {
  const target = $("historyList");
  try {
    const sessions = await getJson("/chat/sessions");
    if (!sessions.length) {
      target.innerHTML = `<p style="font-size:var(--text-sm);color:var(--text-faint);margin:0">
        No past assessments yet.</p>`;
      return;
    }
    target.innerHTML = sessions
      .map(
        (s) => `
        <button class="history-item" type="button" data-id="${escapeHtml(s.id)}"
                aria-current="${s.id === state.sessionId}">
          <strong>${escapeHtml(s.summary)}</strong>
          <span>${
            s.recommended_specialty ? escapeHtml(s.recommended_specialty) : "In progress"
          } &middot; ${new Date(s.started_at).toLocaleDateString()}</span>
        </button>`
      )
      .join("");

    target.querySelectorAll(".history-item").forEach((button) => {
      button.addEventListener("click", () => openAssessment(button.dataset.id));
    });
  } catch {
    target.innerHTML = "";
  }
}

/* ---------------------------------------------------------------- boot */

document.addEventListener("DOMContentLoaded", async () => {
  const user = await renderChrome();
  if (!user) {
    $("assistantRoot").innerHTML = `
      <div class="empty-state">${icon("lock")}
        <h3>Sign in to use the health assistant</h3>
        <p>Your assessments are saved to your account so you can revisit them.</p>
        <div class="cluster" style="justify-content:center;margin-top:var(--space-3)">
          <a class="btn btn-primary btn-sm" href="login.html">Sign in</a>
          <a class="btn btn-secondary btn-sm" href="register.html">Create an account</a>
        </div>
      </div>`;
    return;
  }

  const input = $("chatInput");

  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 128)}px`;
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  });

  $("sendButton").addEventListener("click", send);
  $("newChatButton").addEventListener("click", newAssessment);

  log().addEventListener("click", (event) => {
    if (event.target.closest('[data-action="restart"]')) newAssessment();
  });

  await newAssessment();
});
