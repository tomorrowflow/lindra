// Autosave for the notes step. There is no save button: a pause in typing saves the
// text, leaving the tab saves it, and coming back online saves it again. The status
// area shows one of four states; a failed save also shows the separate retry button.
// Nothing here moves a button: the indicator has a fixed width and the retry button's
// place is always reserved (see quiet-clarity.css).

const area = document.querySelector("[data-notes]");
const indicator = document.querySelector("[data-save-indicator]");
const retry = document.querySelector("[data-retry]");
const states = document.querySelector("#save-states").content;
const badge = document.querySelector(".encounter-link.current ~ .badge-button");
const badgeStates = document.querySelector("#badge-states").content;

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

// The sidebar badge of this encounter follows the notes: empty or not.
function updateBadge(text) {
  const source = badgeStates.querySelector(`[data-state="${text.trim() ? "notes" : "empty"}"]`);
  badge.setAttribute("aria-label", `Zustand: ${source.dataset.label}`);
  badge.innerHTML = source.innerHTML;
  document.getElementById(badge.getAttribute("aria-controls")).textContent =
    source.dataset.explanation;
}

function request(text) {
  return fetch(area.dataset.saveUrl, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ notes: text }),
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
      area.dataset.revision = (await response.json()).notes_revision;
      updateBadge(text);
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
  if (state === "saved" || state === "saving") show("saving");
  timer = setTimeout(save, PAUSE_MS);
});

// The retry button hides after a good save; the caret goes back to the notes first, so
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
