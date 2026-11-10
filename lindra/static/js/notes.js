// The notes step: autosave of the free text (autosave.js), and the sidebar badge of this
// encounter following the saved notes. The save answers with the badge the encounter has now,
// so a draft that became possibly outdated or a proposal that became outdated shows at once.

import { autosave } from "./autosave.js";

const area = document.querySelector("[data-notes]");
const badge = document.querySelector(".encounter-link.current ~ .badge-button");

function updateBadge(state) {
  badge.setAttribute("aria-label", `Zustand: ${state.label}`);
  badge.innerHTML = badgeIcon(state.icon);
  document.getElementById(badge.getAttribute("aria-controls")).textContent = state.explanation;
}

// The icon markup is the page's own: the sidebar holds an icon of every kind in a template.
function badgeIcon(name) {
  return document.querySelector(`#badge-icons [data-icon="${name}"]`).innerHTML;
}

autosave({
  area,
  url: area.dataset.saveUrl,
  payload: (text) => ({ notes: text }),
  retry: document.querySelector("[data-retry]"),
  onSaved(json) {
    area.dataset.revision = json.notes_revision;
    updateBadge(json.badge);
  },
});
