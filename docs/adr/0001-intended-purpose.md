---
status: accepted
date: 2026-11-08
---

# Lindra's intended purpose is administrative: it words what the physician supplied

Lindra organises and words facts and assessments that the physician supplied in their notes or dictation into the physician-authored sections of the admission letter. The physician supplies every diagnosis, interpretation, causal assertion and the inpatient justification. Lindra must not invent or infer any of these, must not prioritise clinical problems, must not recommend treatment, must not infer, convert or assess doses or interactions, must not guess normal findings or provenance, must not resolve contradictions on its own, and must not certify medical completeness or claim physician approval.

We chose this line because, per the legal research (`docs/research/2026-11-04-legal-frame-patient-data-and-llms.md`), software without a medical intended purpose can stay outside the Medical Device Regulation, while clinical interpretation, prioritisation or recommendations would create one (MDCG 2019-11 rev. 1, Rule 11). Physician review is necessary but is not by itself an exemption, so every function is assessed against this purpose before it ships, and a function that crosses the line is a product change that needs a new decision, not an implementation detail.

## Consequences

- Missing or contradictory information goes on the clarification list; the affected section stays incomplete rather than filled in.
- Input references show where a paragraph came from and nothing more; no confidence scores, no correctness claims.
- Pain problems and treatments are kept separate and unranked; the main pain is whichever the physician named.
