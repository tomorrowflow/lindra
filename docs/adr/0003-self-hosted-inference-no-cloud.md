---
status: accepted
date: 2026-11-08
---

# Text generation and speech recognition run self-hosted; there is no cloud path

Both the text model and the speech-to-text model run locally or on hardware the physician's side controls, behind swappable adapters. There is no cloud model, no cloud speech recognition and no automatic fallback to either. Lindra does not use the operating system's or browser's dictation feature, because it cannot assume that feature is local.

We chose this because the legal research (`docs/research/2026-11-04-legal-frame-patient-data-and-llms.md`) shows that sending identifiable health data to a cloud processor is lawful only with an Art. 28 processor contract with no-training terms, §203 StGB secrecy commitments, transfer grounds for US vendors and, for statutory-insurance providers, §393 SGB V with C5 attestation. None of that paperwork exists, and an accidental fallback would breach it silently. Self-hosting trades model quality and operational effort for a boundary that holds without paperwork.

## Considered options

- Cloud model with EU hosting and an AVV: rejected for now; EU hosting alone does not satisfy §393 SGB V or exclude third-country access. May be revisited only as a separate decision with the paperwork in hand.
- Browser or OS dictation: rejected; its locality is not verifiable.

## Consequences

- Which concrete models run, and whether the available hardware carries them with acceptable German medical-text quality, is unverified and must be evaluated in an implementation ticket, not assumed.
- The adapters have a deterministic stand-in each (fixture model, canned transcripts) so that every automated test and the test environment run without a real model. Tests with stand-ins prove the workflow, not medical fidelity or recognition quality.
- Real-model evaluation is a separately and explicitly launched configuration that only ever sees the fictional cast.
