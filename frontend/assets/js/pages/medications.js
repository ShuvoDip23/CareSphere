import { getJson, postJson, apiFetch, escapeHtml } from "../api.js";
import { renderChrome } from "../ui/nav.js";
import { toast } from "../ui/toast.js";

const $ = (id) => document.getElementById(id);
const today = new Date().toLocaleDateString("en-CA");
$("startDate").value = today;

async function load() {
  const [schedule, plans, history, prescriptions] = await Promise.all([
    getJson("/reminders/today"),
    getJson("/reminders"),
    getJson("/reminders/history"),
    getJson("/prescriptions"),
  ]);
  $("prescriptionSource").innerHTML =
    '<option value="">Manual entry</option>' +
    prescriptions.prescriptions
      .map(
        (p) =>
          `<option value="${p.id}">Prescription #${p.id} · ${new Date(p.created_at).toLocaleDateString()}</option>`
      )
      .join("");
  $("prescriptionSource").onchange = () => {
    const selected = prescriptions.prescriptions.find(
      (p) => String(p.id) === $("prescriptionSource").value
    );
    const item = selected?.items?.[0];
    if (item) {
      $("medicine").value = item.medicine_name || "";
      $("dosage").value = item.dosage || "";
      $("frequency").value = item.frequency || "";
      $("instructions").value = item.instructions || "";
    }
  };
  $("today").innerHTML = schedule.schedule.length
    ? schedule.schedule
        .map((entry) => {
          const r = entry.reminder;
          const time = new Date(entry.scheduled_for).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          });
          return `<div class="list-row" style="padding:1rem 0;border-bottom:1px solid var(--color-border)">
      <div><strong>${escapeHtml(r.medicine_name)}</strong> — ${escapeHtml(r.dosage)} <span class="badge">${time}</span>
      <p>${escapeHtml(r.instructions || r.frequency)} · <strong>${escapeHtml(entry.status)}</strong></p></div>
      ${
        entry.status === "upcoming" || entry.status === "missed"
          ? `<div>
      <button class="btn btn-primary btn-sm" data-log="taken" data-id="${r.id}" data-time="${entry.scheduled_for}">Taken</button>
      <button class="btn btn-secondary btn-sm" data-log="skipped" data-id="${r.id}" data-time="${entry.scheduled_for}">Skipped</button></div>`
          : ""
      }
      </div>`;
        })
        .join("")
    : "<p>No medication scheduled for today.</p>";
  $("plans").innerHTML = plans.reminders.length
    ? plans.reminders
        .map(
          (
            r
          ) => `<div class="list-row" style="padding:1rem 0;border-bottom:1px solid var(--color-border)">
    <div><strong>${escapeHtml(r.medicine_name)}</strong> — ${escapeHtml(r.dosage)}<p>${escapeHtml(r.frequency)} · ${r.times.map(escapeHtml).join(", ")} · ${r.start_date}${r.end_date ? " to " + r.end_date : ""}</p>
    <span class="badge">${r.active ? "Active" : "Paused"}</span></div>
    <div><button class="btn btn-secondary btn-sm" data-edit="${r.id}" data-name="${escapeHtml(r.medicine_name)}" data-dosage="${escapeHtml(r.dosage)}" data-frequency="${escapeHtml(r.frequency)}" data-times="${escapeHtml(r.times.join(", "))}" data-instructions="${escapeHtml(r.instructions || "")}">Edit</button>
    <button class="btn btn-secondary btn-sm" data-toggle="${r.id}" data-active="${r.active}">${r.active ? "Pause" : "Activate"}</button>
    <button class="btn btn-ghost btn-sm" data-delete="${r.id}">Delete</button></div></div>`
        )
        .join("")
    : "<p>No medication plans yet.</p>";
  $("stats").innerHTML =
    `<p><strong>${history.statistics.adherence_percent}%</strong> adherence · ${history.statistics.taken} taken · ${history.statistics.skipped} skipped · ${history.statistics.missed} missed</p>`;
  $("history").innerHTML = history.history.length
    ? history.history
        .slice(0, 30)
        .map(
          (x) => `<p>${escapeHtml(x.scheduled_for.replace("T", " "))} — ${escapeHtml(x.status)}</p>`
        )
        .join("")
    : "<p>No dose history yet.</p>";
}
$("medForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const times = $("times")
    .value.split(",")
    .map((x) => x.trim())
    .filter(Boolean);
  try {
    await postJson("/reminders", {
      medicine_name: $("medicine").value,
      dosage: $("dosage").value,
      frequency: $("frequency").value,
      times,
      start_date: $("startDate").value,
      end_date: $("endDate").value || null,
      instructions: $("instructions").value,
      prescription_id: $("prescriptionSource").value ? Number($("prescriptionSource").value) : null,
    });
    event.target.reset();
    $("startDate").value = today;
    toast("Medication plan saved.", "success");
    await load();
  } catch (error) {
    toast(error.message, "error");
  }
});
$("refresh").addEventListener("click", () => load().catch((e) => toast(e.message, "error")));
document.addEventListener("click", async (event) => {
  const log = event.target.closest("[data-log]");
  const toggle = event.target.closest("[data-toggle]");
  const del = event.target.closest("[data-delete]");
  const edit = event.target.closest("[data-edit]");
  try {
    if (log) {
      await postJson(`/reminders/${log.dataset.id}/log`, {
        status: log.dataset.log,
        scheduled_for: log.dataset.time,
      });
      toast(`Dose marked ${log.dataset.log}.`, "success");
      await load();
    } else if (edit) {
      const medicine_name = prompt("Medicine name:", edit.dataset.name);
      if (medicine_name === null) return;
      const dosage = prompt("Dosage:", edit.dataset.dosage);
      if (dosage === null) return;
      const frequency = prompt("Frequency:", edit.dataset.frequency);
      if (frequency === null) return;
      const times = prompt("Reminder times (HH:MM, comma-separated):", edit.dataset.times);
      if (times === null) return;
      const instructions = prompt("Instructions:", edit.dataset.instructions);
      if (instructions === null) return;
      const response = await apiFetch(`/reminders/${edit.dataset.edit}`, {
        method: "PATCH",
        body: JSON.stringify({
          medicine_name,
          dosage,
          frequency,
          times: times
            .split(",")
            .map((x) => x.trim())
            .filter(Boolean),
          instructions,
        }),
      });
      if (!response.ok) throw new Error((await response.json()).error || "Could not edit plan");
      await load();
    } else if (toggle) {
      const response = await apiFetch(`/reminders/${toggle.dataset.toggle}`, {
        method: "PATCH",
        body: JSON.stringify({ active: toggle.dataset.active !== "true" }),
      });
      if (!response.ok) throw new Error((await response.json()).error || "Could not update plan");
      await load();
    } else if (del) {
      if (!confirm("Delete this medication plan and its dose history?")) return;
      const response = await apiFetch(`/reminders/${del.dataset.delete}`, { method: "DELETE" });
      if (!response.ok) throw new Error("Could not delete plan");
      await load();
    }
  } catch (error) {
    toast(error.message, "error");
  }
});
document.addEventListener("DOMContentLoaded", async () => {
  const user = await renderChrome();
  if (!user) {
    location.href = "login.html";
    return;
  }
  try {
    await load();
  } catch (error) {
    $("today").textContent = error.message;
  }
});
