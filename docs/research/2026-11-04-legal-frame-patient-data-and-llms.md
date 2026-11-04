# Research: legal frame for patient data and LLMs in a German pain practice

Answered by Fróði on the SPEC-1 card, 4 November 2026, from web sources listed below.
Confidence: high on the legal framework; medium on Lindra's MDR status until the intended purpose and workflows are defined.

Headline: cloud is not categorically forbidden; neither a processor contract (AVV) nor pseudonymisation alone makes it lawful.

## GDPR

- Identifiable health data require BOTH an Art. 6 ground (typically the treatment contract or the legal documentation duty) AND an Art. 9 exception. Necessary treatment and documentation normally fall under Art. 9(2)(h) with Art. 9(3), under professional secrecy; §22 BDSG also applies.
- Explicit consent (Art. 9(2)(a)) is an alternative, not a blanket requirement for treatment AI.
- Apply data minimisation, transparency, security and retention rules, and assess an Art. 35 data protection impact assessment (DPIA).
- Pseudonymised clinical narratives remain personal data if re-identification is possible.

## Cloud LLM and speech-to-text services

- The practice remains the controller. EU and US processors alike need an Art. 28 AVV covering instructions, confidentiality, subprocessors, security, deletion and audit; vendor training and own-purpose reuse must be excluded.
- Check the actual API and product terms, logs, support access and data locations, not just the vendor's headquarters.
- US transfers additionally need Chapter V grounds: a valid Data Privacy Framework (DPF) certification covering the recipient and processing, or SCCs plus a transfer assessment and supplementary measures. EU hosting does not by itself exclude third-country access.

## §393 SGB V (cloud use by covered healthcare providers and their processors)

- Requires permitted processing countries, a German establishment of the processing entity, security measures, a C5 attestation and implementation of the customer controls. Normally C5 Type 2 since July 2025; statutory transition rules for new systems and equivalent-standard exceptions exist.
- SCCs alone do NOT override the country restriction of §393.
- This applies to cloud production hosting as well as to model and speech-to-text services.

## §203 StGB and §201 StGB

- Patient secrecy under §203 StGB is separate from GDPR. Abs. 3 permits necessary disclosure to outside participating service providers; Abs. 4 requires binding secrecy commitments, including from downstream providers. An AVV must address this separately; it is not automatic permission to disclose unrestricted records.
- Recording consultations raises §201 StGB: obtain the participants' permission for the recording. Distinguish this from the GDPR treatment ground.

## Medical Device Regulation (MDR)

- Purely administrative transcription, formatting, document storage and letters without a medical intended purpose can be outside MDR.
- "No diagnosis, no dosing" is not a sufficient exclusion: clinical interpretation, prioritisation or recommendations may create a medical purpose.
- MDCG 2019-11 rev. 1 (June 2025): assess intended purpose and functions first; only then does Rule 11 classify medical device software, usually class IIa for software providing diagnostic or therapeutic decision information, higher by potential harm. Physician review alone does not exempt it.

## EU AI Act

- An ordinary administrative assistant is not automatically high-risk; MDR software needing third-party conformity assessment triggers Art. 6(1).
- Art. 50 transparency applies where relevant, especially for direct patient chatbot interaction.
- Current Commission timeline reflects the 2026 AI Omnibus: Annex I high-risk obligations start 2 August 2028 (not the old 2027 date); the literacy provisions were simplified.
- KBV's 2025 guide supports assistance, not replacement of medical responsibility; it asks for patient information, an AVV, competence and a compliant cloud. Its old AI timeline must be read against the current amendments.

## Sources

- GDPR Art. 9: https://gdpr-info.eu/art-9-gdpr/
- GDPR Art. 28: https://gdpr-info.eu/art-28-gdpr/
- §203 StGB: https://www.gesetze-im-internet.de/stgb/__203.html
- §201 StGB: https://www.gesetze-im-internet.de/stgb/__201.html
- §393 SGB V: https://www.gesetze-im-internet.de/sgb_5/__393.html
- EDPB DPF FAQ for businesses (April 2026): https://www.edpb.europa.eu/system/files/2026-04/edpb_dpf_faq-for-businesses_v2_en.pdf
- MDCG 2019-11: https://health.ec.europa.eu/document/download/b45335c5-1679-4c71-a91c-fc7a4d37f12b_en?filename=mdcg_2019_11_en.pdf
- AI Omnibus enters into force: https://digital-strategy.ec.europa.eu/en/news/ai-omnibus-enters-force
- KBV Praxiswissen KI: https://www.kbv.de/documents/infothek/publikationen/praxiswissen/praxiswissen-ki.pdf
