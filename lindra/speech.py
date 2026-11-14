"""The speech recognition adapter interface (ADR 0003, ADR 0004).

Lindra asks for a transcript through this one interface. The fixture recogniser in
`lindra/standins.py` implements it for the tests and the test tier; the self-hosted adapter is
in `lindra/backends.py` and runs only in the evaluation configuration. There is no cloud
adapter and no use of the browser's or the operating system's dictation. An adapter gets the
audio of one dictation as bytes and returns its text; Lindra never writes the audio anywhere,
so the recording lives only as long as the call.
"""

from __future__ import annotations

from typing import Protocol

# What the physician reads in the overlay when the adapter fails without saying why.
SPEECH_ERROR = "Die Spracherkennung hat nicht geantwortet."


class TranscriptionFailed(Exception):
    """No transcript came out of the audio. `reason` is a sentence for the overlay."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class SpeechRecognizer(Protocol):
    def transcribe(self, audio: bytes) -> str:
        """The text of one dictation.

        Raises `TranscriptionFailed` when the audio cannot be transcribed.
        """
        ...
