# 07: Assessment review: generation, step-per-section comparison, whole-draft proposal and handover

**Track:** draft

**What to build:** From the assessment's notes the physician asks for a draft and gets one proposal for the seven form-aligned sections, generated through the text model adapter with the fixture model. She reviews one section per step with the current draft and the proposal side by side (stacked in portrait), edits sections by hand, and accepts or discards the proposal as a whole in the final step, which names what is replaced and what stays manual. Acceptance never overwrites her edits; a proposal generated from older notes is refused with a visible reason; a changed-notes marker says the draft is possibly outdated. The handover step and a small control on each section step copy sections of the current draft as plain text with a visible acknowledgement. This ticket also delivers the first half of the browser flow.

**Blocked by:** 01 (Scaffold), 02 (Environments), 05 (Cases and periods), 06 (Encounters and notes)

**Status:** ready-for-agent

**Spec:** PRD stories 17, 18, 18d, 19 to 24b; ADR 0001 (intended purpose), ADR 0003 (adapters and stand-ins), ADR 0008 (proposal semantics, layout), ADR 0010 (assessment sections).

## Acceptance criteria

- [ ] "Entwurf erzeugen" is the only way a draft or proposal comes into being; while generation runs the status area shows it and the physician can keep reading; nothing is generated on save, on open or on a timer.
- [ ] The text model adapter interface exists with the fixture model implementation keyed to the fictional cast; the result is structured (sections, paragraphs, input references, clarification items); unstructured prose counts as a failed generation.
- [ ] The assessment draft has exactly the seven sections of ADR 0010 in the form's order, with the distinct subsection headings inside Therapeutische Anamnese and Untersuchungsbefunde preserved.
- [ ] One step per section: title with badges, a one-line state with icon and "Mehr", two large panes (current draft, proposal), the section's clarification items, and an action bar with back, next, discard, copy; steps are reachable in any order from the sidebar; portrait stacks the panes.
- [ ] A proposal is one object for the whole draft bound to the notes revision; the final step "Übernehmen" lists the sections to be replaced and the manually edited sections that stay, then accepts with one action; no per-section acceptance control exists.
- [ ] Acceptance replaces only sections without the manually-edited flag, including sections edited while the proposal was pending; retained sections carry the "Nicht aktualisiert" badge with the word spelled out on the active section; the clarification list of the proposal becomes the encounter's; the acceptance counter increments.
- [ ] A proposal whose notes revision is not the current one is outdated: it stays visible, acceptance is disabled with the reason spelled out next to it ("Veraltet: Notizen seit diesem Vorschlag geändert"), and only discard and explicit regeneration are offered.
- [ ] When the notes revision moves past the draft's, one encounter-wide marker says the draft is possibly outdated; no per-section staleness is guessed; the marker clears only when a proposal from the current notes is accepted.
- [ ] A failed generation leaves notes and draft untouched and reports plainly in the status area with a retry button.
- [ ] Each section can be edited in place as free text; the edited section loses its input references and gets the manually edited badge.
- [ ] Handover step: one copy control per section of the current accepted draft, plain text, visible acknowledgement, never the pending proposal; an encounter without an accepted draft says there is nothing to copy; the same copy control exists on each section step.
- [ ] Browser flow, first half, on an iPad-sized portrait viewport and a desktop viewport: open a case from "Fall auswählen", open the assessment, type notes, generate, hand-edit a section, accept with that section retained and badged, change notes while a proposal is pending and see acceptance disabled with its reason, copy a section from the handover step and see the acknowledgement; buttons keep their size and position across steps.
- [ ] HTTP API and pure logic tests cover the acceptance merge, outdated detection by notes revision, staleness, failure preservation and copy text; tests use the fixture model only.
- [ ] Unslop: the unslop skill and `references/signs.md` were read before work; the final diff was checked against the signs; the proof names the signs checked and any remaining finding with its reason.

## Proof

- Test, lint and CI green; the report names the API and logic tests for generation, the acceptance merge, outdated detection, staleness, failure preservation and copy text, all on the fixture model.
- The browser flow (first half) runs green in CI on both viewports; its screenshots of the section step with a proposal, the final step naming replaced and retained sections, the outdated proposal with the spelled-out reason, and the handover step are committed under `docs/screenshots/`.
- On a throwaway stack after `reset`: the first fictional case is generated, one section hand-edited, the proposal accepted, and the retained section shows "Nicht aktualisiert"; quoted or screenshotted.
- Unslop proof: the signs checked and any remaining finding with its reason.
