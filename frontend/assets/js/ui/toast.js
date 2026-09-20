/** Replacement for alert(). Non-blocking, styled, screen-reader friendly. */

function stack() {
  let node = document.querySelector(".toast-stack");
  if (!node) {
    node = document.createElement("div");
    node.className = "toast-stack";
    node.setAttribute("role", "status");
    node.setAttribute("aria-live", "polite");
    document.body.appendChild(node);
  }
  return node;
}

export function toast(message, variant = "info", timeout = 4200) {
  const node = document.createElement("div");
  node.className = variant === "info" ? "toast" : `toast toast-${variant}`;
  node.textContent = message;
  stack().appendChild(node);
  setTimeout(() => node.remove(), timeout);
}
