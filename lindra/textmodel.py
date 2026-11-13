"""The text model adapter interface (ADR 0003).

Lindra asks the model for a draft through this one interface. The fixture model in
`lindra/standins.py` implements it for the tests and the test tier; a self-hosted and a
hosted-comparison adapter follow with ticket 11. An adapter returns what its model produced
as plain data (sections, paragraphs, input references, clarification items). The service
checks that structure in `lindra/drafts.py`: prose with no structure is a failed
generation, never a draft. It then checks in `lindra/fidelity.py` what the notes and the
background support and drops the rest, whatever the adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from lindra.prompt import instructions_for

# The source of a reference into the encounter's own notes. A reference into the background of
# a visit names the background encounter instead (`lindra/background.py`).
NOTES_SOURCE = "notes"


class GenerationFailed(Exception):
    """The model gave no usable draft. `reason` is a sentence for the status area."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class BackgroundEncounter:
    """One earlier encounter of the case as the model sees it: its accepted draft.

    `source` is the key a reference to it carries, `sections` the title and plain text of
    each section that has any. Only accepted drafts get here (ADR 0010).
    """

    source: str
    kind: str
    occurred_at: datetime
    sections: tuple[tuple[str, str], ...]

    @property
    def text(self) -> str:
        """The draft as one text; this is what a reference into it quotes from."""
        return "\n\n".join(f"{title}\n{text}" for title, text in self.sections)


@dataclass(frozen=True)
class GenerationRequest:
    """What the model sees: the instructions, the encounter's own notes and, for a visit,
    its background (the accepted draft of the assessment and of earlier visits) and nothing
    else. A pending proposal and a later visit are never in it (ADR 0010)."""

    case_number: str
    kind: str
    occurred_at: datetime
    notes: str
    background: tuple[BackgroundEncounter, ...] = ()
    instructions: str = ""

    def __post_init__(self) -> None:
        if not self.instructions:
            object.__setattr__(self, "instructions", instructions_for(self.kind))


class TextModel(Protocol):
    def generate(self, request: GenerationRequest) -> Any:
        """The model's result: a dict of sections and clarification items.

        Raises `GenerationFailed` when the model cannot answer. Any other result shape is
        checked, and refused, by the caller.
        """
        ...
