"""Badges for encounters and sections (ADR 0008).

A badge is an icon; its label is the accessible name and its explanation opens on tap. A
badge names what Lindra holds, never whether it is correct. The encounter badge in the sidebar
and the overview says one thing about the whole encounter. A section badge on a section's
heading says one thing about that section. The background-changed state of a visit joins
with ticket 09.
"""

from __future__ import annotations

from dataclasses import dataclass

from lindra import drafts
from lindra.store import Encounter


@dataclass(frozen=True)
class Badge:
    icon: str
    label: str
    explanation: str
    # The short word shown next to the icon on the active section, for the states that
    # change what the physician can do.
    word: str = ""


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
HAS_DRAFT = Badge(
    icon="file-check",
    label="Entwurf vorhanden",
    explanation="Für diesen Kontakt gibt es einen Entwurf. Die Übergabe kopiert ihn.",
)
PROPOSAL_PENDING = Badge(
    icon="file-diff",
    label="Vorschlag liegt vor",
    explanation=(
        "Ein Vorschlag wartet auf Ihre Entscheidung. Er ändert den Entwurf erst, "
        "wenn Sie ihn übernehmen."
    ),
)
PROPOSAL_OUTDATED = Badge(
    icon="clock",
    label="Vorschlag veraltet",
    explanation=(
        "Die Notizen haben sich seit diesem Vorschlag geändert. Er lässt sich nicht "
        "übernehmen. Verwerfen Sie ihn oder erzeugen Sie einen neuen."
    ),
)
DRAFT_POSSIBLY_OUTDATED = Badge(
    icon="triangle-alert",
    label="Entwurf möglicherweise veraltet",
    explanation=(
        "Die Notizen haben sich seit dem letzten übernommenen Entwurf geändert. Lindra "
        "vermutet nicht, welche Abschnitte betroffen sind."
    ),
)

# The states a page can swap in without a reload.
STATES = {
    "empty": NO_NOTES,
    "notes": NOTES_ONLY,
    "draft": HAS_DRAFT,
    "proposal": PROPOSAL_PENDING,
    "outdated": PROPOSAL_OUTDATED,
    "possibly_outdated": DRAFT_POSSIBLY_OUTDATED,
}


def encounter_state(encounter: Encounter) -> str:
    """The most urgent thing to say about an encounter, as a key of `STATES`."""
    if encounter.has_proposal:
        outdated = encounter.proposal_revision != encounter.notes_revision
        return "outdated" if outdated else "proposal"
    if drafts.draft_possibly_outdated(encounter.draft_revision, encounter.notes_revision):
        return "possibly_outdated"
    if encounter.has_draft:
        return "draft"
    return "notes" if encounter.has_notes else "empty"


def encounter_badge(encounter: Encounter) -> Badge:
    return STATES[encounter_state(encounter)]


# ---- section badges ----

PROPOSED = Badge(
    icon="file-diff",
    label="Vorschlag ändert diesen Abschnitt",
    explanation=(
        "Der Vorschlag enthält anderen Text für diesen Abschnitt. Er ersetzt den Entwurf "
        "erst, wenn Sie den ganzen Vorschlag übernehmen."
    ),
)
OUTDATED = Badge(
    icon="clock",
    label="Veraltet",
    explanation=(
        "Die Notizen haben sich seit dem Vorschlag geändert. Er lässt sich nicht übernehmen."
    ),
    word="Veraltet",
)
MANUAL = Badge(
    icon="pencil",
    label="Von Hand bearbeitet",
    explanation="Sie haben diesen Abschnitt selbst geschrieben. Eine Übernahme ersetzt ihn nicht.",
)
NOT_UPDATED = Badge(
    icon="circle-minus",
    label="Nicht aktualisiert",
    explanation=(
        "Dieser Abschnitt ist von Hand bearbeitet. Bei der letzten Übernahme blieb er, wie er war."
    ),
    word="Nicht aktualisiert",
)
OPEN_QUESTION = Badge(
    icon="circle-help",
    label="Offene Frage",
    explanation="Zu diesem Abschnitt gibt es eine offene Frage in der Klärungsliste.",
)
COPIED = Badge(
    icon="clipboard-check",
    label="Kopiert",
    explanation="Dieser Abschnitt wurde aus dem aktuellen Entwurf kopiert.",
)


def section_state(review, index: int) -> Badge:
    """The one-line state of a section step: an icon, a short line and its explanation."""
    section = review.sections[index]
    if review.proposal is not None:
        if review.outdated:
            return Badge(
                "clock",
                "Vorschlag veraltet",
                drafts.OUTDATED_REASON + ". Verwerfen Sie ihn oder erzeugen Sie einen neuen.",
            )
        if section.manual:
            return Badge(
                "pencil",
                "Von Hand bearbeitet, der Vorschlag ersetzt den Abschnitt nicht",
                "Die Fassung des Vorschlags bleibt rechts sichtbar, bis Sie den Vorschlag "
                "übernehmen oder verwerfen. Wollen Sie sie, übernehmen Sie sie von Hand.",
            )
        proposed = review.proposal.sections[index]
        if drafts.section_text(proposed) != drafts.section_text(section):
            return Badge("file-diff", PROPOSED.label, PROPOSED.explanation)
        return Badge(
            "check",
            "Vorschlag gleicht dem Entwurf",
            "Der Vorschlag hat für diesen Abschnitt denselben Text wie der Entwurf.",
        )
    if review.draft is None:
        return Badge(
            "file",
            "Noch kein Entwurf",
            "Erzeugen Sie einen Entwurf aus den Notizen oder schreiben Sie diesen Abschnitt "
            "selbst.",
        )
    if section.manual:
        return Badge("pencil", MANUAL.label, "Sie haben diesen Abschnitt selbst geschrieben.")
    return Badge(
        "file-check",
        "Entwurf vorhanden",
        "Dieser Abschnitt ist Teil des aktuellen Entwurfs.",
    )


def section_badges(review, index: int) -> list[Badge]:
    """The badges of one section, in the order the heading shows them.

    `review` is an `EncounterReview`. A proposal marks a section as changed only when its
    text differs from the draft's and the section is not manual, since acceptance would leave
    a manual section alone.
    """
    section = review.sections[index]
    found: list[Badge] = []
    if review.proposal is not None:
        proposed = review.proposal.sections[index]
        differs = drafts.section_text(proposed) != drafts.section_text(section)
        if review.outdated:
            found.append(OUTDATED)
        elif differs and not section.manual:
            found.append(PROPOSED)
    if section.manual:
        found.append(MANUAL)
    if section.not_updated:
        found.append(NOT_UPDATED)
    if review.clarifications_for(section.title):
        found.append(OPEN_QUESTION)
    if section.copied:
        found.append(COPIED)
    return found
