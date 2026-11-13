"""The JSON routes for an encounter's draft, proposal and handover. The token guard in
`lindra/auth.py` covers `/api/`."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Response
from fastapi.responses import JSONResponse

from lindra import cases, drafts, review
from lindra.store import Store
from lindra.textmodel import GenerationFailed, TextModel

RawBody = Annotated[dict[str, Any] | None, Body()]


def section_json(
    number: int, section: drafts.Section, current: review.EncounterReview
) -> dict[str, Any]:
    """A section as the API shows it. Each paragraph says where it comes from: `notes` when it
    has input references into today's notes, `background` when they quote an earlier encounter,
    `notes_and_background` for both, `hand` when the physician wrote it. A reference into an
    earlier encounter names it and its date."""
    stored = drafts.section_to_json(section)
    for paragraph in stored["paragraphs"]:
        paragraph["origin"] = drafts.origin_of([r["source"] for r in paragraph["references"]])
        for reference in paragraph["references"]:
            earlier = drafts.InputReference(reference["source"], reference["quote"])
            reference["origin"] = "notes" if earlier.encounter_id is None else "background"
            reference["encounter"] = (
                None
                if earlier.encounter_id is None
                else {"id": earlier.encounter_id, "label": current.source_label(earlier.source)}
            )
    return {
        "number": number,
        "text": drafts.section_text(section),
        "empty": drafts.is_empty(section),
        **stored,
    }


def proposal_json(current: review.EncounterReview) -> dict[str, Any] | None:
    proposal = current.proposal
    if proposal is None:
        return None
    plan = current.plan
    assert plan is not None
    encounter = current.encounter
    return {
        "notes_revision": proposal.notes_revision,
        "background_revision": proposal.background_revision,
        "outdated": current.outdated,
        "outdated_reason": current.outdated_reason if current.outdated else None,
        "notes_outdated": encounter.proposal_notes_outdated,
        "background_outdated": encounter.proposal_background_outdated,
        "sections": [section_json(i + 1, s, current) for i, s in enumerate(proposal.sections)],
        "clarifications": drafts.clarifications_to_json(proposal.clarifications),
        "replaces": list(plan.replaced),
        "retains": list(plan.retained),
    }


def review_json(
    current: review.EncounterReview, generation: review.GenerationState
) -> dict[str, Any]:
    encounter = current.encounter
    return {
        "has_draft": encounter.has_draft,
        "draft_revision": encounter.draft_revision,
        "notes_revision": encounter.notes_revision,
        "possibly_outdated": current.possibly_outdated,
        "background_revision": encounter.background_revision,
        "draft_background": encounter.draft_background,
        "background_changed": current.background_changed,
        "background_changed_label": drafts.BACKGROUND_CHANGED
        if current.background_changed
        else None,
        "acceptances": encounter.acceptances,
        "sections": [section_json(i + 1, s, current) for i, s in enumerate(current.sections)],
        "clarifications": drafts.clarifications_to_json(current.clarifications),
        "proposal": proposal_json(current),
        "generation": {"state": generation.state, "reason": generation.reason},
    }


def handover_json(current: review.EncounterReview) -> dict[str, Any]:
    """What the handover copies: the current draft, never the pending proposal."""
    sections = []
    if current.draft is not None:
        for number, section in enumerate(current.draft.sections, start=1):
            sections.append(
                {
                    "number": number,
                    "title": section.title,
                    "text": drafts.section_text(section),
                    "empty": drafts.is_empty(section),
                    "copied": section.copied,
                }
            )
    return {"has_draft": current.draft is not None, "sections": sections}


def build_router(store: Store, model: TextModel, generations: review.Generations) -> APIRouter:
    router = APIRouter(prefix="/api/cases/{case_id}/encounters/{encounter_id}")

    def answer(current: review.EncounterReview) -> Response:
        return JSONResponse(review_json(current, generations.state(current.encounter.id)))

    def refused(error: review.Refused) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=409)

    def not_found(error: cases.NotFound) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=404)

    @router.get("/draft")
    def get_draft(case_id: int, encounter_id: int) -> Response:
        try:
            return answer(review.open_review(store, case_id, encounter_id))
        except cases.NotFound as error:
            return not_found(error)

    @router.get("/generation")
    def get_generation(case_id: int, encounter_id: int) -> Response:
        try:
            review.open_review(store, case_id, encounter_id)
        except cases.NotFound as error:
            return not_found(error)
        state = generations.state(encounter_id)
        return JSONResponse({"state": state.state, "reason": state.reason})

    @router.post("/generate")
    def generate(case_id: int, encounter_id: int) -> Response:
        try:
            current = review.generate(store, model, generations, case_id, encounter_id)
        except cases.NotFound as error:
            return not_found(error)
        except review.Refused as error:
            return refused(error)
        except GenerationFailed as error:
            return JSONResponse({"detail": error.reason}, status_code=502)
        return answer(current)

    @router.post("/proposal/accept")
    def accept(case_id: int, encounter_id: int) -> Response:
        try:
            return answer(review.accept(store, case_id, encounter_id))
        except cases.NotFound as error:
            return not_found(error)
        except review.Refused as error:
            return refused(error)

    @router.delete("/proposal")
    def discard(case_id: int, encounter_id: int) -> Response:
        try:
            return answer(review.discard(store, case_id, encounter_id))
        except cases.NotFound as error:
            return not_found(error)

    @router.put("/draft/sections/{number}")
    def save_section(case_id: int, encounter_id: int, number: int, raw: RawBody) -> Response:
        try:
            current = review.save_section(store, case_id, encounter_id, number, raw or {})
            return answer(current)
        except cases.NotFound as error:
            return not_found(error)
        except cases.Invalid as error:
            return JSONResponse(
                {"detail": "Die Angaben sind nicht gültig", "errors": error.errors},
                status_code=422,
            )

    @router.post("/draft/sections/{number}/copied")
    def mark_copied(case_id: int, encounter_id: int, number: int) -> Response:
        try:
            current = review.mark_copied(store, case_id, encounter_id, number)
            return answer(current)
        except cases.NotFound as error:
            return not_found(error)
        except review.Refused as error:
            return refused(error)

    @router.get("/handover")
    def handover(case_id: int, encounter_id: int) -> Response:
        try:
            current = review.open_review(store, case_id, encounter_id)
        except cases.NotFound as error:
            return not_found(error)
        return JSONResponse(handover_json(current))

    return router
