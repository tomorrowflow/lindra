// The section step: the current-draft pane saves as the physician types (autosave.js). A
// saved change makes the section "manuell bearbeitet" and takes the input reference off every
// paragraph she rewrote, so the title badges, the state line and the list of origins are
// fetched again from the server after each save; nothing else on the page moves. The copy
// control in the action bar is only enabled while the pane holds text.

import { autosave } from "./autosave.js";

const area = document.querySelector("[data-section]");
const copy = document.querySelector("[data-copy]");

async function refresh(url, selector) {
  const response = await fetch(url, { credentials: "same-origin" });
  if (!response.ok) return;
  const target = document.querySelector(selector);
  const open = new Set(
    [...target.querySelectorAll("details[open] .origin-quote")].map((quote) => quote.textContent),
  );
  target.outerHTML = await response.text();
  // A reference the physician had open stays open when its paragraph is still generated.
  for (const quote of document.querySelectorAll(`${selector} .origin-quote`)) {
    if (open.has(quote.textContent)) quote.closest("details").open = true;
  }
}

function refreshHead() {
  const base = area.dataset.headUrl.replace(/\/kopf$/, "");
  return Promise.all([
    refresh(area.dataset.headUrl, "#section-head"),
    refresh(`${base}/herkunft`, "#section-origins"),
  ]);
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
