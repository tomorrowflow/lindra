---
status: accepted
date: 2026-11-08
revised: 2026-11-08 (grilling 2: evaluation-only hosted text-model comparison)
---

# Text generation and speech recognition run self-hosted; hosted inference exists only as an evaluation comparison on the fictional cast

Both the text model and the speech-to-text model run locally or on hardware the physician's side controls, behind swappable adapters. The product has no cloud path: no automatic fallback to a hosted service, and no cloud speech recognition at all. Lindra does not use the operating system's or browser's dictation feature, because it cannot assume that feature is local.

One exception, added in grilling 2: for the fictional-case evaluation only, a hosted text model (Ollama Cloud was named) may be configured as a comparison backend next to the self-hosted model, to find out whether local inference is good enough. This is called hosted inference, never local. It is launched separately and explicitly, sees only the fictional cast, is never the default of any environment, and authorises neither real patient data nor spending. Speech recognition stays self-hosted even in the comparison. The operator's statement that Ollama Cloud offers European inference is unverified; EU hosting would not make it local, and it is not recorded as fact until researched.

We chose the self-hosted default because the legal research (`docs/research/2026-11-04-legal-frame-patient-data-and-llms.md`) shows that sending identifiable health data to a cloud processor is lawful only with an Art. 28 processor contract with no-training terms, §203 StGB secrecy commitments, transfer grounds for US vendors and, for statutory-insurance providers, §393 SGB V with C5 attestation. None of that paperwork exists, and an accidental fallback would breach it silently. Self-hosting trades model quality and operational effort for a boundary that holds without paperwork; the fictional-case comparison measures what that trade costs without crossing the boundary, because the fictional cast is not personal data.

## Considered options

- Cloud model as the product backend with EU hosting and an AVV: rejected for now; EU hosting alone does not satisfy §393 SGB V or exclude third-country access. May be revisited only as a separate decision with the paperwork in hand.
- Browser or OS dictation: rejected; its locality is not verifiable.

## Consequences

- Which concrete models run, and whether the available hardware carries them with acceptable German medical-text quality, is unverified and must be evaluated in an implementation ticket, not assumed. The hosted comparison is part of that evaluation.
- The adapters have a deterministic stand-in each (fixture model, canned transcripts) so that every automated test and the test environment run without a real model. Tests with stand-ins prove the workflow, not medical fidelity or recognition quality.
- Real-model evaluation, self-hosted or hosted, is a separately and explicitly launched configuration that only ever sees the fictional cast. The hosted adapter refuses to start outside that configuration.
