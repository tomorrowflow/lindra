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
9a. As the physician, I want a calm light screen with readable text, large touch targets, visible keyboard focus and states that do not rely on colour alone, so that I can work on it for hours and on an iPad with my finger.
9b. As the physician, I want the notes and the letter side by side on a wide screen and as two tabs on a portrait iPad, so that I can compare and correct wherever I am.

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
19. As the physician, I want a new draft offered as one proposal for the whole letter that I accept or discard with one action, so that reviewing a generation costs me one decision, not seven.
20. As the physician, I want to edit the draft freely, so that the final wording is mine.
20a. As the physician, I want sections I edited by hand to survive accepting a proposal, including edits I made while the proposal was pending, with the skipped sections named before I accept and labelled "manuell bearbeitet, nicht aktualisiert" afterwards, so that my wording is never overwritten and I never believe the whole draft is fresh when it is not.
20b. As the physician, I want the proposal's alternative for a skipped section to stay visible until I finally accept or discard the proposal, so that I can take it over by hand if I want it.
20c. As the physician, I want accepting a proposal to adopt its clarification list for the whole case, and my manual edits never to tick off a clarification item by themselves, so that open questions stay open until I resolve them.
21. As the physician, I want one banner on the whole draft saying it is possibly outdated when I change the notes after generating it, without Lindra guessing which sections are affected, so that I know when to regenerate and am not misled by guesses.
21a. As the physician, I want a proposal that was generated from older notes, because I typed, accepted a transcript or changed notes while it was being generated, to stay visible but be unacceptable and labelled "Notizen seit diesem Vorschlag geändert", so that I discard it and regenerate deliberately instead of accepting text that no longer matches my notes.
21b. As the physician, I want badges on section headings that say only "proposed change", "manually edited" or "open clarification", so that I see what needs my attention without any badge pretending to verify content.
22. As the physician, I want my notes and my last draft preserved when a generation fails, so that a model error costs me nothing.
23. As the physician, I want each generated paragraph to carry a tappable input reference that reveals the passage of my notes it came from, without a confidence score or any claim that it is correct, and to lose that reference when I rewrite the paragraph, so that origin is visible and never mistaken for verification.
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
- The case screen is the prototype's variant A (ADR 0008): notes and the letter as one continuous document side by side on wide screens, Notizen/Entwurf tabs on a portrait iPad, the dictation bar and transcript review under the notes, section badges on the headings, a copy action per section, free manual editing of the draft.
- UI foundation (ADR 0009): a single light theme, Quiet Clarity (warm off-white, opaque writing surfaces, forest-teal actions, restrained local SVG icons), on daisyUI 5 component CSS over native semantic HTML controls, pinned and self-hosted with fonts and icons; no React or Web Awesome runtime, no CDN assets, no glass effects, no dark theme, no rich-text editor, no onboarding. daisyUI is conditional on a target-browser check; if it fails, the findings go back to the operator with a Bootstrap alternative. Accessibility baseline: visible keyboard focus, non-colour state cues, reduced-motion behaviour, touch targets of at least 44 by 44 CSS pixels, contrast validated in the real token combinations.
- Browser support: the latest two major Safari and iPadOS releases, current desktop Chrome, Firefox, Edge and Safari. Older iPads are not promised.

Domain model

- A case holds a fictional case identifier, the notes with a notes revision marker, the current draft with the notes revision it was generated from, a per-section manually-edited flag, the pending proposal (if any) with its notes revision, the clarification list and timestamps. Cases list, open and delete; nothing else.
- Notes are one editable text body per case. Every saved change advances the notes revision. A transcript is appended to the notes as a marked passage once the physician accepts it; it never replaces existing text.
- A draft has exactly the fixed sections: admission reason, pain history, relevant history and findings, previous therapy attempts, functional and psychosocial impact, inpatient justification, therapy goals (present only when supplied). Each section holds paragraphs; each generated paragraph carries an input reference (a span of the notes); a paragraph the physician rewrote carries none.
- The clarification list is a list of items, each naming the section it affects and the missing or contradictory information, in the physician's language.
- Structured content the draft must respect: pain problems (site, radiation, course, intensity, modifiers, limitations, main pain only when named), provenance (patient report, prior finding, physician finding, unknown), dates and time windows when supplied, treatments (current or previous; substance, dose, duration, effect, adverse effects, discontinuation reason, each only when supplied), user-entered scores with instrument, version and date when known.

Generation contract

- Generation runs only on the physician's explicit action. The service sends the notes to the text model adapter and receives a structured result: sections with paragraphs and input references, and the clarification list. Prose with no structure is rejected as a failed generation.
- A generation result is stored as one proposal for the whole draft next to the current draft, bound to the notes revision it was generated from. The physician accepts or discards it with one action; there is no per-section acceptance (ADR 0008).
- Acceptance replaces only sections without the manually-edited flag, including sections edited while the proposal was pending. The API reports the sections it would skip before acceptance and the UI names them; after acceptance the skipped sections keep their flag and the label "manuell bearbeitet, nicht aktualisiert", and the proposal's alternative text for them stays visible until the proposal is finally accepted or discarded. Acceptance adopts the proposal's clarification list for the case; manual edits never resolve clarification items.
- When the current notes revision differs from the proposal's, the proposal is outdated: it stays visible, the API refuses to accept it, and the UI labels it "Notizen seit diesem Vorschlag geändert". The physician discards it and regenerates explicitly; Lindra never regenerates on its own, and an outdated proposal never clears the draft's stale state.
- When the notes revision moves past the one the current draft was generated from, the draft is stale: one document-wide banner says it is possibly outdated. No per-section staleness is guessed. The stale state clears only when a proposal generated from the current notes revision is accepted; sections skipped on acceptance stay marked as not updated.
- Section badges carry exactly three meanings: the pending proposal changes this section, the section is manually edited, the clarification list has an open item for it. None expresses verification.
- A failed generation leaves notes and current draft untouched and tells the physician it failed and why, in plain words.
- The prompt and post-processing enforce the intended purpose (ADR 0001): no inference of diagnoses, causes, justification, doses, interactions, normal findings or provenance; no ranking of pain problems; no resolution of contradictions; no completeness or approval claims. The structured result is checked for input references that do not point into the notes and for sections the notes did not support; such paragraphs are dropped and the gap goes on the clarification list.

Adapters

- A text model adapter with three implementations: the fixture model (deterministic, keyed to the fictional cast, used by all tests and by the test tier), a self-hosted model adapter speaking to a local inference server on the same host or network, and a hosted-inference adapter (Ollama Cloud was named) that is usable only in the explicitly launched evaluation configuration and refuses to start anywhere else (ADR 0003). The product configuration has no cloud option and no fallback. Whether the named provider runs inference in Europe is unverified and, even if true, does not make it local.
- A speech-to-text adapter with two implementations: canned transcripts keyed to fixture audio, and a self-hosted recogniser (candidates from research: whisper.cpp, faster-whisper) chosen after evaluation on the available hardware with German medical text. Audio is held in memory or a temporary file only for the duration of transcription.
- The browser captures audio with explicit start and stop, shows the dictation state, uploads the audio for transcription and shows the transcript for review before the physician accepts it into the notes. Browser microphone capture requires a secure origin (HTTPS), which the private-network setup must provide.
- Which concrete models fit the hardware and reach acceptable German quality is unverified and is settled inside an implementation ticket with a recorded result, not assumed by this spec.

Seams for tests

- Primary seam: the application's HTTP API with the fixture model and canned transcripts. Every workflow test goes through it: cases, notes autosave and revisions, dictation and transcript review, generation, proposal acceptance with skipped manually-edited sections, refusal of an outdated proposal, staleness, failure preservation, input references and their loss on rewrite, clarification list adoption, section copy text.
- Pure logic tests where the behaviour is a function: the result check (dropping unsupported paragraphs and unreferenced spans), the acceptance merge (which sections are replaced, which retained and labelled), outdated-proposal detection from notes revisions, staleness, transcript append, section plain-text rendering.
- One small browser flow (iPad-sized portrait with tabs, and desktop viewport side by side) covering notes input, generation, accepting a proposal with one hand-edited section retained and labelled, changing notes while a proposal is pending and seeing acceptance disabled, editing and copying a section, tapping an input reference, plus dictation start, stop, review and accept with a canned transcript. The flow also checks keyboard focus visibility and touch-target size on the primary actions.

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

- **Operator-run, before merge of the scaffold ticket:** on Ella's physical iPad in Safari over the private network, open the scaffold's sample page built on the chosen CSS distribution and confirm it renders, controls are tappable at 44 by 44 CSS pixels, keyboard focus is visible with an external keyboard, and reduced motion is respected. This is the compatibility check ADR 0009 requires before the CSS distribution is committed to; a failure goes back to the operator with a Bootstrap alternative.
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
- Per-section acceptance of a proposal; automatic regeneration; guessing which sections are stale.
- A dark theme, glass or refraction effects, a rich-text editor, onboarding, generated artwork, logo or brand work; a React or Web Awesome runtime; runtime CDN assets; older iPads outside the support policy.
- Ambient recording or any recording of patient conversations; operating-system or browser dictation.
- Cloud text models in the product, including as a fallback; cloud speech recognition in any form. The only hosted inference is the fictional-case evaluation comparison (ADR 0003).
- Native Apple app; offline synchronisation.
- Use with real patient data; this is an evaluation release (ADR 0006).

## Further Notes

- Speech input was added to the first release by the operator's last amendment in the grilling and is binding: voice and text are equal inputs in every ticket, test and acceptance check.
- The admission form and the German pain questionnaire (DSF 12/2024 with an additional PDI sheet) that Ella supplied are a structural reference only. Do not assume the PDI is absent from the local workflow; do not reproduce the forms; do not publish them or the transcript in the repository. The admission PDF's text layer is damaged and the spoken template was mistranscribed, so neither is a template.
- Open technical prerequisites, each resolved inside its ticket with a recorded result: model and recogniser choice and hardware suitability; where the hosted comparison provider actually runs inference and under which terms (unverified, to be researched before it is recorded as fact); iPad browser audio capture and formats; suitability of Linux 790 as the test host; the production host pending the legal check.
- The case-screen prototype (`docs/prototypes/SPEC-1/case-screen.html`, variant A chosen in grilling 3) settled the layout and the proposal and dictation states. Its reducer was corrected after grilling 3 so that acceptance preserves manually edited sections and refuses outdated proposals; the prototype is a record, not code to lift as is.
- The fictional cast is owned by the environments ticket (seed data and the `reset` mechanism, provable before case storage exists); the cases ticket integrates it into case storage. There is no second dataset.
- Apple-platform work does not exist in this release; should a later decision change the platform, its tickets are routed to the Mac node first.
