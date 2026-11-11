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
    references point into the cast's own notes. It reads the background only to know which
    earlier encounters it was given: a paragraph that draws on an encounter missing from the
    request is left out, as a model that never saw it could not have written it, and a
    reference to one that was given names it by the source the request carries.
    """

    def __init__(self, cast: Cast) -> None:
        self._encounters = {
            (case.case_number, encounter.kind, encounter.date): (case, encounter)
            for case in cast.cases
            for encounter in case.encounters
        }

    def generate(self, request: GenerationRequest) -> dict[str, Any]:
        key = (request.case_number, request.kind, request.occurred_at.date())
        found = self._encounters.get(key)
        if found is None:
            raise GenerationFailed(
                "Das Textmodell kennt diesen Kontakt nicht: Es arbeitet nur mit den "
                "erfundenen Fällen."
            )
        case, encounter = found
        sources = {
            other.key: given.source
            for given in request.background
            for other in case.encounters
            if (other.kind, other.date) == (given.kind, given.occurred_at.date())
        }
        sections = []
        for title, paragraphs in encounter.draft.items():
            written = [_paragraph(p, sources) for p in paragraphs]
            sections.append({"title": title, "paragraphs": [w for w in written if w]})
        return {
            "sections": sections,
            "clarifications": [
                {"section": c.section, "text": c.text} for c in encounter.clarifications
            ],
        }


def _paragraph(paragraph: Paragraph, sources: dict[str, str]) -> dict[str, Any] | None:
    """The paragraph as the model returns it, or None when it rests only on background the
    request did not carry."""
    references = [{"source": NOTES_SOURCE, "quote": quote} for quote in paragraph.quotes]
    references += [
        {"source": sources[key], "quote": quote}
        for key, quote in paragraph.background
        if key in sources
    ]
    if not references:
        return None
    return {"text": paragraph.text, "heading": paragraph.heading, "references": references}


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
