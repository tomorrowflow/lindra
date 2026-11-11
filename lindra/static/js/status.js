// The status area shows the most urgent of several sources. A text that is not saved comes
// first, because the physician must not miss it; then a generation in progress or failed,
// then a short "Kopiert", then the save state "Gespeichert" or "Speichert". Every state is a
// text with an icon in the page's template (templates/status.html), so this script only picks
// one. It never touches a button and the area keeps its width, so nothing moves.

const indicator = document.querySelector("[data-save-indicator]");
const states = document.querySelector("#status-states").content;
const ORDER = ["generation", "copy", "save"];
const SAVE_PROBLEMS = ["offline", "failed"];
const chosen = { generation: null, copy: null, save: "saved" };

// The page arrives showing a generation that runs or failed; the server rendered that.
const arrived = document.querySelector("[data-generation]")?.dataset.generation;
if (arrived === "running") chosen.generation = "generating";
if (arrived === "failed") chosen.generation = "generation-failed";

// `state` is a key of the template, or null when the source has nothing to say.
export function setStatus(source, state) {
  chosen[source] = state;
  const problem = SAVE_PROBLEMS.includes(chosen.save) ? chosen.save : null;
  const key = problem ?? ORDER.map((name) => chosen[name]).find(Boolean);
  const node = states.querySelector(`[data-state="${key}"]`);
  indicator.className = `status-indicator status-${node.dataset.tone}`;
  indicator.innerHTML = node.innerHTML;
}
