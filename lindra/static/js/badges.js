// A state badge opens its explanation on tap. The explanation is already in the page,
// hidden; the button and the text are joined by aria-controls. One explanation is open
// at a time, and Escape closes it.

const buttons = document.querySelectorAll(".badge-button");

function close(button) {
  button.setAttribute("aria-expanded", "false");
  document.getElementById(button.getAttribute("aria-controls")).hidden = true;
}

for (const button of buttons) {
  button.addEventListener("click", () => {
    const opening = button.getAttribute("aria-expanded") !== "true";
    for (const other of buttons) close(other);
    if (!opening) return;
    button.setAttribute("aria-expanded", "true");
    document.getElementById(button.getAttribute("aria-controls")).hidden = false;
  });
}

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  for (const button of buttons) close(button);
});
