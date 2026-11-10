// The case dialogs arrive from the server as open <dialog> elements, so they work
// before this script runs. Here they become modals: focus stays inside, Escape
// returns to the page behind, and the period dialog checks the dates as they change.

for (const dialog of document.querySelectorAll("dialog[data-return]")) {
  dialog.removeAttribute("open");
  dialog.showModal();
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    window.location.assign(dialog.dataset.return);
  });
  const form = dialog.querySelector("form[data-check]");
  if (form) watchPeriod(form);
}

// The note under the new-visit fields says where the starting values came from. Once
// the physician changes one of them it no longer applies.
const visitNote = document.querySelector("#visit-note");
if (visitNote) {
  for (const name of ["visit_date", "visit_time"]) {
    document.getElementById(name).addEventListener("input", () => {
      visitNote.textContent = "";
    });
  }
}

function watchPeriod(form) {
  const save = form.querySelector("[data-save]");
  let latest = 0;
  form.addEventListener("input", async () => {
    const mine = ++latest;
    const query = new URLSearchParams({
      period_start: form.elements.period_start.value,
      period_end: form.elements.period_end.value,
    });
    let html;
    try {
      const response = await fetch(`${form.dataset.check}?${query}`);
      // A redirect means the login expired; the form then fails on submit with the login page.
      if (!response.ok || response.redirected) return;
      html = await response.text();
    } catch {
      return;
    }
    if (mine !== latest) return;
    form.querySelector("#period-feedback").outerHTML = html;
    save.disabled = form.querySelector("#period-feedback").dataset.ok !== "true";
  });
}
