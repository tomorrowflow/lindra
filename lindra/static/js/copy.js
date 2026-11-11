// Copy controls: each puts the text of one section of the current draft on the clipboard as
// plain text and says so, in the status area and on the button itself, for a moment. The
// text is already in the page (or is the text area the physician is looking at), so the copy
// happens inside the tap, which Safari requires. Afterwards the server is told the section
// was copied, which gives it the "Kopiert" badge; a failure there changes nothing the
// physician sees.

import { flushAll } from "./autosave.js";
import { setStatus } from "./status.js";

const SHOWN_MS = 2500;

async function writeText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const probe = document.createElement("textarea");
  probe.value = text;
  probe.readOnly = true;
  probe.style.cssText = "position:fixed;opacity:0";
  document.body.appendChild(probe);
  probe.select();
  const done = document.execCommand("copy");
  probe.remove();
  if (!done) throw new Error("copy refused");
}

for (const button of document.querySelectorAll("[data-copy]")) {
  const label = button.querySelector("span");
  const original = label.textContent;
  let timer = null;

  button.addEventListener("click", async () => {
    const source = button.dataset.copyFrom
      ? document.querySelector(button.dataset.copyFrom).value
      : button.dataset.copyText;
    clearTimeout(timer);
    try {
      await writeText(source);
    } catch {
      setStatus("copy", "copy-failed");
      timer = setTimeout(() => setStatus("copy", null), SHOWN_MS);
      return;
    }
    setStatus("copy", "copied");
    label.textContent = "Kopiert";
    timer = setTimeout(() => {
      setStatus("copy", null);
      label.textContent = original;
    }, SHOWN_MS);
    await flushAll();
    await fetch(button.dataset.copiedUrl, { method: "POST", credentials: "same-origin" });
  });
}
