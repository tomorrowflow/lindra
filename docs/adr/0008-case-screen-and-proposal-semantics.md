---
status: accepted
date: 2026-11-08
---

# The case screen is two columns with one whole-draft proposal that never overwrites manual edits

Settled in grilling 3 on the prototype `docs/prototypes/SPEC-1/case-screen.html` (variant A chosen, with the section badges of variant C). The case screen shows the notes and the draft as one continuous letter side by side on wide screens, and as Notizen/Entwurf tabs on a portrait iPad. The dictation bar and the transcript review sit under the notes. The draft is freely editable by hand.

## Proposal semantics

- A generation produces one proposal for the whole draft. It is accepted or discarded with one action; there are no per-section accept controls.
- A proposal is bound to the notes revision it was generated from. When the notes change afterwards, by typing, by an accepted transcript, or while a generation is in flight, the proposal stays visible, cannot be accepted, and is labelled "Notizen seit diesem Vorschlag geändert". The physician discards it and regenerates explicitly. Lindra never regenerates on its own and an outdated proposal never clears the stale marking.
- Accepting replaces only sections the physician has not edited by hand, including sections edited while the proposal was pending. Before acceptance the screen names the sections that will be skipped. After acceptance the retained sections carry the label "manuell bearbeitet, nicht aktualisiert" and the proposal's alternative for them stays visible until the proposal is finally accepted or discarded. The draft is never presented as fully updated when sections were skipped.
- Accepting adopts the proposal's clarification list for the whole case. A manual edit never resolves a clarification item by itself.
- When the notes change after the current draft was generated, one document-wide banner says the draft is possibly outdated. Lindra does not guess which sections are affected before a generation shows it.
- Section badges say only: proposed change, manually edited, open clarification. They never express clinical verification.
- Each generated paragraph carries a tappable input reference that reveals the quoted notes passage. Origin is not verification. A paragraph the physician rewrites loses its reference rather than keeping one that no longer supports the wording.

We chose whole-draft acceptance with edit preservation over per-section acceptance because one decision per generation keeps the physician's review cheap, while preserving manual edits is what makes the physician trust the tool with her wording. The prototype's first reducer replaced edited sections on acceptance; that behaviour was rejected in grilling 3 and is not normative.

## Consequences

- The case needs a notes revision marker, an edited flag per section, and a proposal state with its notes revision, so the API can refuse acceptance of an outdated proposal and report which sections it would skip.
- The browser flow test covers: edit a section, generate, accept, see the section retained and labelled; change notes while a proposal is pending, see acceptance disabled.
