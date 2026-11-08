# Lindra first release: admission letter sections from the physician's notes or dictation

Terms are as defined in `CONTEXT.md`. Decisions referenced as ADR NNNN live in `docs/adr/`. Research behind them lives in `docs/research/`.

## Problem Statement

Ella is the physician in an inpatient multimodal pain-therapy team. After she has assessed a newly admitted patient she has to turn everything she learned, the patient's reports, prior findings, her own findings, the pain problems, the current and previous treatments, the functional and psychosocial impact and her reasoning for inpatient treatment, into the physician-authored sections of the admission letter in the hospital system. Today she does this by hand against a template: she sorts her notes, writes every section out, and checks nothing was lost. It is the single biggest block of organising work in her day, it competes with time for patients, and the sorting is clerical while the content is hers.

The tools on the market record consultations ambiently and write generic notes. She does not want her patient conversations recorded, her hospital system stays the record, and nothing exists for the structure of a pain-therapy admission letter.

## Solution

Lindra is a German web application on her iPad and desktop. She opens a case under a fictional case identifier and puts her notes in, either by typing or pasting free text, or by dictating her own notes after the assessment and correcting the transcript. When she asks for it, Lindra proposes a draft of the letter sections next to her notes, in the hospital's section structure, written only from what she supplied. Every paragraph shows which part of the notes it came from. Whatever the notes did not say, or said twice in contradiction, lands on a clarification list instead of in the draft. She edits the draft, copies each section as plain text into the hospital system, and is done.

Lindra never invents diagnoses, interpretations, causes or justifications, never ranks pain problems, never recommends treatment and never assesses doses (ADR 0001). It runs on self-hosted models with no cloud path in the product (ADR 0003); a hosted text model may be compared against the self-hosted one in the fictional-case evaluation only. The first release is evaluated only on three fictional cases (ADR 0006); its target is at least 30 percent less total preparation time, including review and correction, with no fabricated clinical statement and no lost relevant fact.

## User Stories

Cases and notes

1. As the physician, I want to create a case under a fictional case identifier, so that I can work on one admission without entering any patient-identifying data.
2. As the physician, I want to see a small list of my saved cases, so that I can reopen one I have not finished.
3. As the physician, I want to reopen a case and find my notes, my draft and the clarification list exactly as I left them, so that interrupted work is not lost.
4. As the physician, I want to delete a case, so that nothing lingers once the letter is in the hospital system.
5. As the physician, I want to type or paste free-form notes in any order without a mandatory question-by-question wizard, so that I can work the way my assessment went.
6. As the physician, I want my notes autosaved while I type, so that I never lose them to a closed tab or a dead battery.
7. As the physician, I want a clear indication when my changes are not saved because the network is gone, so that I know what to retype rather than assuming it was kept.
8. As the physician, I want the notes area and the draft side by side, so that I can compare and correct without switching screens.
9. As the physician, I want the application in German on both my iPad and my desktop browser, so that it fits where I actually write.

Dictation

10. As the physician, I want to explicitly start and stop a dictation of my own notes after the assessment, so that nothing is recorded that I did not mean to record.
11. As the physician, I want to always see whether Lindra is idle, recording, transcribing or waiting for my review, so that I never speak into a dead microphone or leave one open.
12. As the physician, I want the transcript shown for review and correction before it joins my notes, so that recognition errors never reach a draft.
13. As the physician, I want an incoming transcript appended to my notes rather than replacing text I typed, so that dictating and typing can be mixed.
14. As the physician, I want the audio discarded once the transcript exists, so that no audio archive of my dictations accumulates.
15. As the physician, I want dictation to work from my iPad's microphone in the browser, so that I can dictate where I assessed the patient.
16. As the physician, I want speech recognition to run self-hosted, so that my dictation never leaves our own hardware.

Generation and the draft

17. As the physician, I want a draft generated only when I explicitly ask for it, so that nothing changes under my hands.
18. As the physician, I want the draft organised in the hospital's sections, admission reason, pain history, relevant history and findings, previous therapy attempts, functional and psychosocial impact, inpatient justification and, when I supplied them, therapy goals, so that it maps onto the letter in the hospital system.
19. As the physician, I want a new draft offered as a proposal I accept or discard, so that it never silently replaces edits I made to the previous draft.
20. As the physician, I want to edit the draft freely, so that the final wording is mine.
21. As the physician, I want the draft marked as potentially stale when I change the notes after generating it, so that I know when to regenerate.
22. As the physician, I want my notes and my last draft preserved when a generation fails, so that a model error costs me nothing.
23. As the physician, I want each paragraph of the draft to show the passage of my notes it came from, without a confidence score or any claim that it is correct, so that I can check origin quickly and still judge content myself.
24. As the physician, I want to copy a single section as plain text with one action, so that pasting into the hospital system is fast and keeps the hospital's formatting.
25. As the physician, I want the text model to run self-hosted with no cloud fallback, so that patient information never leaves our own hardware.
25a. As the operator, I want to compare the self-hosted text model against a hosted one on the fictional cast only, in a configuration I launch explicitly, so that I learn whether local inference is good enough without any real data or default cloud path.

Clinical fidelity

26. As the physician, I want every pain problem kept separate with its site, radiation, course, intensity, modifiers and limitations, so that the letter does not blur two pains into one.
27. As the physician, I want the main pain to be the one I named and none otherwise, so that Lindra never ranks problems for me.
28. As the physician, I want the patient's reports, prior findings and my own findings kept apart in the draft, with dates and time windows preserved when I gave them, so that provenance in the letter stays true.
29. As the physician, I want a statement whose provenance I did not give to stay without a source rather than get an invented one, so that the draft never claims more than I said.
30. As the physician, I want current and previous treatments kept separate, each with the substance, dose, duration, effect, adverse effects and reason for stopping that I supplied, so that the therapy history is complete and mine.
31. As the physician, I want no dose inferred, converted or interpreted and no interaction or recommendation added, so that the draft never contains a clinical judgement I did not make.
32. As the physician, I want the inpatient justification worded only from what I supplied, and left on the clarification list when I supplied nothing, so that the letter never argues for admission in my name.
33. As the physician, I want missing or contradictory information collected on a clarification list while every supported section is still drafted, so that one gap does not block the rest.
34. As the physician, I want no guessed normal findings, no fabricated diagnoses and no silently resolved contradictions, so that I can trust that everything in the draft came from me.
35. As the physician, I want no claim of medical completeness or physician approval anywhere in the draft, so that the responsibility stays visibly mine.
36. As the physician, I want scores I entered, such as a questionnaire result, reproduced with instrument, version and date when I gave them, so that the letter is precise without Lindra scoring anything itself.

Evaluation and operation

37. As the physician, I want three fictional German cases ready in Lindra, so that I can judge it without touching a real patient.
38. As the physician, I want to compare my preparation time with Lindra, including review and correction and including transcript correction when dictating, against my template workflow, so that the release is judged on time saved and facts kept.
39. As the operator, I want a throwaway stack per ticket, a long-lived test environment on `origin/main` and an operator-run production, so that nothing a ticket does can touch production and nothing in test is real.
40. As the operator, I want the test environment and every automated test to run on deterministic stand-ins for the text model and speech recognition, so that tests prove the workflow without a GPU and without a real model.
41. As the operator, I want a separately and explicitly launched real-backend configuration, self-hosted or the hosted comparison, that only ever sees the fictional cast, so that model quality can be evaluated without that becoming the default.
42. As the operator, I want the application reachable only on the private network with a single protected login, so that no registration or role system is needed for one author.

## Implementation Decisions

Shape

- One Python web service with a SQLite database and a server-driven, responsive German browser UI for iPad and desktop (ADR 0005). No native app, no offline synchronisation.
- Access is the private network (Tailscale) plus one protected application login; a single token or password, no registration, no roles.
- The hospital system is the record; Lindra hands over plain-text sections by copy and has no integration, export or sending (ADR 0002).

Domain model

- A case holds a fictional case identifier, the notes, the current draft, the accepted-or-discarded state of the latest proposal, the clarification list, the staleness flag and timestamps. Cases list, open and delete; nothing else.
- Notes are one editable text body per case. A transcript is appended to the notes as a marked passage once the physician accepts it; it never replaces existing text.
- A draft has exactly the fixed sections: admission reason, pain history, relevant history and findings, previous therapy attempts, functional and psychosocial impact, inpatient justification, therapy goals (present only when supplied). Each section holds paragraphs; each paragraph carries an input reference (a span of the notes) or none.
- The clarification list is a list of items, each naming the section it affects and the missing or contradictory information, in the physician's language.
- Structured content the draft must respect: pain problems (site, radiation, course, intensity, modifiers, limitations, main pain only when named), provenance (patient report, prior finding, physician finding, unknown), dates and time windows when supplied, treatments (current or previous; substance, dose, duration, effect, adverse effects, discontinuation reason, each only when supplied), user-entered scores with instrument, version and date when known.

Generation contract

- Generation runs only on the physician's explicit action. The service sends the notes to the text model adapter and receives a structured result: sections with paragraphs and input references, and the clarification list. Prose with no structure is rejected as a failed generation.
- A generation result is stored as a proposal next to the current draft. The physician accepts it (it becomes the draft) or discards it (the current draft stays). Manual edits to the draft are never overwritten.
- When the notes change after the current draft was generated, the draft is flagged stale until the next accepted proposal.
- A failed generation leaves notes and current draft untouched and tells the physician it failed and why, in plain words.
- The prompt and post-processing enforce the intended purpose (ADR 0001): no inference of diagnoses, causes, justification, doses, interactions, normal findings or provenance; no ranking of pain problems; no resolution of contradictions; no completeness or approval claims. The structured result is checked for input references that do not point into the notes and for sections the notes did not support; such paragraphs are dropped and the gap goes on the clarification list.

Adapters

- A text model adapter with three implementations: the fixture model (deterministic, keyed to the fictional cast, used by all tests and by the test tier), a self-hosted model adapter speaking to a local inference server on the same host or network, and a hosted-inference adapter (Ollama Cloud was named) that is usable only in the explicitly launched evaluation configuration and refuses to start anywhere else (ADR 0003). The product configuration has no cloud option and no fallback. Whether the named provider runs inference in Europe is unverified and, even if true, does not make it local.
- A speech-to-text adapter with two implementations: canned transcripts keyed to fixture audio, and a self-hosted recogniser (candidates from research: whisper.cpp, faster-whisper) chosen after evaluation on the available hardware with German medical text. Audio is held in memory or a temporary file only for the duration of transcription.
- The browser captures audio with explicit start and stop, shows the dictation state, uploads the audio for transcription and shows the transcript for review before the physician accepts it into the notes. Browser microphone capture requires a secure origin (HTTPS), which the private-network setup must provide.
- Which concrete models fit the hardware and reach acceptable German quality is unverified and is settled inside an implementation ticket with a recorded result, not assumed by this spec.

Seams for tests

- Primary seam: the application's HTTP API with the fixture model and canned transcripts. Every workflow test goes through it: cases, notes autosave, dictation and transcript review, generation, proposals, staleness, failure preservation, input references, clarification list, section copy text.
- Pure logic tests where the behaviour is a function: the result check (dropping unsupported paragraphs and unreferenced spans), staleness, transcript append, section plain-text rendering.
- One small browser flow (iPad-sized and desktop viewport) covering notes input, generation, editing and copying a section, plus dictation start, stop, review and accept with a canned transcript.

Environments (ADR 0007)

- Throwaway stack per ticket in rootless Docker on its node; long-lived test on Linux 790 as user and node `lindra-test`, port 8780, compose project `lindra-test`, running only `origin/main`, refreshed every 5 minutes by a user timer; production run by the operator as `frogger`.
- One compose file and one `scripts/env.py` with `up`, `check`, `reset`, `down`, `ensure-test`, `install-timer`. `reset` seeds the fictional cast only. Nodes read `LINDRA_TEST_URL` and `LINDRA_TEST_TOKEN`.
- The test tier always runs the stand-ins. A real-backend evaluation configuration, self-hosted or the hosted comparison, is launched separately and explicitly; the hosted provider's account and key stay with the operator, who approved the comparison but no spending.
- The production host for real clinical use is an open decision pending the legal and organisational check; installing production does not authorise real data (ADR 0006).

## Testing Decisions

- A good test drives the HTTP API or the browser like the physician would and asserts only what she would observe: what is saved, what the draft contains, what the clarification list says, what the copied text is, what the dictation state shows. Tests do not assert on prompts, database rows or adapter internals.
- Every automated test uses the fixture model and canned transcripts. These prove the workflow and the fidelity rules Lindra enforces itself (dropping unsupported paragraphs, staleness, no overwrite). They do not prove medical fidelity of a real model or real recognition quality; nobody may cite them as such.
- The fictional cast is the test data everywhere: the three cases from ADR 0006, each with notes, expected fixture draft, expected clarification items and, for dictation, fixture audio with a canned transcript. The third case expects gaps, so a test that passes by filling them is wrong.
- Modules under test: cases and notes, dictation and transcript review, generation and proposals, the result check, section copy text, the environment script's `check` and `reset`.
- Prior art: none in this repository; the scaffold ticket establishes the test runner and the first API test, which every later ticket follows.

Operator-run checks (no factory node can run them; each names when)

- **Operator-run, before merge of the dictation ticket:** on Ella's physical iPad in the browser over the private network, start a dictation, see the recording state, stop, see the transcript, correct it and accept it into the notes. Confirms microphone capture, secure origin and the status display on the real device.
- **Operator-run, before merge of the real-backend ticket:** on the chosen inference hardware, run the self-hosted model and recogniser against the fictional cast, and the hosted comparison with the operator's own account, and record the measured German quality and latency in the repository; a result that cannot carry the workflow is reported as such, not hidden.
- **Operator-run, at the end of the release:** Ella prepares the three fictional cases with her template workflow and with Lindra, typed and dictated, measuring total time including review, correction and transcript correction, and judges fabricated statements, lost facts and usability. The result is recorded in the repository; a missed target creates follow-ups and is not weakened.
- **Operator-run, at install of test:** the operator checks Linux 790 for suitability (no production service, rootless Docker, port 8780 free) before the test environment goes there.
- **Operator-run, at install of production:** the operator deploys to the host they name following the runbook and confirms `env.py check` passes; this confirms the evaluation configuration only.

## Out of Scope

- Team accounts, roles, collaborative editing; other disciplines as authors.
- Schedules, planning, daily visit documentation, ongoing progress records.
- Final discharge synthesis or epicrisis; treatment-plan generation; any clinical recommendation.
- A research assistant; a full electronic record.
- Hospital system integration of any kind: FHIR, eArztbrief, KIM, HL7, GDT; PDF or Word export; sending letters.
- PDF upload or OCR of forms, a patient portal, complete questionnaire capture, automatic scoring or psychological interpretation.
- Ambient recording or any recording of patient conversations; operating-system or browser dictation.
- Cloud text models in the product, including as a fallback; cloud speech recognition in any form. The only hosted inference is the fictional-case evaluation comparison (ADR 0003).
- Native Apple app; offline synchronisation.
- Use with real patient data; this is an evaluation release (ADR 0006).

## Further Notes

- Speech input was added to the first release by the operator's last amendment in the grilling and is binding: voice and text are equal inputs in every ticket, test and acceptance check.
- The admission form and the German pain questionnaire (DSF 12/2024 with an additional PDI sheet) that Ella supplied are a structural reference only. Do not assume the PDI is absent from the local workflow; do not reproduce the forms; do not publish them or the transcript in the repository. The admission PDF's text layer is damaged and the spoken template was mistranscribed, so neither is a template.
- Open technical prerequisites, each resolved inside its ticket with a recorded result: model and recogniser choice and hardware suitability; where the hosted comparison provider actually runs inference and under which terms (unverified, to be researched before it is recorded as fact); iPad browser audio capture and formats; suitability of Linux 790 as the test host; the production host pending the legal check.
- Apple-platform work does not exist in this release; should a later decision change the platform, its tickets are routed to the Mac node first.
