"""Measure a text model and a recogniser on the fictional cast (ADR 0003).

The operator runs this in the evaluation configuration (`scripts/evaluation.py measure`) to fill
`docs/evaluation/real-backends.md`. Each cast encounter is sent through the same path the
physician's generation takes (`review.ask`: structure check, then fidelity check), typed as the
cast has it and dictated as the physician's flow has it: the recognised clip appended to the
typed notes as a marked passage. The numbers are mechanical: latency, how many of the
passages the expected draft rests on came back as references, how many paragraphs the
fidelity check dropped, whether the gaps the cast expects were flagged, and the word error
rate of a transcript. They do not judge German wording or clinical fidelity; the physician
reads the output for that, and the record keeps her judgement apart from these numbers.

Nothing here writes audio or notes anywhere: the recordings are the operator's own files of the
cast's canned transcripts, read into memory.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from datetime import time as clock_time
from pathlib import Path
from typing import Any

from lindra import background, dictation, drafts, review
from lindra.cast import SECTIONS, Case, Cast, Encounter
from lindra.speech import SpeechRecognizer, TranscriptionFailed
from lindra.textmodel import (
    NOTES_SOURCE,
    BackgroundEncounter,
    GenerationFailed,
    GenerationRequest,
    TextModel,
)

TYPED, DICTATED = "typed", "dictated"
OK = "ok"
NO_RECORDING = "no recording"
UNSTRUCTURED = drafts.UNSTRUCTURED
CARRIES = "carries the workflow (mechanical check only; the physician judges the German)"
CANNOT_CARRY = "cannot carry the workflow"
# The marker of a dictated passage needs a time; the harness uses one fixed time.
DICTATION_TIME = datetime(2026, 11, 10, 12, 0)
ENCOUNTER_TIME = clock_time(9, 0)

Clock = Callable[[], float]


@dataclass(frozen=True)
class TextRow:
    case_number: str
    encounter: str
    mode: str
    outcome: str
    seconds: float
    sections_filled: int = 0
    sections_total: int = 0
    sections_unexpected: int = 0
    paragraphs_returned: int = 0
    paragraphs_dropped: int = 0
    passages_expected: int = 0
    passages_carried: int = 0
    gaps_expected: int = 0
    gaps_flagged: int = 0


@dataclass(frozen=True)
class SpeechRow:
    clip: str
    outcome: str
    seconds: float | None = None
    word_error_rate: float | None = None
    audio_bytes: int = 0


class Recording:
    """The model, remembering the raw result of its last call."""

    def __init__(self, model: TextModel) -> None:
        self._model = model
        self.raw: Any = None

    def generate(self, request: GenerationRequest) -> Any:
        self.raw = self._model.generate(request)
        return self.raw


# ---- the text model ----


def measure_text(
    model: TextModel, cast: Cast, mode: str = TYPED, clock: Clock = time.perf_counter
) -> list[TextRow]:
    """Every encounter of the cast, notes as the cast has them."""
    return [
        run_text(model, case, encounter, encounter.notes, mode, clock)
        for case in cast.cases
        for encounter in case.encounters
    ]


def measure_dictated(
    model: TextModel,
    speech: SpeechRecognizer,
    cast: Cast,
    audio_dir: Path,
    clock: Clock = time.perf_counter,
) -> list[TextRow]:
    """Every encounter that has a clip, with the recognised clip appended to its notes."""
    rows = []
    for case in cast.cases:
        for encounter in case.encounters:
            if not encounter.audio:
                continue
            notes = encounter.notes
            failure = None
            for clip in encounter.audio:
                recording = find_recording(audio_dir, clip.key)
                if recording is None:
                    failure = NO_RECORDING
                    break
                try:
                    notes = dictation.append(
                        notes, speech.transcribe(recording.read_bytes()), DICTATION_TIME
                    )
                except TranscriptionFailed as error:
                    failure = f"failed: {error.reason}"
                    break
            if failure:
                rows.append(TextRow(case.case_number, encounter.key, DICTATED, failure, 0.0))
            else:
                rows.append(run_text(model, case, encounter, notes, DICTATED, clock))
    return rows


def run_text(
    model: TextModel, case: Case, encounter: Encounter, notes: str, mode: str, clock: Clock
) -> TextRow:
    request = GenerationRequest(
        case.case_number,
        encounter.kind,
        datetime.combine(encounter.date, ENCOUNTER_TIME),
        notes,
        background=tuple(earlier_encounters(case, encounter)),
    )
    recorder = Recording(model)
    started = clock()
    try:
        generated = review.ask(recorder, request)
        outcome = OK
    except GenerationFailed as error:
        generated, outcome = None, f"failed: {error.reason}"
    seconds = clock() - started
    if generated is None:
        return TextRow(
            case.case_number,
            encounter.key,
            mode,
            outcome,
            seconds,
            sections_total=len(SECTIONS[encounter.kind]),
            passages_expected=len(expected_passages(encounter)),
            gaps_expected=len(encounter.clarifications),
        )
    returned = drafts.parse_generated(recorder.raw, encounter.kind)
    kept = sum(len(s.paragraphs) for s in generated.sections)
    asked = sum(len(s.paragraphs) for s in returned.sections)
    expected = expected_passages(encounter)
    carried = quoted_passages(generated)
    flagged = {item.section for item in generated.clarifications}
    return TextRow(
        case.case_number,
        encounter.key,
        mode,
        outcome,
        seconds,
        sections_filled=sum(1 for s in generated.sections if s.paragraphs),
        sections_total=len(generated.sections),
        sections_unexpected=sum(
            1 for s in generated.sections if s.paragraphs and not encounter.draft.get(s.title)
        ),
        paragraphs_returned=asked,
        paragraphs_dropped=asked - kept,
        passages_expected=len(expected),
        passages_carried=sum(1 for passage in expected if carries(carried, passage)),
        gaps_expected=len(encounter.clarifications),
        gaps_flagged=sum(1 for item in encounter.clarifications if item.section in flagged),
    )


def earlier_encounters(case: Case, encounter: Encounter) -> list[BackgroundEncounter]:
    """The background of a visit as the physician's flow sends it: what the cast's timeline
    says was accepted, here the expected draft of each earlier encounter."""
    found = []
    for number, key in enumerate(encounter.background, start=1):
        earlier = next(e for e in case.encounters if e.key == key)
        sections = tuple(
            (title, "\n\n".join(p.text for p in paragraphs))
            for title, paragraphs in earlier.draft.items()
            if paragraphs
        )
        found.append(
            BackgroundEncounter(
                background.source_key(number),
                earlier.kind,
                datetime.combine(earlier.date, ENCOUNTER_TIME),
                sections,
            )
        )
    return found


def expected_passages(encounter: Encounter) -> list[str]:
    """The passages of the notes the expected draft was written from."""
    paragraphs = [p for section in encounter.draft.values() for p in section]
    return [quote for paragraph in paragraphs for quote in paragraph.quotes]


def quoted_passages(generated: drafts.Generated) -> list[str]:
    return [
        squash(reference.quote)
        for section in generated.sections
        for paragraph in section.paragraphs
        for reference in paragraph.references
        if reference.source == NOTES_SOURCE
    ]


def carries(quoted: Iterable[str], passage: str) -> bool:
    wanted = squash(passage)
    return any(wanted in quote or quote in wanted for quote in quoted if quote)


def squash(text: str) -> str:
    return " ".join(text.split()).casefold()


def verdict(rows: list[TextRow]) -> str:
    """A model that fails on an encounter, or returns nothing of the passages an encounter
    rests on, cannot carry the workflow. Anything else only passes the mechanical check."""
    for row in rows:
        if row.outcome != OK or (row.passages_expected and row.passages_carried == 0):
            return CANNOT_CARRY
    return CARRIES


# ---- the recogniser ----


def measure_speech(
    speech: SpeechRecognizer, cast: Cast, audio_dir: Path, clock: Clock = time.perf_counter
) -> list[SpeechRow]:
    rows = []
    for case in cast.cases:
        for encounter in case.encounters:
            for clip in encounter.audio:
                recording = find_recording(audio_dir, clip.key)
                if recording is None:
                    rows.append(SpeechRow(clip.key, NO_RECORDING))
                    continue
                audio = recording.read_bytes()
                started = clock()
                try:
                    text = speech.transcribe(audio)
                except TranscriptionFailed as error:
                    rows.append(
                        SpeechRow(clip.key, f"failed: {error.reason}", audio_bytes=len(audio))
                    )
                    continue
                rows.append(
                    SpeechRow(
                        clip.key,
                        OK,
                        clock() - started,
                        word_error_rate(clip.transcript, text),
                        len(audio),
                    )
                )
    return rows


def find_recording(audio_dir: Path, key: str) -> Path | None:
    """The operator's recording of a clip: `<key>` with any extension."""
    found = sorted(audio_dir.glob(f"{key}.*"))
    return found[0] if found else None


def words(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold())


def word_error_rate(reference: str, hypothesis: str) -> float:
    """Substitutions, insertions and deletions over the words of the reference."""
    wanted, heard = words(reference), words(hypothesis)
    if not wanted:
        return 0.0 if not heard else 1.0
    previous = list(range(len(heard) + 1))
    for i, word in enumerate(wanted, start=1):
        current = [i]
        for j, other in enumerate(heard, start=1):
            current.append(
                min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (word != other))
            )
        previous = current
    return previous[-1] / len(wanted)


# ---- the report ----


def render(text_rows: list[TextRow], speech_rows: list[SpeechRow] | None = None) -> str:
    """The rows as Markdown tables for the evaluation record."""
    lines = [
        "| Case | Encounter | Mode | Outcome | Seconds | Sections filled | Unexpected | "
        "Paragraphs returned / dropped | Passages carried | Gaps flagged |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in text_rows:
        lines.append(
            f"| {row.case_number} | {row.encounter} | {row.mode} | {row.outcome} | "
            f"{row.seconds:.1f} | {row.sections_filled} of {row.sections_total} | "
            f"{row.sections_unexpected} | {row.paragraphs_returned} / {row.paragraphs_dropped} | "
            f"{row.passages_carried} of {row.passages_expected} | "
            f"{row.gaps_flagged} of {row.gaps_expected} |"
        )
    lines += ["", f"Text model {verdict(text_rows)}." if text_rows else ""]
    if speech_rows:
        lines += [
            "",
            "| Clip | Outcome | Seconds | WER |",
            "| --- | --- | --- | --- |",
        ]
        for clip in speech_rows:
            seconds = "" if clip.seconds is None else f"{clip.seconds:.1f}"
            rate = "" if clip.word_error_rate is None else f"{clip.word_error_rate:.2f}"
            lines.append(f"| {clip.clip} | {clip.outcome} | {seconds} | {rate} |")
    return "\n".join(lines) + "\n"
