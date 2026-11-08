# 08: Fidelity: the structured result contract, pain problems, provenance, references and the clarification list

**Track:** draft

**What to build:** The generation result is checked before it becomes a proposal, so that the draft contains only what the physician supplied. Pain problems stay separate with no fixed count and the main pain is named only when she named it; patient reports, prior findings and her own findings stay apart with their dates; treatments keep only the attributes she gave; every generated paragraph carries a tappable input reference that reveals the quoted notes passage and disappears when she rewrites the paragraph; paragraphs without support in the notes are dropped and their gap goes on the clarification list; the clarification list is adopted on acceptance and never resolved by a manual edit. The third fictional case proves that gaps are left as gaps.

**Blocked by:** 01 (Scaffold), 02 (Environments), 05, 06, 07 (Assessment review)

**Status:** ready-for-agent

**Spec:** PRD stories 20c, 23, 26 to 36; ADR 0001 (intended purpose), ADR 0008 (references and clarification semantics), ADR 0010 (Schmerzanamnese).

## Acceptance criteria

- [ ] The result check runs on every generation result: a paragraph whose input reference does not point into the encounter's notes (or, later, into a background encounter) is dropped and a clarification item names the section and the gap; a section the notes do not support stays empty with a clarification item; a result that fails structurally is a failed generation.
- [ ] Prompt and post-processing enforce ADR 0001: no inferred diagnoses, causes, justification, doses, conversions, interactions, normal findings or provenance; no ranking of pain problems; no silent resolution of contradictions; no completeness or approval claims. The fixture cast contains a case that tempts each of these and the tests assert the draft does not contain them.
- [ ] Within the Schmerzanamnese, each pain problem is a separate block with only the attributes supplied (site, radiation, onset and history, time course, intensity with its timeframe, quality, modifiers, coping, functional limitations, goals); the number of pains follows the notes; "Hauptschmerz" appears only when the physician named it.
- [ ] Provenance is kept: patient report, prior finding, physician finding, or unknown; dates and time windows are reproduced when supplied; unknown provenance stays unknown.
- [ ] Current and previous treatments are separate; substance, dose, duration, effect, adverse effects and discontinuation reason appear only when supplied.
- [ ] User-entered scores are reproduced with instrument, version and date when given; Lindra computes no score.
- [ ] Every generated paragraph shows a tappable "aus Notizen" reference that reveals the quoted passage; no confidence score or correctness claim anywhere; a hand-rewritten paragraph shows "von Hand, keine Herkunft".
- [ ] Contradictions in the notes become clarification items in the physician's language; the clarification list is per encounter, shown on the section steps for their items and in full on the final step; acceptance adopts the proposal's list; a manual edit never removes an item.
- [ ] The third fictional case (contradictory doses, unclear time references, missing inpatient justification) yields a draft with the corresponding gaps and clarification items; a test that passes by filling them fails.
- [ ] HTTP API tests cover the result check, references and their loss on rewrite, clarification adoption and persistence; pure logic tests cover the check and the reference validation.
- [ ] Unslop: the unslop skill and `references/signs.md` were read before work; the final diff was checked against the signs; the proof names the signs checked and any remaining finding with its reason.

## Proof

- Test, lint and CI green; the report names the tests for the result check, reference validation and loss on rewrite, clarification adoption and persistence, and the ADR 0001 negative cases (no inferred diagnosis, dose, normal finding, ranking or resolved contradiction in the fixture outputs).
- The third fictional case, generated on a throwaway stack after `reset`, yields the expected gaps and clarification items; the report quotes the clarification list.
- Screenshots of a tapped input reference with its quoted passage, a hand-rewritten paragraph without a reference, and the Schmerzanamnese step with two separate pain problems, on both viewports, committed under `docs/screenshots/`.
- Unslop proof: the signs checked and any remaining finding with its reason.
