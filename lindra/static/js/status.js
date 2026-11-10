// The status area shows the most urgent of several sources: a generation in progress or
// failed, then a short "Kopiert", then the save state of the text being typed. Every state
// is a text with an icon in the page's template (templates/status.html), so this script only
// picks one. It never touches a button and the area keeps its width, so nothing moves.

const indicator = document.querySelector("[data-save-indicator]");
const states = document.querySelector("#status-states").content;
const ORDER = ["generation", "copy", "save"];
const chosen = { generation: null, copy: null, save: "saved" };

// The page arrives showing a generation that runs or failed; the server rendered that.
const arrived = document.querySelector("[data-generation]")?.dataset.generation;
if (arrived === "running") chosen.generation = "generating";
if (arrived === "failed") chosen.generation = "generation-failed";

// `state` is a key of the template, or null when the source has nothing to say.
export function setStatus(source, state) {
  chosen[source] = state;
  const key = ORDER.map((name) => chosen[name]).find(Boolean);
  const node = states.querySelector(`[data-state="${key}"]`);
  indicator.className = `status-indicator status-${node.dataset.tone}`;
  indicator.innerHTML = node.innerHTML;
}
