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

  // Resolves with true when everything typed is saved, with false when saving fails.
  async function flush() {
    clearTimeout(timer);
    while (inFlight || area.value !== savedText) {
      if (inFlight) {
        await new Promise((resolve) => setTimeout(resolve, 50));
      } else {
        await save(true);
      }
      if (state === "failed" || state === "offline") return false;
    }
    return true;
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

  saves.push({ flush, dirty: () => area.value !== savedText });
  return { save, flush };
}

// True when everything the physician typed on this page is saved, false when saving failed.
export async function flushAll() {
  const results = await Promise.all(saves.map((entry) => entry.flush()));
  return results.every(Boolean);
}

const unsaved = () => saves.some((entry) => entry.dirty());

// Following a link or sending a form with unsaved text saves it first, so a tap on Weiter or
// Übernehmen never leaves a hand edit behind (an iPad does not ask before leaving). If the
// save fails the page stays and the status area says so.
document.addEventListener("click", async (event) => {
  const link = event.target.closest("a[href]");
  const plain = event.button === 0 && !(event.metaKey || event.ctrlKey || event.shiftKey);
  if (!link || event.defaultPrevented || !plain || link.target || !unsaved()) return;
  event.preventDefault();
  if (await flushAll()) location.assign(link.href);
});

document.addEventListener("submit", async (event) => {
  if (event.defaultPrevented || !unsaved()) return;
  event.preventDefault();
  if (await flushAll()) event.target.submit();
});
