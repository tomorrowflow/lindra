// The section step: the current-draft pane saves as the physician types (autosave.js). A
// saved change makes the section "manuell bearbeitet", so the title badges and the state line
// are fetched again from the server after each save; nothing else on the page moves. The copy
// control in the action bar is only enabled while the pane holds text.

import { autosave } from "./autosave.js";

const area = document.querySelector("[data-section]");
const copy = document.querySelector("[data-copy]");

async function refreshHead() {
  const response = await fetch(area.dataset.headUrl, { credentials: "same-origin" });
  if (!response.ok) return;
  const head = document.querySelector("#section-head");
  head.outerHTML = await response.text();
}

function updateCopy() {
  copy.disabled = area.value.trim() === "";
}

autosave({
  area,
  url: area.dataset.saveUrl,
  payload: (text) => ({ text }),
  retry: document.querySelector("[data-retry]"),
  onSaved: refreshHead,
});
area.addEventListener("input", updateCopy);
