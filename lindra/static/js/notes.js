// Autosave for the notes step. There is no save button: a pause in typing saves the
// text, leaving the tab saves it, and coming back online saves it again. The status
// area shows one of four states; a failed save also shows the separate retry button.
// Nothing here moves a button: the indicator has a fixed width and the retry button's
// place is always reserved (see quiet-clarity.css).

const area = document.querySelector("[data-notes]");
const indicator = document.querySelector("[data-save-indicator]");
const retry = document.querySelector("[data-retry]");
const states = document.querySelector("#save-states").content;

const PAUSE_MS = 800;

let savedText = area.value;
let state = "saved";
let timer = null;
let inFlight = false;

function show(next) {
  state = next;
  const source = states.querySelector(`[data-state="${next}"]`);
  indicator.className = `status-indicator status-${source.dataset.tone}`;
  indicator.innerHTML = source.innerHTML;
  retry.hidden = next !== "offline" && next !== "failed";
}

function request(text, keepalive = false) {
  return fetch(area.dataset.saveUrl, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ notes: text }),
    credentials: "same-origin",
    keepalive,
  });
}

async function save() {
  clearTimeout(timer);
  // The save in flight looks at the text again when it ends.
  if (inFlight) return;
  const text = area.value;
  if (text === savedText) {
    show("saved");
    return;
  }
  inFlight = true;
  show("saving");
  let outcome;
  try {
    const response = await request(text);
    if (response.ok) {
      savedText = text;
      area.dataset.revision = (await response.json()).notes_revision;
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

area.addEventListener("input", () => {
  clearTimeout(timer);
  // After a failure the status stays what it was until a save has been tried again.
  if (state === "saved" || state === "saving") show("saving");
  timer = setTimeout(save, PAUSE_MS);
});

// The retry button hides after a good save; the caret goes back to the notes first, so
// focus never falls onto a button that is about to disappear.
retry.addEventListener("click", () => {
  area.focus();
  save();
});
window.addEventListener("online", () => {
  if (state === "offline") save();
});

// Leaving the tab (an iPad switching apps, a closing tab) saves at once; a page that is
// going away uses a keep-alive request so the browser finishes it.
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState !== "hidden" || area.value === savedText) return;
  clearTimeout(timer);
  request(area.value, true).catch(() => {});
});

// Ask before the tab closes with text that is not saved.
window.addEventListener("beforeunload", (event) => {
  if (area.value === savedText) return;
  event.preventDefault();
});
