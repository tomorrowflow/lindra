# 05: Cases with a treatment period and the sidebar entry point

**Track:** case

**What to build:** Behind the token login from ticket 01, the physician sees the sidebar list her cases by case number with the patient name as subtitle, and starts on "Fall auswählen" with nothing preselected. She creates a case with a case number, a required patient name, an optional label, the admission assessment's date and time and the inclusive treatment period; the form validates inline. Selecting a case shows its overview. She can correct the period later and is refused, with the conflicting encounters named, when the new period would strand one. She can delete a case. `reset` now seeds the fictional cast into case storage through the hook from ticket 02.

**Blocked by:** 01 (Scaffold), 02 (Environments)

**Status:** ready-for-agent

**Spec:** PRD stories 1 to 4c, 42; ADR 0002, ADR 0005, ADR 0008 (sidebar, status area, action bar), ADR 0010 (cases and treatment period).

## Acceptance criteria

- [ ] Every case page and API route sits behind the token login from ticket 01; this ticket adds no second mechanism, no registration and no role.
- [ ] The sidebar lists cases by case number with the patient name and the period as subtitle; with no case selected the main area says "Fall auswählen" and offers "Neuer Fall"; no case is ever preselected.
- [ ] Creating a case requires case number, patient name, assessment date and time and the inclusive period (Behandlungsbeginn, Behandlungsende); the label is optional; the assessment date must lie in the period; end before start is refused; errors show inline without moving the form's buttons.
- [ ] The case overview shows number, patient name, label, period with "Ändern", the assessment date and the encounter list (encounters themselves arrive in ticket 06; here the assessment entry exists).
- [ ] Correcting the period refuses a change that would leave the assessment or any encounter outside, names the conflicting encounters with their dates, disables saving, and changes nothing; a valid change saves and is visible in the sidebar.
- [ ] Deleting a case removes it and everything under it after a confirmation; nothing else is deleted.
- [ ] `scripts/env.py reset` seeds the three fictional cases into case storage via the seed hook; `check` confirms they are present; the cast remains the only dataset.
- [ ] HTTP API tests cover that case routes refuse requests without the token, case creation validation, period conflict refusal, overview, delete and seeding; a pure logic test covers period conflict detection.
- [ ] Portrait viewport: the sidebar is a drawer behind a button in the top bar; case switching works from it.
- [ ] Unslop: the unslop skill and `references/signs.md` were read before work; the final diff was checked against the signs; the proof names the signs checked and any remaining finding with its reason.

## Proof

- Test, lint and CI green on the ticket branch; the report quotes the commands and names the new API and logic tests.
- On a throwaway stack: `scripts/env.py up`, `reset`, `check` pass and the three fictional cases appear in the sidebar; quoted in the report.
- Screenshots of "Fall auswählen", the new-case form with a validation error, the overview and the refused period change, on an iPad-sized portrait viewport (drawer open and closed) and a desktop viewport, committed under `docs/screenshots/`.
- Unslop proof: the signs checked and any remaining finding with its reason.
