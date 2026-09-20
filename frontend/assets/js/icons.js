/* Inline SVG icons. Kept in one module so stroke width and sizing stay
   consistent, and so no icon font or external request is needed. */

const PATHS = {
  logo: '<path d="M12 21s-7-4.35-7-10a4 4 0 0 1 7-2.65A4 4 0 0 1 19 11c0 5.65-7 10-7 10Z"/><path d="M3.5 12H8l1.5-3 2 6 1.5-3h4"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  stethoscope:
    '<path d="M6 3v5a4 4 0 0 0 8 0V3"/><path d="M4 3h4M10 3h4"/><path d="M10 12v2a5 5 0 0 0 10 0v-1"/><circle cx="20" cy="10" r="2"/>',
  pin: '<path d="M12 21s7-5.5 7-11a7 7 0 1 0-14 0c0 5.5 7 11 7 11Z"/><circle cx="12" cy="10" r="2.5"/>',
  hospital: '<path d="M4 21V8l8-5 8 5v13"/><path d="M9 21v-5h6v5"/><path d="M12 8v4M10 10h4"/>',
  phone:
    '<path d="M21 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 1.1 4.2 2 2 0 0 1 3.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.4 2.1L7.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2Z"/>',
  calendar: '<path d="M8 3v4M16 3v4M4 9h16"/><rect x="4" y="5" width="16" height="16" rx="2"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  shield:
    '<path d="M12 3 5 6v5c0 4.4 2.8 8.4 7 10 4.2-1.6 7-5.6 7-10V6l-7-3Z"/><path d="m9 12 2 2 4-4"/>',
  check: '<path d="m20 6-11 11-5-5"/>',
  chevronRight: '<path d="m9 6 6 6-6 6"/>',
  arrowLeft: '<path d="M19 12H5M11 6l-6 6 6 6"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  sparkles:
    '<path d="M12 3v4M12 17v4M3 12h4M17 12h4"/><path d="m6.3 6.3 2.4 2.4M15.3 15.3l2.4 2.4M17.7 6.3l-2.4 2.4M8.7 15.3l-2.4 2.4"/>',
  users:
    '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M17 5.2a3.5 3.5 0 0 1 0 5.6M18 14.4a6.5 6.5 0 0 1 3.5 5.6"/>',
  inbox:
    '<path d="M4 13h4l1.5 3h5L16 13h4"/><path d="M5.5 5h13l2 8v5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2v-5Z"/>',
  brain:
    '<path d="M9 4a3 3 0 0 0-3 3 3 3 0 0 0-1 5.8V15a3 3 0 0 0 4 2.8V4Z"/><path d="M15 4a3 3 0 0 1 3 3 3 3 0 0 1 1 5.8V15a3 3 0 0 1-4 2.8V4Z"/>',
  bone: '<path d="M7 10 4.8 7.8a2.2 2.2 0 1 1 3-3L10 7"/><path d="m14 17 2.2 2.2a2.2 2.2 0 1 0 3-3L17 14"/><path d="m7 10 7 7"/><path d="M10 7a2.2 2.2 0 1 1 3-3 2.2 2.2 0 0 1 0 3"/><path d="M17 14a2.2 2.2 0 1 1 3 3 2.2 2.2 0 0 1-3 0"/>',
  ear: '<path d="M7 18a5 5 0 0 1-1-3V9a6 6 0 1 1 12 0c0 3-3 3.5-3 6a3 3 0 0 1-5.5 1.6"/>',
  skin: '<circle cx="12" cy="12" r="9"/><path d="M8.5 9.5h.01M14 8h.01M10 14.5h.01M15.5 13.5h.01"/>',
  fileText:
    '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h4"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/>',
  download:
    '<path d="M12 4v12M7 11l5 5 5-5"/><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h9"/>',
  star: '<path d="m12 2.6 2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 17.5l-5.9 3.1 1.2-6.5L2.5 9.5l6.6-.9Z"/>',
};

/** Render an inline stroked icon. */
export function icon(name, className = "") {
  const path = PATHS[name] || PATHS.info;
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"${
      className ? ` class="${className}"` : ""
    }>${path}</svg>`;
}

/** Filled star, used only for ratings. */
export function starIcon(filled) {
  return `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"${
    filled ? "" : ' class="is-empty"'
  }>${PATHS.star}</svg>`;
}

/** A five-star row for the given rating. */
export function stars(rating) {
  const rounded = Math.round(Math.max(0, Math.min(5, Number(rating) || 0)));
  return `<span class="stars" role="img" aria-label="${rounded} out of 5">${Array.from(
    { length: 5 },
    (_, index) => starIcon(index < rounded)
  ).join("")}</span>`;
}

/** Best-guess icon for a specialty slug. */
export function specialtyIcon(slug) {
  const map = {
    cardiologist: "shield",
    dermatologist: "skin",
    "ent-specialist": "ear",
    neurologist: "brain",
    orthopedic: "bone",
    "general-physician": "stethoscope",
  };
  return icon(map[slug] || "stethoscope");
}
