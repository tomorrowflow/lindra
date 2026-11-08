# Research: prior art and existing solutions

Answered by Fróði on the SPEC-1 card, 4 November 2026, from a fresh web preflight with the sources listed below.
Confidence: high on product categories, on the directly retrieved Noa, Mediform, tomedo and medatixx terms, and on the offline architecture; medium on indexed prices and privacy claims; low on unverified German clinical performance.

Headline: ambient notes and letters are a crowded market; no ready-made German multimodal-pain team workflow was found. This supports investigating the proposed default (pain-therapy-specific workflow on a swappable model backend), it is not a product decision.

## Commercial tools (displayed prices; confirm quotes and terms)

- Nabla: ambient notes, dictation, coding. Pricing quote-only. German clinical availability and support need confirmation. GDPR DPA allows transfers subject to safeguards; not automatically EU-only.
- Heidi: German scribe, templates, derivative documents and evidence. Free tier confirmed; German premium and team prices require a quote or dynamic checkout. German compliance claim, not an independent approval.
- Doctolib: ambient consultation documentation; indexed official offer €59 incl. VAT per month on an annual subscription per practitioner; confirm bundle eligibility. Says EU storage and DSGVO.
- Noa Notes: ambient summaries and letters; €59, 79, 89 or 109 net per month by integration tier; setup €99 or 199; annual or monthly toggle, so confirm the term. Official page says Frankfurt hosting, DSGVO and ISO 27001.
- Tiro.health: now presents an AI outpatient EHR for dermatology, plastics and aesthetics, not just a generic scribe. Solo from €299, Practice €274 per clinician per month billed annually. Privacy says EU processing; German language and practice-system suitability unverified. Do not confuse with tirodocs.com.
- Mediform: primarily telephone and appointment automation, not an established ambient-letter comparator; €0.18 per minute incl. VAT plus €90 base; MediChat €82 per calendar per month. C5 claim.
- Practice-system vendors: CGM DokuAssistent integrates documentation (€49 per month is a secondary source only; request a quote). medatixx with Corti x.scribe generates notes and follow-up letters (price unverified); its separate free Copilot is software help, not scribing. tomedo.Intelligence includes a consultation assistant and letter tools and says normal usage should remain without additional charges (practice-system rental separate).

GDPR: these are vendor claims, NOT blanket German-law clearance. Verify the actual AVV, §203 confidentiality, subprocessors and transfers, deletion, no-training terms, patient recording consent and the controller's DPIA; for statutory-insurance cloud use verify the applicable §393 SGB V and C5 evidence. EU hosting alone is insufficient.

## Offline building blocks

- Speech-to-text: Whisper large-v3 or turbo via whisper.cpp (MIT; CPU, Apple and GPU, quantization) or faster-whisper (MIT, CTranslate2, GPU and CPU). German fine-tunes exist but no demonstrated superiority for pain terminology was found. Test negation, doses and speakers.
- Local LLMs: Qwen3 open weights (Apache-2.0 variants) offer multilingual German local inference; medical German accuracy must be tested. MedGemma is a medical open-weight model under Gemma terms, NOT OSI open source; its published evaluation is primarily English, so it gives no German clinical assurance.
- Records: HAPI FHIR (Apache-2.0) supplies a self-hosted FHIR repository and API, not a complete EHR. OpenEMR (GPLv3+) is a self-hosted EHR with FHIR support, not automatically German practice-system, KBV or telematics compliant.

## Sources

- https://www.nabla.com/security-documents/data-protection-agreement
- https://www.heidihealth.com/de-de/preise
- https://www.heidihealth.com/de-de/compliance/compliance-deutschland
- https://info.doctolib.de/ki-sprechstundenassistent/
- https://noa.ai/de/preise
- https://tiro.health/pricing
- https://tiro.health/privacy
- https://mediform.io/pricing
- https://www.cgm.com/deu_de/loesungen/praxissoftware/zusatzprodukte/cgm-one-dokuassistent.html
- https://comparescribes.com/scribes/cgm-one
- https://medatixx.de/ki-in-der-praxis
- https://support.tomedo.de/handbuch/tomedo/tomedo-intelligence/
- https://github.com/ggml-org/whisper.cpp
- https://github.com/SYSTRAN/faster-whisper
- https://huggingface.co/Qwen/Qwen3-8B
- https://huggingface.co/google/medgemma-4b-it
- https://hapifhir.io/
- https://www.open-emr.org/
