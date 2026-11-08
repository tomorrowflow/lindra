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
One patient admission as the physician works on it in Lindra: the notes, the current draft, the clarification list and a fictional case identifier. A case is never the patient's record.
_Avoid_: patient, chart, file, record

**Case identifier**:
The short fictional label the physician gives a case to find it again. It is never a patient name, date of birth or hospital number.

**Notes**:
The physician's free-form input for a case: typed or pasted text, or a corrected transcript, in any order and without a required structure. Notes are what a draft is generated from.
_Avoid_: input, source text, prompt, anamnesis

**Dictation**:
A recording the physician explicitly starts and stops to speak their own notes after the assessment. Never a recording of a conversation with the patient.
_Avoid_: ambient recording, scribe, consultation recording

**Transcript**:
The text produced from a dictation, shown to the physician for review and correction before it becomes part of the notes. A transcript never replaces typed text on its own.

**Letter**:
The admission letter the hospital system expects. Lindra produces only its physician-authored sections; the other disciplines' sections and the final discharge synthesis are not Lindra's.
_Avoid_: report, epicrisis, discharge summary

**Section**:
One of the fixed parts of the letter that Lindra drafts: admission reason, pain history, relevant history and findings, previous therapy attempts, functional and psychosocial impact, the physician's inpatient justification, and, when supplied, therapy goals.

**Draft**:
The wording Lindra proposes for the letter sections from the current notes. A draft is a proposal the physician accepts or discards; it never silently replaces the physician's edits.
_Avoid_: output, result, generated letter

**Generation**:
The explicit action by which the physician asks for a new draft from the current notes. Nothing is generated without it.

**Stale draft**:
A draft whose notes changed after it was generated. Lindra marks it; it does not regenerate on its own.

**Clarification list**:
The list of information the physician must still supply or resolve because the notes were missing it or contradicted themselves. Lindra still drafts every section the notes support.
_Avoid_: warnings, errors, gaps, validation

**Input reference**:
The pointer from a paragraph of the draft to the passage of the notes it was written from. It shows origin, not correctness.
_Avoid_: citation, source, confidence

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
