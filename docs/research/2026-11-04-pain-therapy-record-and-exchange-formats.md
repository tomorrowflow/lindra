# Research: what a multimodal pain-therapy record must contain and how practice systems exchange it

Answered by Fróði on the SPEC-1 card, 4 November 2026, from web sources listed below.
Confidence: high on published requirements; medium on a particular practice or hospital system's usable interfaces (vendor, version and licence dependent).

## The record

Distinguish five things: intake assessment, dated treatment and progress entries, interdisciplinary conference decisions, longitudinal outcomes, and recipient-facing letters.

### OPS 8-918 (inpatient multimodal pain therapy)

- OPS 8-918 is an inpatient coding criterion, NOT a universal outpatient record law.
- It requires at least 7 days, at least 2 disciplines including psychological, psychiatric or psychosomatic expertise, specified eligibility, a treatment plan, interdisciplinary diagnostics, at least 3 active modalities, standardized outcome assessment, a daily medical round OR team discussion, and a weekly interdisciplinary conference.
- Evidence needs disciplines, dates, modalities, duration or units, group size and decisions. Subcodes add unit counts and individual conversations.
- Day-clinic care has separate 8-91c criteria.
- Explicit jointly agreed goals are supported by clinical and quality-assurance guidance; do not misquote them as a literal 8-918 requirement.

### Outpatient duty: KBV quality-assurance agreement on pain therapy, §7

- Requires a standardized initial questionnaire; disease type, severity, cause and comorbidities; pain duration and chronicity stage; psychosomatic and psychopathological effects and course; interventions; and standardized follow-up.
- Include biopsychosocial history, findings and diagnoses, medication with effect and adverse effects, functional limitations, goals and plan, and reassessment.

### Instruments

- The Deutscher Schmerzfragebogen (DSF) is patient-reported intake. KEDOQ-Schmerz combines it with clinical core documentation at baseline, course and follow-up for quality assurance and benchmarking; it does not replace encounter notes.
- The current DSF is version 12/2024 (released May 2025); the society says to retire older forms.
- NRS intensity (0 to 10) needs a timeframe and context; disability and emotional distress are separate outcomes.
- PDI and HADS are possible legacy or local instruments, NOT mandated OPS scales: the DSF 2020 manual already replaced PDI with three von Korff interference scales and HADS with DASS.
- Verify the current instrument version and usage rights before reproducing questionnaires. Retain instrument, date, raw responses and score rather than an interchangeable "pain score".

## Exchange boundary (evidence, not a release decision)

- GDT: common file-based exchange between practice systems and devices; versions 2.1, 3.1 and 3.5 coexist; not whole-record portability.
- BDT: legacy bulk practice-system migration; field and document fidelity varies.
- Hospital HL7 v2: live patient and encounter data (ADT), orders, results and documents via site-specific interfaces.
- FHIR: profiled REST APIs, notably gematik ISiK; not an automatically available universal endpoint.
- KIM is the secure telematics-infrastructure transport, not a clinical data model.
- The KBV eArztbrief requires a QES-signed PDF/A PLUS XML identification and header data, KIM, and the relevant confirmation or certification. A PDF export alone is neither an eArztbrief nor a KIM integration.
- PDF/A preserves a readable letter, not structured round-trip fidelity. File-only PDF or GDT feasibility still needs target-system samples and mapping.

## Sources

- OPS 2026, block 8-90 to 8-91: https://klassifikationen.bfarm.de/ops/kode-suche/htmlops2026/block-8-90...8-91.htm
- KBV QS-Vereinbarung Schmerztherapie: https://www.kbv.de/documents/infothek/rechtsquellen/bundesmantelvertrag/anlage-03-qualitaetssicherung/qs-vereinbarung-schmerztherapie.pdf
- DSF, current version: https://www.schmerzgesellschaft.de/schmerzfragebogen
- DSF manual 2020 (KEDOQ, scales): https://www.schmerzgesellschaft.de/fileadmin/pdf/DSF_Handbuch_2020.pdf
- BÄK Kursbuch Spezielle Schmerztherapie (educational guidance, not law): https://www.bundesaerztekammer.de/fileadmin/user_upload/BAEK/Themen/Aus-Fort-Weiterbildung/Weiterbildung/Kursbuecher/2018/20220217_18_MKB_Spezielle_Schmerztherapie.pdf
- GDT (QMS standards): https://www.qms-standards.de/
- BDT, vendor description: https://www.med7.de/fuer-umsteiger/bdt-schnittstelle/
- HL7 v2, vendor description: https://mesalvo.com/en/features/hl7-schnittstelle
- gematik ISiK: https://fachportal.gematik.de/zielgruppen/primaersystemhersteller/isik
- KBV eArztbrief requirements: https://update.kbv.de/ita-update/Abrechnung/eArztbrief/KBV_ITA_VGEX_Anforderungskatalog_eArztbrief.pdf
