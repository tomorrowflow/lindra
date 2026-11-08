# 09: Visit review with background: four sections, earlier accepted encounters, historical references and the changed-background marker

**Track:** draft

**What to build:** For a visit the physician generates a short progress draft with four sections from the visit's notes and its background: the accepted assessment and the accepted visits dated earlier, never later visits or pending proposals. Paragraphs drawn from the background carry a reference marked as coming from an earlier encounter. When an encounter in the background is accepted again after the visit's draft or proposal was generated, the draft shows "Hintergrund seit Erstellung geändert" and the proposal is refused with that reason; nothing regenerates on its own. A backdated visit sees only what preceded it. Contradictions between background and today's notes become clarification items.

**Blocked by:** 01 (Scaffold), 02 (Environments), 05, 06, 07, 08 (Fidelity and clarifications)

**Status:** ready-for-agent

**Spec:** PRD stories 8, 18a to 18c, 27a; ADR 0008 (per-encounter proposals), ADR 0010 (background rules).

## Acceptance criteria

- [ ] A visit's draft has exactly the sections Verlauf seit letzter Visite, Aktuelle Befunde, Ärztliche Einschätzung, Vereinbartes Vorgehen und Ziele; empty sections stay empty and appear on the clarification list; nothing is padded.
- [ ] Generation for a visit sends its own notes plus the background: the accepted draft of the assessment and the accepted drafts of visits with an earlier date; a pending proposal of any encounter and visits with a later date are never included; a backdated visit's background follows its own date.
- [ ] Each visit carries a background revision (the sum of the acceptance counters of its background encounters); the proposal stores the background revision it was generated from, the draft stores the one it was accepted at.
- [ ] Paragraphs that draw on background carry a reference "aus früherem Kontakt" that reveals the quoted passage and names the encounter and date; today's observations keep "aus Notizen"; the two are visually distinct.
- [ ] When the current background revision differs from the proposal's, the proposal is outdated: acceptance is disabled with the spelled-out reason ("Veraltet: Hintergrund seit diesem Vorschlag geändert"); when it differs from the draft's, the draft shows the "Hintergrund seit Erstellung geändert" badge and the text is preserved; the sidebar shows the background badge on the encounter; only explicit regeneration uses the new background.
- [ ] Treatment decisions and goals in a visit are worded only as supplied; the fixture cast includes a visit whose notes carry no decision, and the section stays empty with a clarification item.
- [ ] A contradiction between a background statement and today's notes is a clarification item naming both; it is never resolved silently.
- [ ] Acceptance, manual-edit preservation, handover and copy behave for visits exactly as for the assessment (ticket 07).
- [ ] Browser flow, second half, on both viewports: create a backdated visit inside the period and be refused outside it, generate the visit and see a historical reference, accept a change to the assessment and see the visit's background badge and the refused proposal, switch encounters through the portrait drawer, open an encounter without an accepted draft and see that nothing can be copied.
- [ ] HTTP API and pure logic tests cover background selection by date, background revision, refusal by background, backdated visits and contradiction items; tests use the fixture model only.
- [ ] Unslop: the unslop skill and `references/signs.md` were read before work; the final diff was checked against the signs; the proof names the signs checked and any remaining finding with its reason.
