# 01: Scaffold the Lindra service, its commands and the UI shell

**Track:** scaffold

**What to build:** A developer clones the repository, runs the commands named in `AGENTS.md`, and gets a running German web service with one health endpoint, a passing test suite, a passing linter and a green CI run. Opening the service in a browser shows the application shell on the chosen UI foundation: the sidebar region, the top-right status area and the stable action bar from ADR 0008, styled with the Quiet Clarity tokens derived from the brand kit (ADR 0009), with no product behaviour behind them yet. Every later ticket builds inside this skeleton and follows its test pattern.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

**Spec:** `docs/prd/lindra-first-release.md`; ADR 0005 (Python web service, SQLite, server-driven browser UI, single protected user), ADR 0008 (shell regions), ADR 0009 (UI foundation, brand kit, unslop).

## Acceptance criteria

- [ ] `AGENTS.md` names the commands to install, run, test, lint and format the project, and states the unslop requirement for UI work: read the unslop skill and its signs before work, check the final diff against the signs, name the signs checked and remaining findings in the proof.
- [ ] A Python web service starts locally, serves German pages, and answers a health endpoint used by later environment checks.
- [ ] One HTTP API test exists and passes; it is the pattern every later ticket follows (drive the API, assert what the physician would observe, no assertions on internals).
- [ ] Lint and format commands pass on a clean tree; CI runs install, lint and tests on every push and is green.
- [ ] The UI foundation is in place per ADR 0009: daisyUI 5 component CSS over native semantic HTML controls, pinned and self-hosted together with fonts and icons; no runtime CDN asset, no React or Web Awesome runtime; light theme only.
- [ ] Quiet Clarity tokens are derived from the brand kit palette (Teal, Sage, Ink, Paper, White) and every text-on-surface and accent combination used in the shell passes a 4.5 to 1 contrast check; the results and any adjusted values are recorded in the repository.
- [ ] Readable repo-local copies of the brand assets and guidance are present (obtained from the operator); the logo appears in the shell only where the layout has a place for it; nobody claims to have read assets that were not available.
- [ ] A sample page shows the shell: sidebar region (empty list with "Fall auswählen"), top-right status area that never shifts layout and never looks like a button, and a bottom action bar whose buttons keep stable size and position while content scrolls; it works on an iPad-sized portrait viewport with the sidebar as a drawer and on a desktop viewport.
- [ ] Accessibility baseline on the sample page: visible keyboard focus, states that do not rely on colour alone, reduced-motion respected, touch targets of at least 44 by 44 CSS pixels.
- [ ] The target-browser check for the CSS distribution is recorded (latest two major Safari and iPadOS, current desktop Chrome, Firefox, Edge, Safari). If the check fails, the ticket stops and brings a Bootstrap alternative back to the operator for decision instead of substituting silently.
- [ ] Operator-run, before merge: on Ella's physical iPad in Safari over the private network, the sample page renders, controls are tappable at 44 by 44 CSS pixels, keyboard focus is visible with an external keyboard, reduced motion is respected, and the drawer opens and closes in portrait.
- [ ] Unslop: the unslop skill and `references/signs.md` were read before work; the final diff was checked against the signs; the proof names the signs checked and any remaining finding with its reason. No unrelated redesign, no story video, no image generation.
