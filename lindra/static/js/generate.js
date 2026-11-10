// "Entwurf erzeugen": the only way a draft or proposal comes into being. Nothing is generated
// on save, on open or on a timer. The request runs while the physician keeps reading and
// writing; the status area says it is running. A failure is reported in the status area and
// in the line beside the generate button, and a separate retry button tries again. The page
// reloads once when the proposal is stored, after what was typed is saved.

import { flushAll } from "./autosave.js";
import { setStatus } from "./status.js";

const strip = document.querySelector("[data-generation]");

if (strip) {
  const button = strip.querySelector("[data-generate]");
  const retry = strip.querySelector("[data-retry-generation]");
  const reason = strip.querySelector("[data-generation-reason]");

  function failed(text) {
    setStatus("generation", "generation-failed");
    reason.textContent = text;
    retry.hidden = false;
    button.disabled = false;
  }

  async function generate() {
    // What was typed reaches the server first, or the proposal would be outdated on arrival.
    await flushAll();
    button.disabled = true;
    retry.hidden = true;
    reason.textContent = "";
    setStatus("generation", "generating");
    let response;
    try {
      response = await fetch(strip.dataset.generateUrl, {
        method: "POST",
        credentials: "same-origin",
      });
    } catch {
      failed("Keine Verbindung zum Dienst. Die Notizen und der Entwurf sind unverändert.");
      return;
    }
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      failed(body.detail || "Der Entwurf konnte nicht erzeugt werden.");
      return;
    }
    setStatus("generation", null);
    await flushAll();
    location.reload();
  }

  button.addEventListener("click", generate);
  retry.addEventListener("click", generate);

  // A generation started on another step of this encounter is still running: wait for it.
  if (strip.dataset.generation === "running") {
    const poll = setInterval(async () => {
      const response = await fetch(strip.dataset.stateUrl, { credentials: "same-origin" });
      if (!response.ok) return;
      if ((await response.json()).state !== "running") {
        clearInterval(poll);
        location.reload();
      }
    }, 1500);
  }
}
