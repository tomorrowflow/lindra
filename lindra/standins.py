"""Deterministic stand-ins for the text model and speech recognition (ADR 0003).

The throwaway and test tiers run only these. The fixture text model returns the
expected draft of a cast encounter; the fixture speech recogniser returns the
canned transcript of a cast clip. Neither guesses: input outside the cast is
refused, so a test never passes on invented output. Tests with stand-ins prove
the workflow, not medical fidelity or recognition quality.
"""

from __future__ import annotations

import hashlib
from typing import Any

from lindra.cast import Cast, Paragraph, fixture_audio
from lindra.textmodel import NOTES_SOURCE, GenerationFailed, GenerationRequest


class NotInTheCast(LookupError):
    """The stand-in only knows the fictional cast."""


class FixtureTextModel:
    """The cast's expected drafts, found by case number, encounter kind and date.

    The model does not read the notes beyond that key: the draft of a cast encounter is the
    same whatever the notes say, so a test can change the notes and still get the draft whose
    references point into the cast's own notes.
    """

    def __init__(self, cast: Cast) -> None:
        self._encounters = {
            (case.case_number, encounter.kind, encounter.date): encounter
            for case in cast.cases
            for encounter in case.encounters
        }

    def generate(self, request: GenerationRequest) -> dict[str, Any]:
        key = (request.case_number, request.kind, request.occurred_at.date())
        encounter = self._encounters.get(key)
        if encounter is None:
            raise GenerationFailed(
                "Das Textmodell kennt diesen Kontakt nicht: Es arbeitet nur mit den "
                "erfundenen Fällen."
            )
        return {
            "sections": [
                {"title": title, "paragraphs": [_paragraph(p) for p in paragraphs]}
                for title, paragraphs in encounter.draft.items()
            ],
            "clarifications": [
                {"section": c.section, "text": c.text} for c in encounter.clarifications
            ],
        }


def _paragraph(paragraph: Paragraph) -> dict[str, Any]:
    return {
        "text": paragraph.text,
        "heading": paragraph.heading,
        "references": [{"source": NOTES_SOURCE, "quote": quote} for quote in paragraph.quotes],
    }


class FixtureSpeech:
    def __init__(self, cast: Cast) -> None:
        self._transcripts = {
            hashlib.sha256(fixture_audio(clip.key)).hexdigest(): clip.transcript
            for case in cast.cases
            for encounter in case.encounters
            for clip in encounter.audio
        }

    def transcribe(self, audio: bytes) -> str:
        transcript = self._transcripts.get(hashlib.sha256(audio).hexdigest())
        if transcript is None:
            raise NotInTheCast("this audio is not fixture audio of the fictional cast")
        return transcript
