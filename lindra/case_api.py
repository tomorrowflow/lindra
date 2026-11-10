"""The JSON routes for cases. The token guard in `lindra/auth.py` covers `/api/`."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Response
from fastapi.responses import JSONResponse

from lindra import badges, cases, drafts
from lindra.store import TIMESTAMP_FORMAT, Case, Encounter, OpenedEncounter, Store


def encounter_json(encounter: Encounter) -> dict[str, Any]:
    if not encounter.has_proposal:
        proposal = "none"
    elif encounter.proposal_revision == encounter.notes_revision:
        proposal = "pending"
    else:
        proposal = "outdated"
    return {
        "id": encounter.id,
        "kind": encounter.kind,
        "label": cases.ENCOUNTER_LABELS[encounter.kind],
        "occurred_at": encounter.occurred_at.strftime(TIMESTAMP_FORMAT),
        "notes_revision": encounter.notes_revision,
        "has_draft": encounter.has_draft,
        "proposal": proposal,
        "possibly_outdated": drafts.draft_possibly_outdated(
            encounter.draft_revision, encounter.notes_revision
        ),
        "acceptances": encounter.acceptances,
    }


def opened_json(opened: OpenedEncounter) -> dict[str, Any]:
    """The encounter with its notes and the badge the sidebar shows for it now."""
    state = badges.encounter_state(opened.encounter)
    badge = badges.STATES[state]
    return {
        **encounter_json(opened.encounter),
        "notes": opened.notes,
        "badge": {
            "state": state,
            "icon": badge.icon,
            "label": badge.label,
            "explanation": badge.explanation,
        },
    }


def case_json(case: Case) -> dict[str, Any]:
    return {
        "id": case.id,
        "case_number": case.case_number,
        "patient_name": case.patient_name,
        "label": case.label,
        "period_start": case.period_start.isoformat(),
        "period_end": case.period_end.isoformat(),
        "encounters": [encounter_json(e) for e in case.encounters],
    }


# A request without a body counts as an empty one, so the missing fields are named.
RawBody = Annotated[dict[str, Any] | None, Body()]


def invalid(error: cases.Invalid) -> JSONResponse:
    return JSONResponse(
        {"detail": "Die Angaben sind nicht gültig", "errors": error.errors}, status_code=422
    )


def not_found(error: cases.NotFound) -> JSONResponse:
    return JSONResponse({"detail": str(error)}, status_code=404)


def conflict(error: cases.PeriodConflict) -> JSONResponse:
    return JSONResponse(
        {
            "detail": "Der Zeitraum würde Kontakte ausschließen",
            "conflicts": [encounter_json(e) for e in error.conflicts],
        },
        status_code=409,
    )


def build_router(store: Store) -> APIRouter:
    router = APIRouter(prefix="/api/cases")

    @router.get("")
    def list_cases() -> dict[str, Any]:
        return {"cases": [case_json(c) for c in cases.list_cases(store)]}

    @router.post("")
    def create_case(raw: RawBody) -> Response:
        try:
            created = cases.create_case(store, raw or {})
            return JSONResponse(case_json(created), status_code=201)
        except cases.Invalid as error:
            return invalid(error)

    @router.get("/{case_id}")
    def get_case(case_id: int) -> Response:
        try:
            return JSONResponse(case_json(cases.get_case(store, case_id)))
        except cases.NotFound as error:
            return not_found(error)

    @router.put("/{case_id}/period")
    def change_period(case_id: int, raw: RawBody) -> Response:
        try:
            changed = cases.change_period(store, case_id, raw or {})
            return JSONResponse(case_json(changed))
        except cases.NotFound as error:
            return not_found(error)
        except cases.Invalid as error:
            return invalid(error)
        except cases.PeriodConflict as error:
            return conflict(error)

    @router.post("/{case_id}/visits")
    def create_visit(case_id: int, raw: RawBody) -> Response:
        try:
            visit = cases.create_visit(store, case_id, raw or {})
            return JSONResponse(encounter_json(visit), status_code=201)
        except cases.NotFound as error:
            return not_found(error)
        except cases.Invalid as error:
            return invalid(error)

    @router.get("/{case_id}/encounters/{encounter_id}")
    def get_encounter(case_id: int, encounter_id: int) -> Response:
        try:
            return JSONResponse(opened_json(cases.get_encounter(store, case_id, encounter_id)))
        except cases.NotFound as error:
            return not_found(error)

    @router.put("/{case_id}/encounters/{encounter_id}/notes")
    def save_notes(case_id: int, encounter_id: int, raw: RawBody) -> Response:
        try:
            saved = cases.save_notes(store, case_id, encounter_id, raw or {})
            return JSONResponse(opened_json(saved))
        except cases.NotFound as error:
            return not_found(error)
        except cases.Invalid as error:
            return invalid(error)

    @router.delete("/{case_id}")
    def delete_case(case_id: int) -> Response:
        try:
            cases.delete_case(store, case_id)
        except cases.NotFound as error:
            return not_found(error)
        return Response(status_code=204)

    return router
