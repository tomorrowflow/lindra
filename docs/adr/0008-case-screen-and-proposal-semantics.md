---
status: accepted (layout revised 2026-11-08 after prototype rounds 2 and 3, grill 4)
date: 2026-11-08
---

# The case screen is a sidebar, a step-per-section review with a large side-by-side comparison, and one whole-draft proposal that never overwrites manual edits

Settled over three prototype rounds (`docs/prototypes/SPEC-1/case-screen.html`, `case-wizard.html`, `case-flow.html`) and grill 4.

## Layout and navigation

- A left sidebar is the entry point and the orientation: the case list first (initially "Fall auswählen", no case preselected), then the selected case's encounters (the admission assessment, the dated visits, "Neue Visite"), then the selected encounter's review steps. In portrait the sidebar becomes a drawer behind a button in the top bar, so switching case or encounter is never lost.
- The review is one step per section: step 1 the free-text notes, then one step per section showing the current draft and the proposal as two large panes side by side (stacked in portrait), then a final step that is either "Übernehmen" (while a proposal is pending) or "Übergabe" (copy each section of the current draft as plain text). Steps are reachable in any order from the sidebar; next and back are a convenience, never a required progression. Notes are never a question-by-question form.
- Dictation is reachable from every step through a persistent control. Recording, transcribing and transcript review run in a full overlay that blocks navigation and every other interaction until the transcript is accepted into the selected encounter's notes or discarded.
- State is shown as icons with a short label; the explanation opens on tap. No long state sentences on the screen (operator feedback, 2026-11-08).

## Proposal semantics (per encounter)

- A generation produces one proposal for the whole draft of one encounter. It is accepted or discarded with one action; there are no per-section accept controls.
- A proposal is bound to the notes revision it was generated from and, for a visit, to its background revision (ADR 0010). When either moves on, the proposal stays visible, cannot be accepted, and is labelled accordingly. The physician discards it and regenerates explicitly. Lindra never regenerates on its own and an outdated proposal never clears a stale marking.
- Accepting replaces only sections the physician has not edited by hand, including sections edited while the proposal was pending. The final step names the sections that will be replaced and those that stay manual before acceptance; afterwards the retained sections carry the "manuell bearbeitet, nicht aktualisiert" badge. The draft is never presented as fully updated when sections were skipped.
- Accepting adopts the proposal's clarification list for the encounter. A manual edit never resolves a clarification item by itself.
- When the notes change after the current draft was generated, one encounter-wide marker says the draft is possibly outdated. Lindra does not guess which sections are affected before a generation shows it.
- Section badges mean only: proposed change, manually edited, not updated, open clarification, copied. Never clinical verification.
- Each generated paragraph carries a tappable input reference that reveals the quoted notes passage, or for a visit the quoted passage of a background encounter, marked as such. Origin is not verification. A paragraph the physician rewrites loses its reference.
- Handover copies the current draft, never the pending proposal.

We chose whole-draft acceptance with edit preservation over per-section acceptance because one decision per generation keeps the physician's review cheap, while preserving manual edits is what makes the physician trust the tool with her wording. The step-per-section review with a large comparison replaced the single dense screen of round 1 because the operator found the comparison too small to read.

## Consequences

- An encounter needs a notes revision, a background revision (visits), an edited flag per section, and a proposal state with both revisions, so the API can refuse acceptance of an outdated proposal and report which sections it would skip.
- The browser flow covers: open a case from the empty start, pick an encounter, edit a section, generate, accept with the edited section retained and badged, change notes while a proposal is pending and see acceptance disabled, dictate from a review step with the overlay blocking, switch encounters through the portrait drawer, copy from the handover step.
