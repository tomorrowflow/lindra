// Autosave for a text area: the notes and the text of a section. There is no save button: a
// pause in typing saves the text, leaving the tab saves it, and coming back online saves it
// again. The status area shows one of four states; a failed save also shows the separate
// retry button. Nothing here moves a button: the indicator has a fixed width and the retry
// button's place is always reserved (see quiet-clarity.css).

import { setStatus } from "./status.js";

const PAUSE_MS = 800;
const saves = [];

// `payload(text)` is the JSON body; `onSaved(json)` runs after every good save.
export function autosave({ area, url, payload, retry, onSaved }) {
  let savedText = area.value;
  let state = "saved";
  let timer = null;
  let inFlight = false;

  function show(next) {
    state = next;
    setStatus("save", next);
    retry.hidden = next !== "offline" && next !== "failed";
  }

  function request(text) {
    return fetch(url, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload(text)),
      credentials: "same-origin",
    });
  }

  // `manual` is a tap on the retry button or the network coming back. A save that only
  // follows typing after a failure tries again without changing the status until it ends.
  async function save(manual = false) {
    clearTimeout(timer);
    // The save in flight looks at the text again when it ends.
    if (inFlight) return;
    const text = area.value;
    if (text === savedText) {
      show("saved");
      return;
    }
    inFlight = true;
    if (manual || state === "saved" || state === "saving") show("saving");
    let outcome;
    try {
      const response = await request(text);
      if (response.ok) {
        savedText = text;
        await onSaved(await response.json());
        outcome = "saved";
      } else {
        outcome = "failed";
      }
    } catch {
      outcome = "offline";
    }
    inFlight = false;
    if (outcome === "saved" && area.value !== savedText) {
      save();
    } else {
      show(outcome);
    }
  }

  // Resolves when everything typed is saved, or when saving fails.
  async function flush() {
    clearTimeout(timer);
    while (inFlight || area.value !== savedText) {
      if (inFlight) {
        await new Promise((resolve) => setTimeout(resolve, 50));
      } else {
        await save(true);
      }
      if (state === "failed" || state === "offline") return;
    }
  }

  area.addEventListener("input", () => {
    clearTimeout(timer);
    if (state === "saved" || state === "saving") show("saving");
    timer = setTimeout(save, PAUSE_MS);
  });

  // The retry button hides after a good save; the caret goes back to the text first, so
  // focus never falls onto a button that is about to disappear.
  retry.addEventListener("click", () => {
    area.focus();
    save(true);
  });
  window.addEventListener("online", () => {
    if (state === "offline") save(true);
  });

  // Leaving the tab (an iPad switching apps) saves at once.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") save();
  });

  // Ask before the tab closes with text that is not saved.
  window.addEventListener("beforeunload", (event) => {
    if (area.value === savedText) return;
    event.preventDefault();
  });

  saves.push(flush);
  return { save, flush };
}

// Everything the physician typed on this page is saved, or saving failed.
export function flushAll() {
  return Promise.all(saves.map((flush) => flush()));
}
