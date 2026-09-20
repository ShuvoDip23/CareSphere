/* Prescription OCR engine.
 *
 * Text recognition runs entirely in the browser with Tesseract.js, so the
 * prescription image is never uploaded anywhere. The library is loaded on
 * demand from a CDN the first time the user starts an extraction, which keeps
 * every other page light.
 */

export const MAX_FILE_BYTES = 10 * 1024 * 1024;
export const ACCEPTED_TYPES = ["image/png", "image/jpeg", "image/webp", "image/bmp"];

export const LANGUAGES = [
  { code: "eng", label: "English" },
  { code: "eng+ben", label: "English + Bengali (larger first download)" },
];

const TESSERACT_URL = "https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js";

/** Longest image side, in pixels, that gives Tesseract enough detail without stalling. */
const MIN_SIDE = 1500;
const MAX_SIDE = 3000;
const MAX_UPSCALE = 3;

export function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Returns a user-facing error message, or null when the file is acceptable. */
export function validateImageFile(file) {
  if (!file) return "Choose an image first.";
  if (!ACCEPTED_TYPES.includes(file.type)) {
    return "Unsupported file type. Use a PNG, JPG, WebP or BMP image.";
  }
  if (file.size === 0) return "That file is empty.";
  if (file.size > MAX_FILE_BYTES) {
    return `That image is ${formatBytes(file.size)}. The limit is ${formatBytes(MAX_FILE_BYTES)}.`;
  }
  return null;
}

export function countWords(text) {
  const trimmed = String(text || "").trim();
  return trimmed ? trimmed.split(/\s+/).length : 0;
}

/**
 * Convert RGBA pixel data to grayscale and stretch the contrast in place.
 * The darkest and lightest 1% of pixels are clipped first so a single shadow
 * or glare spot on a phone photo does not flatten the rest of the page.
 */
export function enhanceGrayscale(data) {
  const pixelCount = data.length / 4;
  if (!pixelCount) return data;

  const histogram = new Array(256).fill(0);
  for (let i = 0; i < data.length; i += 4) {
    const gray = Math.round(0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2]);
    data[i] = data[i + 1] = data[i + 2] = gray;
    histogram[gray] += 1;
  }

  const clip = pixelCount * 0.01;
  let low = 0;
  let seen = 0;
  while (low < 255 && seen + histogram[low] <= clip) {
    seen += histogram[low];
    low += 1;
  }
  let high = 255;
  seen = 0;
  while (high > 0 && seen + histogram[high] <= clip) {
    seen += histogram[high];
    high -= 1;
  }
  if (high - low < 16) return data; // effectively one flat tone; stretching would only add noise

  const scale = 255 / (high - low);
  for (let i = 0; i < data.length; i += 4) {
    const value = Math.max(0, Math.min(255, Math.round((data[i] - low) * scale)));
    data[i] = data[i + 1] = data[i + 2] = value;
  }
  return data;
}

/** Scale factor that brings the longest side into the MIN_SIDE..MAX_SIDE range. */
export function targetScale(width, height) {
  const longest = Math.max(width, height);
  if (longest > MAX_SIDE) return MAX_SIDE / longest;
  if (longest < MIN_SIDE) return Math.min(MAX_UPSCALE, MIN_SIDE / longest);
  return 1;
}

function loadImageElement(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      URL.revokeObjectURL(url);
      resolve(image);
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("That file could not be read as an image."));
    };
    image.src = url;
  });
}

/**
 * Resize and (optionally) enhance the image before recognition.
 * Returns a PNG Blob. With `enhance` off the original file is returned untouched.
 */
export async function prepareImage(file, { enhance = true } = {}) {
  if (!enhance) return file;

  const image = await loadImageElement(file);
  const scale = targetScale(image.naturalWidth, image.naturalHeight);
  const width = Math.max(1, Math.round(image.naturalWidth * scale));
  const height = Math.max(1, Math.round(image.naturalHeight * scale));

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  context.fillStyle = "#ffffff"; // flatten transparent PNGs onto white
  context.fillRect(0, 0, width, height);
  context.drawImage(image, 0, 0, width, height);

  const pixels = context.getImageData(0, 0, width, height);
  enhanceGrayscale(pixels.data);
  context.putImageData(pixels, 0, 0);

  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("Could not prepare the image."))),
      "image/png"
    );
  });
}

/**
 * Map a Tesseract.js logger message to a single 0..1 value so the progress
 * bar only ever moves forward. Returns null for messages we do not track.
 */
export function overallProgress(status, progress = 0) {
  const p = Math.max(0, Math.min(1, Number(progress) || 0));
  const s = String(status || "");
  if (s.startsWith("loading tesseract core")) return 0.02 + p * 0.08;
  if (s.startsWith("initializing tesseract") || s.startsWith("initialized tesseract")) {
    return 0.1 + p * 0.05;
  }
  if (s.startsWith("loading language") || s.startsWith("loaded language")) {
    return 0.15 + p * 0.25;
  }
  if (s.startsWith("initializing api") || s.startsWith("initialized api")) {
    return 0.4 + p * 0.02;
  }
  if (s.startsWith("recognizing")) return 0.42 + p * 0.58;
  return null;
}

/** Friendly label for a Tesseract.js status string. */
export function statusLabel(status) {
  const s = String(status || "");
  if (s.startsWith("loading tesseract core") || s.startsWith("initializing tesseract")) {
    return "Starting the OCR engine…";
  }
  if (s.startsWith("loading language") || s.startsWith("loaded language")) {
    return "Loading language data…";
  }
  if (s.startsWith("initializing api") || s.startsWith("initialized")) {
    return "Getting ready…";
  }
  if (s.startsWith("recognizing")) return "Reading the text…";
  return "Working…";
}

let tesseractPromise = null;

/** Load Tesseract.js once and reuse it. Rejects with a readable message if the CDN is unreachable. */
export function loadTesseract() {
  if (window.Tesseract) return Promise.resolve(window.Tesseract);
  if (tesseractPromise) return tesseractPromise;

  tesseractPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = TESSERACT_URL;
    script.async = true;
    script.onload = () => {
      if (window.Tesseract) resolve(window.Tesseract);
      else reject(new Error("The OCR engine loaded but did not start."));
    };
    script.onerror = () => {
      script.remove();
      tesseractPromise = null; // let the user retry after reconnecting
      reject(new Error("Could not download the OCR engine. Check your internet connection."));
    };
    document.head.appendChild(script);
  });
  return tesseractPromise;
}

export function isCancelled(error) {
  return error?.name === "AbortError";
}

/**
 * Start an OCR job. Returns `{ promise, cancel }`.
 * `promise` resolves to `{ text, confidence }` and rejects with an AbortError
 * if `cancel()` is called first.
 */
export function startOcr(image, language, onProgress) {
  let worker = null;
  let cancelled = false;
  let terminated = false;
  let rejectCancelled;

  const cancelSignal = new Promise((_, reject) => {
    rejectCancelled = reject;
  });

  async function terminate() {
    if (!worker || terminated) return;
    terminated = true;
    try {
      await worker.terminate();
    } catch {
      /* the worker is already gone */
    }
  }

  const work = (async () => {
    const Tesseract = await loadTesseract();
    worker = await Tesseract.createWorker(language, 1, {
      logger: (message) => onProgress?.(message),
    });
    if (cancelled) {
      await terminate();
      return null;
    }
    const { data } = await worker.recognize(image);
    return { text: String(data.text || "").trim(), confidence: Math.round(data.confidence || 0) };
  })();
  work.catch(() => {}); // a late failure after cancel() must not surface as unhandled

  const promise = Promise.race([work, cancelSignal]).finally(terminate);

  function cancel() {
    if (cancelled) return;
    cancelled = true;
    const error = new Error("Extraction cancelled.");
    error.name = "AbortError";
    rejectCancelled(error);
    terminate();
  }

  return { promise, cancel };
}
