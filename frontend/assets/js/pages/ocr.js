import { icon } from "../icons.js";
import { renderChrome } from "../ui/nav.js";
import { toast } from "../ui/toast.js";
import {
  LANGUAGES,
  countWords,
  formatBytes,
  isCancelled,
  overallProgress,
  prepareImage,
  startOcr,
  statusLabel,
  validateImageFile,
} from "../ocr-engine.js";

const $ = (id) => document.getElementById(id);

const state = {
  file: null,
  previewUrl: null,
  job: null,
  cancelRequested: false,
};

function setError(message) {
  const box = $("ocrError");
  if (!message) {
    box.classList.remove("is-visible");
    $("ocrErrorText").textContent = "";
    return;
  }
  $("ocrErrorText").textContent = message;
  box.classList.add("is-visible");
}

function setBusy(busy) {
  $("runBtn").disabled = busy || !state.file;
  $("runBtn").setAttribute("aria-busy", String(busy));
  $("runBtn").hidden = busy;
  $("cancelBtn").hidden = !busy;
  $("removeBtn").disabled = busy;
  $("languageSelect").disabled = busy;
  $("enhanceToggle").disabled = busy;
  $("fileInput").disabled = busy;
  $("dropzone").classList.toggle("is-disabled", busy);
}

function setProgress(fraction, label) {
  const percent = Math.round(fraction * 100);
  $("progressFill").style.width = `${percent}%`;
  $("progressTrack").setAttribute("aria-valuenow", String(percent));
  $("progressLabel").textContent = label;
}

function showProgress(visible) {
  $("ocrProgress").hidden = !visible;
  if (!visible) setProgress(0, "");
}

function refreshOutputControls() {
  const text = $("ocrOutput").value;
  const hasText = text.trim().length > 0;
  $("copyBtn").disabled = !hasText;
  $("downloadBtn").disabled = !hasText;
  $("clearBtn").disabled = !hasText;
  $("wordCount").textContent = `${countWords(text)} word${countWords(text) === 1 ? "" : "s"}`;
}

function showConfidence(confidence) {
  const badge = $("confidenceBadge");
  if (confidence === null) {
    badge.hidden = true;
    return;
  }
  let variant = "badge-ok";
  if (confidence < 60) variant = "badge-danger";
  else if (confidence < 80) variant = "badge-warn";
  badge.className = `badge ${variant}`;
  badge.textContent = `Confidence ${confidence}%`;
  badge.hidden = false;
  $("lowConfidence").classList.toggle("is-visible", confidence < 60);
}

function clearResult() {
  $("ocrOutput").value = "";
  showConfidence(null);
  $("lowConfidence").classList.remove("is-visible");
  refreshOutputControls();
}

function releasePreview() {
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
  state.previewUrl = null;
}

function removeFile() {
  releasePreview();
  state.file = null;
  $("fileInput").value = "";
  $("previewWrap").hidden = true;
  $("previewImg").removeAttribute("src");
  $("runBtn").disabled = true;
  setError("");
}

function selectFile(file) {
  const problem = validateImageFile(file);
  if (problem) {
    setError(problem);
    return;
  }
  setError("");
  releasePreview();
  state.file = file;
  state.previewUrl = URL.createObjectURL(file);
  $("previewImg").src = state.previewUrl;
  $("fileName").textContent = file.name || "Pasted image";
  $("fileSize").textContent = formatBytes(file.size);
  $("previewWrap").hidden = false;
  $("runBtn").disabled = false;
  clearResult();
}

async function runExtraction() {
  if (!state.file || state.job) return;
  state.cancelRequested = false;
  setError("");
  clearResult();
  setBusy(true);
  showProgress(true);
  setProgress(0.01, "Preparing the image…");

  let lastFraction = 0.01;
  try {
    const image = await prepareImage(state.file, { enhance: $("enhanceToggle").checked });
    if (state.cancelRequested) return;
    const job = startOcr(image, $("languageSelect").value, (message) => {
      const fraction = overallProgress(message.status, message.progress);
      if (fraction === null) return;
      lastFraction = Math.max(lastFraction, fraction);
      setProgress(lastFraction, statusLabel(message.status));
    });
    state.job = job;
    const { text, confidence } = await job.promise;

    if (!text) {
      setError(
        "No text was found. Try a sharper, well-lit photo taken straight on, or switch the language."
      );
      return;
    }
    $("ocrOutput").value = text;
    showConfidence(confidence);
    refreshOutputControls();
    toast("Text extracted. Please review it before relying on it.", "success");
    $("ocrOutput").focus();
  } catch (error) {
    if (!isCancelled(error)) {
      setError(error.message || "Text extraction failed. Please try again.");
    }
  } finally {
    state.job = null;
    showProgress(false);
    setBusy(false);
  }
}

function cancelExtraction() {
  state.cancelRequested = true;
  state.job?.cancel();
}

async function copyText() {
  const text = $("ocrOutput").value;
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    $("ocrOutput").select();
    document.execCommand("copy");
  }
  toast("Copied to clipboard.", "success");
}

function downloadText() {
  const base = (state.file?.name || "prescription").replace(/\.[^.]+$/, "");
  const blob = new Blob([$("ocrOutput").value], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${base}-ocr.txt`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function bindDropzone() {
  const zone = $("dropzone");
  ["dragenter", "dragover"].forEach((type) =>
    zone.addEventListener(type, (event) => {
      event.preventDefault();
      if (!$("fileInput").disabled) zone.classList.add("is-dragover");
    })
  );
  ["dragleave", "drop"].forEach((type) =>
    zone.addEventListener(type, (event) => {
      event.preventDefault();
      zone.classList.remove("is-dragover");
    })
  );
  zone.addEventListener("drop", (event) => {
    if ($("fileInput").disabled) return;
    const [file] = event.dataTransfer?.files || [];
    if (file) selectFile(file);
  });
}

function bindPaste() {
  document.addEventListener("paste", (event) => {
    if ($("fileInput").disabled) return;
    const item = [...(event.clipboardData?.items || [])].find((entry) =>
      entry.type.startsWith("image/")
    );
    const file = item?.getAsFile();
    if (file) {
      event.preventDefault();
      selectFile(file);
    }
  });
}

function fillIcons() {
  document.querySelectorAll("[data-icon]").forEach((node) => {
    node.innerHTML = icon(node.dataset.icon);
  });
}

function fillLanguages() {
  $("languageSelect").innerHTML = LANGUAGES.map(
    (language) => `<option value="${language.code}">${language.label}</option>`
  ).join("");
}

document.addEventListener("DOMContentLoaded", async () => {
  await renderChrome();
  fillIcons();
  fillLanguages();
  bindDropzone();
  bindPaste();

  $("fileInput").addEventListener("change", (event) => {
    const [file] = event.target.files;
    if (file) selectFile(file);
  });
  $("removeBtn").addEventListener("click", removeFile);
  $("runBtn").addEventListener("click", runExtraction);
  $("cancelBtn").addEventListener("click", cancelExtraction);
  $("ocrOutput").addEventListener("input", refreshOutputControls);
  $("copyBtn").addEventListener("click", copyText);
  $("downloadBtn").addEventListener("click", downloadText);
  $("clearBtn").addEventListener("click", clearResult);

  refreshOutputControls();
});
