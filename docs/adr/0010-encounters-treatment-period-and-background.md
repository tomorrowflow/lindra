---
status: accepted
date: 2026-11-08
---

# A case is a treatment period with one admission assessment and dated visits; a visit draws only on earlier accepted encounters

Settled in grill 4. This widens release one beyond the admission assessment (the PRD's earlier exclusion of ongoing progress documentation is withdrawn) but adds no discharge summary, no scheduling, no recommendations and no full record.

## Cases and the treatment period

- Creating a case collects the case number (primary identifier), a required patient name (grill 5; shown as subtitle in the sidebar and in the case header), the date and time of the admission assessment, an optional short label, and the treatment period as inclusive Behandlungsbeginn and Behandlungsende dates. No birth date, address or other identifying data is collected, and no patient-management workflow exists. In the evaluation release the case number and the patient name are fictional (ADR 0006); hospital-issued case numbers are a later integration concern (ADR 0002).
- Every encounter's date must lie in the treatment period; the visit date picker is constrained to it and the time is free within the chosen day. A new visit defaults to now when now lies in the period and to nothing otherwise; backdating within the period is allowed.
- The period can be corrected later. A change that would leave an existing encounter outside the period is refused and the conflicting encounters are named. Encounters are never deleted or moved by a period change.

## Encounters

- Each case has exactly one admission assessment and any number of visits. Each encounter has its own date and time, its own notes, its own draft, its own proposal state and its own clarification list. Notes of one encounter are never appended to another, and an earlier encounter is never rewritten by a later one.
- The admission assessment's sections follow the clinical headings and order of the ward's assessment form, grouped into seven review steps: Sozialanamnese; Frühere Anamnese und Vormedikation; Therapeutische Anamnese (current and previous medication, current and previous non-drug treatments); Schmerzanamnese (the main pain only when the physician named it, every further pain problem kept separate, no fixed number of pains, no ranking); Internistische, vegetative, psychiatrische und Suchtmittelanamnese; Untersuchungsbefunde (physical and internal examination, further diagnostics, psychopathological, orthopaedic and neurological findings); Behandlungsplan und vereinbarte Ziele (only as supplied). The form is a structural reference, not a template to reproduce; its checkboxes are not digitised, and the form itself is not published.
- A visit's sections are Verlauf seit letzter Visite; Aktuelle Befunde; Ärztliche Einschätzung; Vereinbartes Vorgehen und Ziele. Empty headings stay empty and go on the clarification list; nothing is invented to fill them.

## Background of a visit

- Generating a visit's draft uses, besides the visit's own notes, only its background: the accepted draft of the admission assessment and the accepted drafts of visits dated earlier than this one. Later visits and pending proposals are never background, so a backdated visit sees only what preceded it.
- Paragraphs that draw on background carry an input reference to that encounter, marked as historical, so today's observations and earlier information stay distinguishable. Contradictions between background and today's notes are never resolved silently; they go on the clarification list.
- Every encounter carries a background revision: the count of acceptances in its background. When an encounter in the background is accepted again after a visit's draft or proposal was generated, that draft is marked "Hintergrund seit Erstellung geändert" and that proposal becomes outdated and unacceptable (ADR 0008). The text is preserved; nothing is regenerated or rewritten automatically; an explicit regeneration uses the current background.
- Lindra organises the treatment decisions and goals the physician supplied; it never recommends or infers a clinical decision (ADR 0001).

## Consequences

- The data model needs per-encounter notes revisions, acceptance counters and the derived background revision; the API refuses acceptance of a proposal whose notes or background revision is stale and refuses period changes that strand an encounter.
- The fictional cast grows: each case gets a treatment period, an admission assessment and at least one visit, one of them backdated, and one case has a background change after a visit draft.
