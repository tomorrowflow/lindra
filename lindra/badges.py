"""The state badge of an encounter in the sidebar and the overview (ADR 0008).

A badge is an icon; its label is the accessible name and its explanation opens on tap.
A badge names what Lindra holds for the encounter, never whether it is correct. Until an
encounter can have a draft, the two states are the two things that can be said of its
notes. The draft states of ADR 0008 (proposal pending, proposal outdated, draft possibly
outdated, background changed) join them with the tickets that create drafts.
"""

from __future__ import annotations

from dataclasses import dataclass

from lindra.store import Encounter


@dataclass(frozen=True)
class Badge:
    icon: str
    label: str
    explanation: str


NO_NOTES = Badge(
    icon="file",
    label="Keine Notizen",
    explanation="Für diesen Kontakt sind noch keine Notizen gespeichert.",
)
NOTES_ONLY = Badge(
    icon="file-text",
    label="Notizen gespeichert, noch kein Entwurf",
    explanation="Die Notizen sind gespeichert. Für diesen Kontakt gibt es noch keinen Entwurf.",
)


def encounter_badge(encounter: Encounter) -> Badge:
    return NOTES_ONLY if encounter.has_notes else NO_NOTES
