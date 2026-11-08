# Lindra

Lindra is a working assistant for a physician in an inpatient multimodal pain-therapy team. It turns the physician's own notes or dictation after an assessment into the physician-authored sections of the admission letter, which the physician then copies into the hospital system. Settled in the SPEC-1 grilling (November 2026); see `docs/adr/` for the decisions.

## Language

### People and systems

**Physician**:
The single author who uses Lindra: the pain-therapy physician who assessed the patient and supplies every fact, finding and assessment Lindra works with.
_Avoid_: user, doctor, author, clinician

**Hospital system**:
The hospital's own information system, which remains the authoritative patient record and holds the other disciplines' contributions. Lindra never writes to it.
_Avoid_: KIS, EHR, PVS, practice system, record system

**Team**:
The interdisciplinary multimodal pain-therapy team the physician belongs to. In the first release the team does not use Lindra; only the physician does.

### The work

**Case**:
One patient admission as the physician works on it in Lindra: a fictional case identifier, an optional short label, the treatment period, one admission assessment and any number of visits. A case is never the patient's record.
_Avoid_: patient, chart, file, record

**Case identifier**:
The short fictional label the physician gives a case to find it again. It is never a patient name, date of birth or hospital number.

**Treatment period**:
The inclusive span from Behandlungsbeginn to Behandlungsende within which every encounter of the case must lie. It can be corrected later, but never so that an existing encounter falls outside it.
_Avoid_: stay, admission dates, interval

**Encounter**:
One dated contact that has its own notes and its own draft: the admission assessment or a visit. Encounters are never merged, appended to each other or rewritten by a later one.
_Avoid_: entry, record, session

**Admission assessment**:
The one encounter per case that holds the admission findings; its draft follows the clinical headings of the ward's assessment form. German: Aufnahmeassessment.
_Avoid_: intake, anamnesis, admission letter

**Visit**:
A dated encounter after the admission assessment with its own notes and a short progress draft. A visit may be backdated within the treatment period. German: Visite.
_Avoid_: round, progress note, follow-up

**Background**:
What a visit's draft may draw on besides its own notes: the accepted draft of the admission assessment and the accepted drafts of earlier visits only. Later visits and pending proposals are never background.
_Avoid_: context, history, memory

**Changed background**:
The state of a visit's draft or proposal when an encounter in its background was accepted again after the draft or proposal was generated. The text stays; a pending proposal on old background cannot be accepted; nothing regenerates on its own.

**Notes**:
The physician's free-form input for one encounter: typed or pasted text, or a corrected transcript, in any order and without a required structure. Notes are what that encounter's draft is generated from.
_Avoid_: input, source text, prompt, anamnesis

**Dictation**:
A recording the physician explicitly starts and stops to speak their own notes after the assessment. Never a recording of a conversation with the patient.
_Avoid_: ambient recording, scribe, consultation recording

**Transcript**:
The text produced from a dictation, shown to the physician for review and correction before it is appended to the selected encounter's notes. A transcript never replaces typed text on its own. While a dictation runs, nothing else in Lindra can be done.

**Letter**:
The physician-authored text the hospital system expects for an encounter, assembled there from the sections the physician copies out of Lindra. The other disciplines' contributions and the discharge synthesis are not Lindra's.
_Avoid_: report, epicrisis, discharge summary

**Section**:
One fixed part of an encounter's draft, also one review step. Admission assessment: Sozialanamnese; Frühere Anamnese und Vormedikation; Therapeutische Anamnese; Schmerzanamnese; Internistische, vegetative, psychiatrische und Suchtmittelanamnese; Untersuchungsbefunde; Behandlungsplan und vereinbarte Ziele. Visit: Verlauf seit letzter Visite; Aktuelle Befunde; Ärztliche Einschätzung; Vereinbartes Vorgehen und Ziele.

**Draft**:
The current wording of an encounter's sections, generated from its notes and then edited by the physician. New wording arrives only as a proposal; a draft never silently replaces the physician's edits.
_Avoid_: output, result, generated letter

**Review**:
Going through an encounter's sections one step at a time, each step showing the current draft and the proposal side by side. Steps are reachable in any order; next and back are a convenience. German: Durchsicht.
_Avoid_: wizard, form, questionnaire

**Handover**:
The last review step: copying each section of the current draft as plain text into the hospital system, one section at a time. Never the pending proposal. German: Übergabe.
_Avoid_: export, send, publish

**Generation**:
The explicit action by which the physician asks for a new draft from the current notes. Nothing is generated without it.

**Proposal**:
The result of one generation, held next to the current draft until the physician accepts or discards it as a whole. There is no per-section acceptance.
_Avoid_: suggestion, candidate, new version

**Notes revision**:
The exact state of the notes a proposal was generated from. A proposal is bound to it; when the notes move on, the proposal becomes outdated.

**Outdated proposal**:
A proposal whose notes revision is no longer the current notes. It stays visible, cannot be accepted, and must be discarded before a new generation.
_Avoid_: stale proposal, expired

**Stale draft**:
A draft whose notes changed after it was generated. Lindra marks the whole draft with one banner; it does not guess which sections are affected and does not regenerate on its own.

**Manually edited section**:
A section of the draft whose text the physician changed by hand. Accepting a proposal leaves it untouched and labels it as not updated; the proposal's alternative for it stays visible until the proposal is accepted or discarded.
_Avoid_: locked section, protected section

**Clarification list**:
The list of information the physician must still supply or resolve because the notes were missing it or contradicted themselves. Lindra still drafts every section the notes support.
_Avoid_: warnings, errors, gaps, validation

**Input reference**:
The pointer from a generated paragraph of the draft to the passage of the notes it was written from, revealed on tap. It shows origin, not correctness, and a paragraph the physician rewrote loses it.
_Avoid_: citation, source, confidence

**Section badge**:
A small icon on a section heading or sidebar entry that says one thing: the pending proposal changes this section, the section was manually edited, it was not updated on the last acceptance, the clarification list has an open item for it, or it was copied. Never a clinical verification. The explanation opens on tap; the badge itself carries no sentence.
_Avoid_: status, checkmark, banner

### Clinical content

**Pain problem**:
One distinct pain the patient has, kept separate from every other: its site, radiation, course, intensity, modifiers and the limitations it causes. Lindra never merges or ranks pain problems.
_Avoid_: complaint, diagnosis, pain score

**Main pain**:
The pain problem the physician names as the main one. Only the physician can name it.

**Provenance**:
Who a statement comes from: the patient's report, a prior finding from elsewhere, or the physician's own finding. Provenance may be unknown; Lindra never guesses it.
_Avoid_: source, evidence level

**Treatment**:
A current or previous therapy, kept separate from the others, with whatever the physician supplied of substance, dose, duration, effect, adverse effects and reason for discontinuation. Lindra never infers, converts or assesses any of these.
_Avoid_: medication, prescription, therapy attempt

**Inpatient justification**:
The physician's own reasoning why inpatient multimodal pain therapy is indicated. Lindra words it only when the physician supplied it.
_Avoid_: indication, rationale

**Intended purpose**:
What Lindra is for, as written in `docs/adr/0001-intended-purpose.md`: organising and wording facts and assessments the physician supplied. It is the line every function is checked against.

### Delivery

**Fictional cast**:
The three fully invented German cases that every test, demonstration and evaluation of the first release uses. Never a real, transformed or pseudonymised patient.
_Avoid_: test data, sample patients, demo data

**Evaluation release**:
What the first release is: a release used only with the fictional cast to judge whether Lindra saves the physician time without fabricating or losing facts. Use with real patient data needs a separate approval.

**Hosted inference**:
A text model run by an outside provider, allowed only as a comparison backend in the fictional-case evaluation, never as a product backend or fallback. Hosting in the EU does not make it local.
_Avoid_: cloud fallback, local, EU-local

**Stand-in**:
The deterministic replacement for an outside service in tests and in the test environment: the fixture model for the text model, canned transcripts for speech recognition.
_Avoid_: mock, fake, simulator
