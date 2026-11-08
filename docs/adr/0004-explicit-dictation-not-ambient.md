---
status: accepted
date: 2026-11-08
---

# Dictation is explicit, self-spoken and transient; never an ambient recording

Speech input is a dictation the physician explicitly starts and stops to speak their own notes after the assessment. Lindra never records a conversation with the patient. The transcript is reviewed and corrected before it enters the notes and never overwrites typed text on its own. Audio is kept only as long as transcription needs it; there is no audio archive.

We chose this over ambient scribing for three reasons. Recording a consultation requires every participant's permission under §201 StGB, which the setting cannot guarantee. Ambient notes are a crowded commercial market (`docs/research/2026-11-04-prior-art-and-existing-solutions.md`), while the physician's burden is organising information after the assessment. And a self-spoken dictation keeps the physician as the single source of every fact, which the intended purpose (ADR 0001) relies on.

The operator added dictation to the first release late in the grilling and expects a quick move from typing towards dictation plus manual correction, so voice and text are equal inputs that feed the same notes and the same generation workflow.

## Consequences

- The dictation state (idle, recording, transcribing, transcript ready for review) is always visible.
- Microphone capture on the physician's iPad in a browser needs a secure origin (HTTPS) and physical validation that no factory node can run; that check is operator-run.
