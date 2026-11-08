# 10: Dictation: persistent control, blocking overlay, canned transcripts and append to the encounter's notes

**Track:** dictation

**What to build:** From any step of any encounter the physician starts a dictation through a persistent microphone control aligned with the action bar. A full overlay blocks everything else while recording, transcribing and reviewing the transcript; she corrects the transcript and accepts it, which appends it to the selected encounter's notes and advances the notes revision (so a pending proposal becomes outdated), or discards it. Audio is kept only for transcription. A denied microphone permission or a failed transcription is told to her in the overlay with a way out. Speech recognition runs through an adapter whose test stand-in returns canned transcripts for fixture audio.

**Blocked by:** 01 (Scaffold), 02 (Environments), 05 (Cases and periods), 06 (Encounters and notes)

**Status:** ready-for-agent

**Spec:** PRD stories 10 to 16, 14a; ADR 0003 (self-hosted speech, stand-in), ADR 0004 (explicit dictation, transient audio), ADR 0008 (overlay).

## Acceptance criteria

- [ ] A microphone control is present on every step of an encounter, aligned with the other controls, disabled when no encounter is selected; it starts a dictation explicitly and never records without that action.
- [ ] The overlay shows the states recording (with stop), transcribing (waiting), and reviewing (editable transcript with "In Notizen übernehmen" and "Verwerfen"); while open, navigation and every other interaction are blocked, in landscape and portrait.
- [ ] The browser captures audio only after the physician's start, stops on her stop, uploads it for transcription, and the server holds the audio only until the transcript exists; no audio is stored.
- [ ] The speech adapter interface exists with the canned-transcript stand-in keyed to fixture audio as default; no cloud or browser dictation path exists.
- [ ] Accepting appends the corrected transcript to the selected encounter's notes as a marked passage, never replacing typed text, and advances the notes revision; a pending proposal of that encounter becomes outdated and the overlay said so beforehand; discarding changes nothing.
- [ ] Denied microphone permission and failed transcription are shown inside the overlay in plain words with a way to close or retry; typed notes are never lost by either.
- [ ] HTTP API tests cover transcript upload with the stand-in, append and revision, outdating of a pending proposal, and the failure path; a pure logic test covers the append.
- [ ] Browser flow addition on both viewports: start a dictation from a review step, see the overlay block the step, stop, review and correct the canned transcript, accept and see it in the notes.
- [ ] Operator-run, before merge: on Ella's physical iPad in Safari over the private network (HTTPS), start a dictation from a review step, see the overlay block the rest of the app, stop, see a transcript, correct it and accept it into that encounter's notes; also deny the microphone permission once and see the overlay's message. Confirms microphone capture, secure origin and the overlay on the real device.
- [ ] Unslop: the unslop skill and `references/signs.md` were read before work; the final diff was checked against the signs; the proof names the signs checked and any remaining finding with its reason.
