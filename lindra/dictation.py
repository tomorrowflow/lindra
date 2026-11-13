"""Dictation operations the JSON API uses: transcribe one recording, append a transcript (ADR 0004).

A dictation is something the physician starts and stops herself. Lindra transcribes the
recording while the request runs and keeps nothing of it. The transcript comes back to her to
correct; only when she accepts it does it reach the notes, as a marked passage after what she
typed. Accepting goes through the same notes write as typing, so the revision advances and a
pending proposal becomes outdated by the one rule that already exists for that.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from lindra import cases, formatting
from lindra.speech import SPEECH_ERROR, SpeechRecognizer, TranscriptionFailed
from lindra.store import OpenedEncounter, Store

log = logging.getLogger(__name__)

# About an hour of speech in a compressed browser recording, far above a dictation.
MAX_AUDIO_BYTES = 25 * 1024 * 1024
NO_RECORDING = "Keine Aufnahme übermittelt"
NO_SPEECH = "In der Aufnahme war nichts zu verstehen."
TRANSCRIPT_MISSING = "Kein Text zum Übernehmen"
TRANSCRIPT_NOT_TEXT = "Das Diktat als Text übermitteln"
DICTATION_ID = re.compile(r"[A-Za-z0-9-]{8,64}")
DICTATION_ID_MISSING = "Kennung des Diktats fehlt"


class NoRecording(Exception):
    """The upload holds no audio."""


class RecordingTooLarge(Exception):
    """The upload is larger than a dictation can be."""


@dataclass(frozen=True)
class Transcript:
    text: str
    # Accepting it would leave the encounter's pending proposal outdated; the overlay says so.
    outdates_proposal: bool


def marker(at: datetime) -> str:
    """The line that opens a dictated passage in the notes."""
    return f"[Diktat, {formatting.german_datetime(at)}]"


def append(notes: str, transcript: str, at: datetime) -> str:
    """The notes with the transcript added as a marked passage at the end.

    What the physician typed stays exactly as it is. The passage starts on a line of its own
    after a blank line, and ends with a line break so typing can go on below it.
    """
    passage = f"{marker(at)}\n{transcript.strip()}\n"
    missing = max(0, 2 - (len(notes) - len(notes.rstrip("\n"))))
    separator = "\n" * missing if notes else ""
    appended = f"{notes}{separator}{passage}"
    if len(appended) > cases.MAX_NOTES_LENGTH:
        raise cases.Invalid(
            {"transcript": f"Die Notizen dürfen höchstens {cases.MAX_NOTES_LENGTH} Zeichen haben"}
        )
    return appended


def parse_transcript(raw: Mapping[str, Any]) -> str:
    """The transcript as the physician corrected it, without its outer blanks."""
    transcript = raw.get("transcript")
    if not isinstance(transcript, str):
        raise cases.Invalid({"transcript": TRANSCRIPT_NOT_TEXT})
    if not transcript.strip():
        raise cases.Invalid({"transcript": TRANSCRIPT_MISSING})
    return transcript.strip()


def parse_dictation_id(raw: Mapping[str, Any]) -> str:
    """The id the browser gave this dictation when its transcript arrived."""
    dictation_id = raw.get("dictation_id")
    if not isinstance(dictation_id, str) or not DICTATION_ID.fullmatch(dictation_id):
        raise cases.Invalid({"dictation_id": DICTATION_ID_MISSING})
    return dictation_id


def recognise(speech: SpeechRecognizer, audio: bytes) -> str:
    """Call the adapter; whatever goes wrong inside it is a failed transcription."""
    try:
        text = speech.transcribe(audio)
    except TranscriptionFailed:
        raise
    except Exception as error:
        log.exception("the speech recogniser failed")
        raise TranscriptionFailed(SPEECH_ERROR) from error
    if not text.strip():
        raise TranscriptionFailed(NO_SPEECH)
    return text.strip()


def transcribe(
    store: Store, speech: SpeechRecognizer, case_id: int, encounter_id: int, audio: bytes
) -> Transcript:
    """The transcript of one recording of this encounter. Nothing is stored: the notes are as
    they were, and the audio is gone when the call returns."""
    cases.get_encounter(store, case_id, encounter_id)
    if not audio:
        raise NoRecording(NO_RECORDING)
    if len(audio) > MAX_AUDIO_BYTES:
        raise RecordingTooLarge(len(audio))
    text = recognise(speech, audio)
    # Read again: a proposal may have been generated or accepted while the audio was processed.
    encounter = cases.get_encounter(store, case_id, encounter_id).encounter
    return Transcript(text, encounter.has_proposal and not encounter.proposal_outdated)


def accept(
    store: Store, case_id: int, encounter_id: int, raw: Mapping[str, Any], at: datetime
) -> OpenedEncounter:
    """Append the corrected transcript to the notes of this encounter and advance their revision.

    The notes are read and written in one transaction, so a note saved a moment earlier is
    never replaced by the append. The dictation's id is remembered in the same transaction: a
    browser that never saw the answer sends the request again, and a dictation that is
    appended already changes nothing the second time. A refused transcript rolls the id back
    with everything else, so it can be sent again, corrected.
    """
    with store.write() as tx:
        if tx.get_case(case_id) is None:
            raise cases.NotFound(cases.NOT_FOUND)
        opened = tx.get_encounter(case_id, encounter_id)
        if opened is None:
            raise cases.NotFound(cases.ENCOUNTER_NOT_FOUND)
        transcript = parse_transcript(raw)
        if tx.record_dictation(encounter_id, parse_dictation_id(raw)):
            tx.set_notes(case_id, encounter_id, append(opened.notes, transcript, at))
        saved = tx.get_encounter(case_id, encounter_id)
    assert saved is not None
    return saved
