// Dictation (ADR 0004): the microphone control opens a modal overlay that records, waits for
// the transcript, lets the physician correct it and then accepts it into the notes or discards
// it. Nothing records before the tap on the control; the browser captures audio only between
// that tap and "Aufnahme beenden", sends it to the service for transcription and drops it. The
// service never stores it. There is no browser or operating-system speech recognition here.
//
// The overlay is a modal <dialog>: everything behind it is inert, and Escape does nothing,
// because the dictation ends only by accepting, discarding or closing a failure message.

import { flushAll } from "./autosave.js";

const dialog = document.querySelector("dialog.dictation");
const control = document.querySelector("[data-dictate]");

if (dialog && control) {
  const panel = (state) => dialog.querySelector(`[data-state="${state}"]`);
  const field = dialog.querySelector("[data-transcript]");
  const accept = dialog.querySelector("[data-accept]");
  const discard = dialog.querySelector("[data-discard]");
  const outdates = dialog.querySelector("[data-outdates]");
  const acceptError = dialog.querySelector("[data-accept-error]");
  const elapsed = dialog.querySelector("[data-elapsed]");
  const TYPES = ["audio/webm;codecs=opus", "audio/mp4", "audio/ogg;codecs=opus"];

  let stream = null;
  let recorder = null;
  let ticker = null;
  let recording = null; // the blob being transcribed, kept only so a retry can send it again
  let retry = null;
  let ended = true; // false from the tap on the control until a button ends the dictation
  let current = null; // the panel showing
  let dictationId = null; // names the transcript under review
  let maybeAppended = false; // an accept of this transcript may have been saved unseen

  // The service did not answer, or failed after it may have saved: the append may have happened.
  // The text is locked meanwhile: the service keeps the first text it received for this id.
  const UNSURE =
    "Ob der Text schon in den Notizen steht, ist unklar. Versuchen Sie es erneut. Ein schon übernommener Text wird nicht doppelt eingefügt. Bis dahin lässt sich der Text nicht ändern.";

  function newId() {
    if (crypto.randomUUID) return crypto.randomUUID();
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  }

  function show(state) {
    current = state;
    for (const item of dialog.querySelectorAll("[data-state]")) item.hidden = item.dataset.state !== state;
    // Focus goes to what the physician does next; a panel with nothing to tap takes it itself,
    // so a screen reader announces the new state.
    const target = panel(state).querySelector("textarea, .btn-primary") ?? panel(state).querySelector(".dialog-body");
    if (!target.matches("textarea, button")) target.setAttribute("tabindex", "-1");
    target.focus();
  }

  function fail(title, message, again) {
    dialog.querySelector("[data-failed-title]").textContent = title;
    dialog.querySelector("[data-failed-message]").textContent = message;
    retry = again;
    show("failed");
  }

  function release() {
    clearInterval(ticker);
    if (stream) for (const track of stream.getTracks()) track.stop();
    stream = null;
    recorder = null;
  }

  function close() {
    release();
    recording = null;
    retry = null;
    field.value = "";
    field.readOnly = false;
    maybeAppended = false;
    ended = true;
    dialog.close();
    control.focus();
  }

  const clock = (seconds) => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

  async function start() {
    release();
    recording = null;
    show("starting");
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      fail(
        "Aufnahme nicht möglich",
        "Dieser Browser oder diese Verbindung erlaubt keine Aufnahme. Das Mikrofon braucht eine gesicherte Verbindung (HTTPS).",
        start,
      );
      return;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      if (error.name === "NotFoundError" || error.name === "OverconstrainedError") {
        fail("Kein Mikrofon gefunden", "An diesem Gerät ist kein Mikrofon verfügbar.", start);
      } else if (error.name === "NotAllowedError" || error.name === "SecurityError") {
        fail(
          "Mikrofon nicht erlaubt",
          "Lindra darf das Mikrofon nicht benutzen. Erlauben Sie es in den Einstellungen des Browsers für diese Seite und versuchen Sie es dann erneut.",
          start,
        );
      } else {
        fail("Aufnahme nicht möglich", "Das Mikrofon lässt sich gerade nicht benutzen.", start);
      }
      return;
    }
    const type = TYPES.find((candidate) => MediaRecorder.isTypeSupported?.(candidate));
    const chunks = [];
    recorder = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
    recorder.addEventListener("dataavailable", (event) => {
      if (event.data?.size) chunks.push(event.data);
    });
    recorder.addEventListener("stop", () => {
      const mime = recorder?.mimeType || chunks[0]?.type || "application/octet-stream";
      release();
      const blob = new Blob(chunks, { type: mime });
      if (!blob.size) {
        fail("Nichts aufgenommen", "Es kam kein Ton an. Prüfen Sie das Mikrofon und versuchen Sie es erneut.", start);
        return;
      }
      transcribe(blob);
    });
    recorder.addEventListener("error", () => {
      release();
      fail("Aufnahme abgebrochen", "Die Aufnahme wurde unterbrochen. Versuchen Sie es erneut.", start);
    });
    const began = Date.now();
    elapsed.textContent = clock(0);
    ticker = setInterval(() => {
      elapsed.textContent = clock(Math.floor((Date.now() - began) / 1000));
    }, 500);
    recorder.start();
    show("recording");
  }

  async function transcribe(blob) {
    recording = blob;
    show("transcribing");
    let response;
    try {
      response = await fetch(dialog.dataset.transcriptUrl, {
        method: "POST",
        headers: { "Content-Type": blob.type },
        body: blob,
        credentials: "same-origin",
      });
    } catch {
      fail(
        "Keine Verbindung",
        "Der Dienst ist nicht erreichbar. Die Aufnahme ist noch hier: Versuchen Sie es erneut, sobald die Verbindung steht.",
        () => transcribe(blob),
      );
      return;
    }
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      fail("Text nicht erstellt", body.detail || "Aus der Aufnahme konnte kein Text erstellt werden.", () => transcribe(blob));
      return;
    }
    const result = await response.json();
    recording = null;
    // One id per transcript, kept for every attempt to accept it: the service adds the passage
    // once however often the same id arrives.
    dictationId = newId();
    maybeAppended = false;
    discard.disabled = false;
    field.readOnly = false;
    field.value = result.transcript;
    outdates.hidden = !result.outdates_proposal;
    acceptError.hidden = true;
    accept.disabled = !field.value.trim();
    show("reviewing");
  }

  function rejected(message, locked = false) {
    field.readOnly = locked;
    acceptError.querySelector("span").textContent = message;
    acceptError.hidden = false;
    acceptError.scrollIntoView({ block: "nearest" });
    accept.disabled = !field.value.trim();
    discard.disabled = false;
  }

  // Appending runs on the service, to the notes as they are saved there, so what was typed on
  // this page has to be saved first; the page then reloads to show the notes as they are now.
  // While the request is on its way the transcript can be neither accepted again nor discarded:
  // the service may save the passage after the overlay was closed over the old notes.
  async function acceptTranscript() {
    acceptError.hidden = true;
    accept.disabled = true;
    discard.disabled = true;
    if (!(await flushAll())) {
      rejected("Ihre Notizen sind noch nicht gespeichert. Der Text bleibt hier, bis Sie es erneut versuchen.");
      return;
    }
    let response;
    try {
      response = await fetch(dialog.dataset.acceptUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dictation_id: dictationId, transcript: field.value }),
        credentials: "same-origin",
      });
    } catch {
      maybeAppended = true;
      rejected(UNSURE, true);
      return;
    }
    if (response.status >= 500) {
      maybeAppended = true;
      rejected(UNSURE, true);
      return;
    }
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      const detail = body.errors?.transcript || body.detail;
      rejected(`${detail || "Der Text konnte nicht übernommen werden."} Die Notizen sind unverändert.`);
      return;
    }
    // The overlay stays up until the page behind it shows the new notes.
    if (location.pathname === dialog.dataset.notesUrl) {
      location.reload();
    } else {
      location.assign(dialog.dataset.notesUrl);
    }
  }

  control.addEventListener("click", () => {
    ended = false;
    dialog.showModal();
    start();
  });
  dialog.querySelector("[data-stop]").addEventListener("click", () => recorder?.state === "recording" && recorder.stop());
  // Discarding changes nothing, unless an accept may have reached the service without its
  // answer arriving. Then the page behind still shows the notes from before, and the next
  // thing the physician typed would save over the passage. Reloading shows the notes as saved.
  discard.addEventListener("click", () => {
    if (!maybeAppended) {
      close();
    } else {
      location.reload();
    }
  });
  dialog.querySelector("[data-close]").addEventListener("click", close);
  dialog.querySelector("[data-retry-dictation]").addEventListener("click", () => retry?.());
  accept.addEventListener("click", acceptTranscript);
  field.addEventListener("input", () => {
    accept.disabled = !field.value.trim();
  });
  // Escape would close the overlay with a transcript in it; only the buttons end a dictation.
  // A browser still closes the dialog on a second Escape without a tap in between, whatever
  // `cancel` did, so a close the buttons did not ask for puts the overlay back as it was.
  dialog.addEventListener("cancel", (event) => event.preventDefault());
  dialog.addEventListener("close", () => {
    if (!ended) {
      dialog.showModal();
      show(current);
    }
  });
}
