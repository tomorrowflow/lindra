"""The review operations the pages and the JSON API share: generate, accept, discard, edit, copy.

Input arrives raw from a form or a JSON body and is checked once here. The rules between a
draft and its proposal are pure and live in `lindra/drafts.py`; this module loads an
encounter, applies them inside one transaction and stores the result.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from lindra import cases, drafts
from lindra.cast import SECTIONS, Clarification
from lindra.store import OpenedEncounter, Store, Tx
from lindra.textmodel import GenerationFailed, GenerationRequest, TextModel

log = logging.getLogger(__name__)

# Only the admission assessment has a review in this release step; a visit's four sections
# and its background arrive with ticket 09.
DRAFTABLE = frozenset({cases.ASSESSMENT})

NOT_DRAFTABLE = "Für Visiten gibt es noch keinen Entwurf"
SECTION_NOT_FOUND = "Abschnitt nicht gefunden"
NO_NOTES = "Zuerst Notizen eintragen"
ALREADY_RUNNING = "Für diesen Kontakt wird gerade ein Entwurf erzeugt"
NO_PROPOSAL = "Es liegt kein Vorschlag vor"
NOTHING_TO_COPY = "Es gibt noch nichts zu kopieren"
MODEL_ERROR = "Das Textmodell hat nicht geantwortet."
SECTION_NOT_TEXT = "Den Text des Abschnitts als Text übermitteln"
MAX_SECTION_LENGTH = 50_000

IDLE, RUNNING, FAILED = "idle", "running", "failed"


class Refused(Exception):
    """The action is not possible in the encounter's current state; the message says why."""


@dataclass(frozen=True)
class GenerationState:
    state: str
    reason: str = ""


class Generations:
    """Which encounters have a generation running and which one failed last.

    Held in memory: a restart forgets a running generation, which then cannot finish
    either, and the failure of an earlier run.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running: set[int] = set()
        self._failures: dict[int, str] = {}

    def begin(self, encounter_id: int) -> bool:
        """Mark a generation as running; False when one runs already."""
        with self._lock:
            if encounter_id in self._running:
                return False
            self._running.add(encounter_id)
            self._failures.pop(encounter_id, None)
            return True

    def end(self, encounter_id: int, failure: str | None = None) -> None:
        with self._lock:
            self._running.discard(encounter_id)
            if failure:
                self._failures[encounter_id] = failure

    def state(self, encounter_id: int) -> GenerationState:
        with self._lock:
            if encounter_id in self._running:
                return GenerationState(RUNNING)
            if encounter_id in self._failures:
                return GenerationState(FAILED, self._failures[encounter_id])
            return GenerationState(IDLE)

    def reset(self) -> None:
        with self._lock:
            self._running.clear()
            self._failures.clear()


@dataclass(frozen=True)
class EncounterReview:
    """An encounter with its draft, proposal and clarification list read out of storage."""

    opened: OpenedEncounter
    draft: drafts.Draft | None
    proposal: drafts.Proposal | None
    clarifications: tuple[Clarification, ...]

    @property
    def encounter(self):
        return self.opened.encounter

    @property
    def titles(self) -> tuple[str, ...]:
        return SECTIONS[self.encounter.kind]

    @property
    def sections(self) -> tuple[drafts.Section, ...]:
        """The sections of the current draft; empty ones when there is no draft yet."""
        return (self.draft or drafts.empty_draft(self.encounter.kind)).sections

    @property
    def outdated(self) -> bool:
        return self.proposal is not None and drafts.proposal_outdated(
            self.proposal, self.encounter.notes_revision
        )

    @property
    def possibly_outdated(self) -> bool:
        return drafts.draft_possibly_outdated(
            self.encounter.draft_revision, self.encounter.notes_revision
        )

    @property
    def plan(self) -> drafts.Plan | None:
        return drafts.plan(self.draft, self.proposal) if self.proposal else None

    def clarifications_for(self, title: str) -> list[Clarification]:
        return [c for c in self.clarifications if c.section == title]


def describe(opened: OpenedEncounter) -> EncounterReview:
    review = opened.review
    draft = drafts.draft_from_json(json.loads(review.draft)) if review.draft else None
    proposal = None
    if review.proposal and opened.encounter.proposal_revision is not None:
        proposal = drafts.proposal_from_json(
            json.loads(review.proposal), opened.encounter.proposal_revision
        )
    clarifications = drafts.clarifications_from_json(json.loads(review.clarifications))
    return EncounterReview(opened, draft, proposal, clarifications)


def load(tx: Tx, case_id: int, encounter_id: int) -> EncounterReview:
    """One draftable encounter of the case, or the reason it cannot be opened."""
    if tx.get_case(case_id) is None:
        raise cases.NotFound(cases.NOT_FOUND)
    opened = tx.get_encounter(case_id, encounter_id)
    if opened is None:
        raise cases.NotFound(cases.ENCOUNTER_NOT_FOUND)
    if opened.encounter.kind not in DRAFTABLE:
        raise cases.NotFound(NOT_DRAFTABLE)
    return describe(opened)


def open_review(store: Store, case_id: int, encounter_id: int) -> EncounterReview:
    with store.read() as tx:
        return load(tx, case_id, encounter_id)


def section_index(review: EncounterReview, number: int) -> int:
    """The zero-based index of the section with this one-based step number."""
    if not 1 <= number <= len(review.titles):
        raise cases.NotFound(SECTION_NOT_FOUND)
    return number - 1


# ---- generation ----


def generate(
    store: Store,
    model: TextModel,
    generations: Generations,
    case_id: int,
    encounter_id: int,
) -> EncounterReview:
    """Ask the model for a draft from the current notes and hold it as the proposal.

    The model runs outside any transaction, so the physician can keep typing: the proposal
    is bound to the notes revision read here, and a note saved meanwhile outdates it. A
    pending proposal, outdated or not, is replaced only when the model delivers; a failed
    generation changes nothing stored. Raises `GenerationFailed` with the reason to show.
    """
    with store.read() as tx:
        review = load(tx, case_id, encounter_id)
        case = tx.get_case(case_id)
    assert case is not None
    notes = review.opened.notes
    if not notes.strip():
        raise Refused(NO_NOTES)
    if not generations.begin(encounter_id):
        raise Refused(ALREADY_RUNNING)
    failure = None
    try:
        request = GenerationRequest(
            case.case_number, review.encounter.kind, review.encounter.occurred_at, notes
        )
        generated = ask(model, request)
        proposal = drafts.Proposal(
            review.encounter.notes_revision, generated.sections, generated.clarifications
        )
        with store.write() as tx:
            load(tx, case_id, encounter_id)
            tx.set_proposal(
                encounter_id, dump(drafts.proposal_to_json(proposal)), proposal.notes_revision
            )
            return load(tx, case_id, encounter_id)
    except GenerationFailed as error:
        failure = error.reason
        raise
    finally:
        generations.end(encounter_id, failure)


def ask(model: TextModel, request: GenerationRequest) -> drafts.Generated:
    """Call the adapter and check its result; anything but a structured draft is a failure."""
    try:
        raw = model.generate(request)
    except GenerationFailed:
        raise
    except Exception as error:
        log.exception("the text model failed")
        raise GenerationFailed(MODEL_ERROR) from error
    return drafts.parse_generated(raw, request.kind)


# ---- the physician's decisions ----


def accept(store: Store, case_id: int, encounter_id: int) -> EncounterReview:
    """Accept the pending proposal as a whole; refused while it is outdated."""
    with store.write() as tx:
        review = load(tx, case_id, encounter_id)
        if review.proposal is None:
            raise Refused(NO_PROPOSAL)
        if review.outdated:
            raise Refused(drafts.OUTDATED_REASON)
        merged = drafts.accept(review.draft, review.proposal)
        tx.accept_proposal(
            encounter_id,
            dump(drafts.draft_to_json(merged)),
            review.proposal.notes_revision,
            dump(drafts.clarifications_to_json(review.proposal.clarifications)),
        )
        return load(tx, case_id, encounter_id)


def discard(store: Store, case_id: int, encounter_id: int) -> EncounterReview:
    """Drop the pending proposal. Discarding when there is none changes nothing."""
    with store.write() as tx:
        load(tx, case_id, encounter_id)
        tx.clear_proposal(encounter_id)
        return load(tx, case_id, encounter_id)


def parse_section_text(raw: Mapping[str, Any]) -> str:
    """The text exactly as sent, like the notes."""
    text = raw.get("text")
    if not isinstance(text, str):
        raise cases.Invalid({"text": SECTION_NOT_TEXT})
    if len(text) > MAX_SECTION_LENGTH:
        raise cases.Invalid({"text": f"Höchstens {MAX_SECTION_LENGTH} Zeichen"})
    return text


def save_section(
    store: Store, case_id: int, encounter_id: int, number: int, raw: Mapping[str, Any]
) -> EncounterReview:
    """Replace one section of the current draft with the physician's own text.

    Saving the text that is stored already changes nothing, so a browser that never saw the
    answer can send the request again.
    """
    with store.write() as tx:
        review = load(tx, case_id, encounter_id)
        index = section_index(review, number)
        text = parse_section_text(raw)
        edited = drafts.edit_section(review.draft, review.encounter.kind, index, text)
        if edited is not review.draft:
            assert edited is not None
            tx.set_draft(encounter_id, dump(drafts.draft_to_json(edited)))
        return load(tx, case_id, encounter_id)


def mark_copied(store: Store, case_id: int, encounter_id: int, number: int) -> EncounterReview:
    """Record that a section of the current draft was copied."""
    with store.write() as tx:
        review = load(tx, case_id, encounter_id)
        index = section_index(review, number)
        if review.draft is None or drafts.is_empty(review.draft.sections[index]):
            raise Refused(NOTHING_TO_COPY)
        marked = drafts.mark_copied(review.draft, index)
        if marked != review.draft:
            tx.set_draft(encounter_id, dump(drafts.draft_to_json(marked)))
        return load(tx, case_id, encounter_id)


def dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)
