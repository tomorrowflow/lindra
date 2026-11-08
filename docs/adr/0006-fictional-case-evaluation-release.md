---
status: accepted
date: 2026-11-08
---

# The first release is an evaluation release on a fictional cast only

The first release is used only with three entirely fictional German cases, even where it would technically work with real data. Any use with real patient data needs a separate operator, hosting and legal approval; local processing, Tailscale and private hardware do not by themselves establish that authorisation. The repository is public and never contains real, transformed or pseudonymised patient material, nor the institutional documents supplied during the grilling.

We chose this because the legal frame (`docs/research/2026-11-04-legal-frame-patient-data-and-llms.md`) ties lawful processing to a data protection impact assessment, secrecy commitments and, for a hospital, its own organisational approval, none of which the project can grant itself. Separating "technically complete" from "demonstrated useful" lets the first release be judged on its own target: at least 30 percent less total preparation time, including review and correction, with no fabricated clinical statements and no lost relevant facts, for both typed and dictated input. A missed target is reported as missed and followed up; it is never weakened after the fact.

## Consequences

- Every case number and patient name in the cast is invented; real names appear only after the separate approval, never in the repository.
- The fictional cast covers: a simple single pain problem with clear prior therapy and supplied justification; multiple pain problems, therapies and impacts; and a case with contradictory doses, unclear time references and a missing inpatient justification, where leaving gaps is the correct result.
- The evaluation itself (the physician's timing and judgement) is operator-run and recorded in the repository as a result, not assumed.
