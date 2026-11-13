"""The evaluation configuration's guards: only the fictional cast (ADR 0003, ADR 0006, ADR 0007).

A real or hosted backend sees only the invented cases. Two guards keep it so. The first runs at
start: the database may hold the cast's cases and nothing else, by case number and patient
name. The second runs on every call: the text model is asked only for a case that is in the
cast, so a case created after the start never reaches a real model.
"""

from __future__ import annotations

from lindra.cast import Cast
from lindra.store import Store
from lindra.textmodel import GenerationFailed, GenerationRequest, TextModel

NOT_THE_CAST = (
    "Das Textmodell arbeitet in der Evaluation nur mit den erfundenen Fällen; dieser Fall "
    "gehört nicht dazu."
)
SPEECH_NOT_THE_CAST = (
    "Die Spracherkennung arbeitet in der Evaluation nur mit den erfundenen Fällen; dieser "
    "Fall gehört nicht dazu."
)


class NonFictionalData(RuntimeError):
    """The evaluation configuration found a case that is not part of the fictional cast."""


def fictional_cases(cast: Cast) -> frozenset[tuple[str, str]]:
    return frozenset((case.case_number, case.patient_name) for case in cast.cases)


def require_fictional_only(store: Store, cast: Cast) -> None:
    """Refuse to start when the database holds anything but the fictional cast.

    An empty database passes. The message names the case numbers found, never a patient name:
    what is not the cast might be a real name, and it must not reach a log.
    """
    known = fictional_cases(cast)
    with store.read() as tx:
        foreign = [
            case.case_number
            for case in tx.list_cases()
            if (case.case_number, case.patient_name) not in known
        ]
    if foreign:
        raise NonFictionalData(
            "The evaluation configuration refuses to start: the database holds a case that is "
            f"not part of the fictional cast ({', '.join(foreign)}). Use an empty data "
            "directory, or one that holds only the cast. Nothing was changed."
        )


class CastOnlyTextModel:
    """The text model, asked only for cases of the cast."""

    def __init__(self, model: TextModel, cast: Cast) -> None:
        self._model = model
        self._case_numbers = frozenset(case.case_number for case in cast.cases)

    def generate(self, request: GenerationRequest):
        if request.case_number not in self._case_numbers:
            raise GenerationFailed(NOT_THE_CAST)
        return self._model.generate(request)
