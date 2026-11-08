# 06: Encounters: the admission assessment, dated visits and per-encounter notes

**Track:** case

**What to build:** A selected case shows its admission assessment and its dated visits in the sidebar and the overview, with "Neue Visite". The physician creates a visit whose date is constrained to the treatment period, defaults to now when now lies inside it and to nothing otherwise, with the time free within the day and backdating allowed. Each encounter has its own notes step: free text typed or pasted, autosaved with a notes revision, with saving, unsaved and failed-save states in the top-right status area and a separate retry button. Encounter badges in the sidebar show the encounter's state; review steps expand only beneath the selected encounter. In portrait the drawer switches case and encounter.

**Blocked by:** 01 (Scaffold), 02 (Environments), 05 (Cases and periods)

**Status:** ready-for-agent

**Spec:** PRD stories 3, 4a, 4b, 5 to 8, 7a, 7b, 9b; ADR 0008 (sidebar, status area, action bar), ADR 0010 (encounters).

## Acceptance criteria

- [ ] Each case has exactly one admission assessment (dated at creation) and any number of visits; each encounter has its own date and time, notes, notes revision and later its own draft state.
- [ ] "Neue Visite" opens a form whose date picker is limited to the period; the default is now when now is in the period and empty otherwise, with a note that says so; the time is editable within the chosen day; a date outside the period is refused; backdating inside the period works and the visit sorts by date.
- [ ] The notes step shows the encounter's free text area; every saved change advances the notes revision; autosave happens without a save button; the status area shows saved, saving, not saved (network lost) and failed save; retry is a distinct button; no status change moves or covers the action bar.
- [ ] The sidebar shows cases, then the selected case's encounters with status badges (icons, explanation on tap), then the selected encounter's steps; other encounters keep their badges; the case header shows number and patient name.
- [ ] Portrait viewport: the drawer lists cases and encounters and switching from it works; the action bar keeps stable button sizes and positions across steps and orientations.
- [ ] HTTP API tests cover visit creation inside, outside and before now, notes autosave and revision, and failed save with retry; a pure logic test covers the default visit date.
- [ ] Unslop: the unslop skill and `references/signs.md` were read before work; the final diff was checked against the signs; the proof names the signs checked and any remaining finding with its reason.

## Proof

- Test, lint and CI green; the report names the new API and logic tests (visit creation inside, outside and backdated; autosave and revision; failed save and retry; default visit date).
- On a throwaway stack after `reset`: the fictional case with a backdated visit shows its encounters in date order; a visit outside the period is refused; quoted or screenshotted.
- Screenshots of the new-visit form in both default states (now inside the period, now outside), the notes step with the saved and the not-saved status, and the sidebar with encounter badges, on both viewports, committed under `docs/screenshots/`; the action bar position is identical across the notes step screenshots.
- Unslop proof: the signs checked and any remaining finding with its reason.
