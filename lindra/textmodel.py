"""The text model adapter interface (ADR 0003).

Lindra asks the model for a draft through this one interface. The fixture model in
`lindra/standins.py` implements it for the tests and the test tier; a self-hosted and a
hosted-comparison adapter follow with ticket 11. An adapter returns what its model produced
as plain data (sections, paragraphs, input references, clarification items). The service
checks that structure in `lindra/drafts.py`: prose with no structure is a failed
generation, never a draft.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

# The only source a reference points to in this release: a passage of the encounter's notes.
# A visit's background (ticket 09) adds another.
NOTES_SOURCE = "notes"


class GenerationFailed(Exception):
    """The model gave no usable draft. `reason` is a sentence for the status area."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class GenerationRequest:
    """What the model sees: the encounter's own notes and nothing else (ADR 0010 adds the
    background of a visit with ticket 09)."""

    case_number: str
    kind: str
    occurred_at: datetime
    notes: str


class TextModel(Protocol):
    def generate(self, request: GenerationRequest) -> Any:
        """The model's result: a dict of sections and clarification items.

        Raises `GenerationFailed` when the model cannot answer. Any other result shape is
        checked, and refused, by the caller.
        """
        ...
