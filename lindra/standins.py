"""Deterministic stand-ins for the text model and speech recognition (ADR 0003).

The throwaway and test tiers run only these. The fixture text model returns the
expected draft of a cast encounter; the fixture speech recogniser returns the
canned transcript of a cast clip. Neither guesses: input outside the cast is
refused, so a test never passes on invented output. Tests with stand-ins prove
the workflow, not medical fidelity or recognition quality.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from lindra.cast import Cast, Clarification, fixture_audio

STAND_IN = "fixture"


class NotInTheCast(LookupError):
    """The stand-in only knows the fictional cast."""


@dataclass(frozen=True)
class GeneratedDraft:
    sections: dict[str, str]
    clarifications: tuple[Clarification, ...]


class FixtureTextModel:
    def __init__(self, cast: Cast) -> None:
        self._encounters = {
            (case.case_number, encounter.key): encounter
            for case in cast.cases
            for encounter in case.encounters
        }

    def generate(self, case_number: str, encounter_key: str) -> GeneratedDraft:
        encounter = self._encounters.get((case_number, encounter_key))
        if encounter is None:
            raise NotInTheCast(f"{case_number} {encounter_key} is not in the fictional cast")
        return GeneratedDraft(dict(encounter.draft), encounter.clarifications)


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
