---
status: accepted
date: 2026-11-08
---

# The hospital system stays the record; Lindra hands over plain text by copy

The hospital system remains the authoritative patient record and hosts the other disciplines' contributions. Lindra prepares the physician's letter sections and the physician copies each section as plain text into the hospital system. Lindra has no integration with it: no FHIR, no eArztbrief, no KIM, no PDF or Word export, no sending.

We chose copy-out because the exchange research (`docs/research/2026-11-04-pain-therapy-record-and-exchange-formats.md`) shows every structured path is heavy and site-specific (eArztbrief needs a QES-signed PDF/A plus XML plus KIM, FHIR via ISiK is not universally available), while the physician's actual burden is organising the text, not transporting it. Keeping Lindra outside the record also keeps it a working aid rather than a second record, which matters for the intended purpose (ADR 0001) and for data protection.

## Consequences

- A case in Lindra is a working copy identified by a case number with the patient name as its subtitle (ADR 0010, grill 5); no birth date or other demographics are held. In the evaluation release both are fictional (ADR 0006). Taking over hospital-issued case numbers is a later integration concern, not release one.
- Letter formatting beyond plain text is the hospital system's job.
