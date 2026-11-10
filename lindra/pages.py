"""The case pages: start screen, overview, and the three dialogs (ADR 0008).

Each dialog is a page of its own: the route renders the screen behind it with the
dialog open, so the browser's back button, a reload and a refused form all behave
without client state. The token guard in `lindra/auth.py` covers every route here.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from lindra import cases
from lindra.store import Case, Store


class PeriodForm(BaseModel):
    """Every field defaults to blank, so the case operations name what is missing."""

    period_start: str = ""
    period_end: str = ""


class NewCaseForm(PeriodForm):
    case_number: str = ""
    patient_name: str = ""
    label: str = ""
    assessment_date: str = ""
    assessment_time: str = ""


NewCaseBody = Annotated[NewCaseForm, Form()]
PeriodBody = Annotated[PeriodForm, Form()]


def build_router(store: Store, templates: Jinja2Templates) -> APIRouter:
    router = APIRouter()

    def page(
        request: Request,
        template: str,
        *,
        status_code: int = 200,
        case: Case | None = None,
        **context: Any,
    ) -> Response:
        listed = cases.list_cases(store)
        return templates.TemplateResponse(
            request,
            template,
            {"cases": listed, "case": case, "selected_id": case.id if case else None, **context},
            status_code=status_code,
        )

    def not_found(request: Request, error: cases.NotFound) -> Response:
        return page(request, "start.html", status_code=404, notice=str(error))

    def with_case(request: Request, case_id: int, template: str, **context: Any) -> Response:
        try:
            case = cases.get_case(store, case_id)
        except cases.NotFound as error:
            return not_found(request, error)
        return page(request, template, case=case, **context)

    @router.get("/")
    def start(request: Request) -> Response:
        return page(request, "start.html")

    @router.get("/faelle/neu")
    def new_case_form(request: Request) -> Response:
        return page(request, "start.html", dialog="new_case", form={}, errors={})

    @router.post("/faelle/neu")
    def create_case(request: Request, body: NewCaseBody) -> Response:
        form = body.model_dump()
        try:
            created = cases.create_case(store, form)
        except cases.Invalid as error:
            return page(
                request,
                "start.html",
                status_code=422,
                dialog="new_case",
                form=form,
                errors=error.errors,
            )
        return RedirectResponse(f"/faelle/{created.id}", status_code=303)

    @router.get("/faelle/{case_id}")
    def overview(request: Request, case_id: int) -> Response:
        return with_case(request, case_id, "case.html")

    @router.get("/faelle/{case_id}/zeitraum")
    def period_form(request: Request, case_id: int) -> Response:
        try:
            case = cases.get_case(store, case_id)
        except cases.NotFound as error:
            return not_found(request, error)
        form = {
            "period_start": case.period_start.isoformat(),
            "period_end": case.period_end.isoformat(),
        }
        return page(
            request, "case.html", case=case, dialog="period", form=form, errors={}, conflicts=[]
        )

    @router.post("/faelle/{case_id}/zeitraum")
    def change_period(request: Request, case_id: int, body: PeriodBody) -> Response:
        form = body.model_dump()
        dialog = {"dialog": "period", "form": form}
        try:
            cases.change_period(store, case_id, form)
        except cases.NotFound as error:
            return not_found(request, error)
        except cases.Invalid as error:
            return with_case(
                request,
                case_id,
                "case.html",
                status_code=422,
                errors=error.errors,
                conflicts=[],
                **dialog,
            )
        except cases.PeriodConflict as error:
            return with_case(
                request,
                case_id,
                "case.html",
                status_code=409,
                errors={},
                conflicts=error.conflicts,
                **dialog,
            )
        return RedirectResponse(f"/faelle/{case_id}", status_code=303)

    @router.get("/faelle/{case_id}/zeitraum/pruefen")
    def check_period(
        request: Request, case_id: int, period_start: str = "", period_end: str = ""
    ) -> Response:
        """The feedback region of the period dialog, refreshed while the dates are edited."""
        raw = {"period_start": period_start, "period_end": period_end}
        try:
            check = cases.check_period(store, case_id, raw)
        except cases.NotFound as error:
            return Response(str(error), status_code=404)
        return templates.TemplateResponse(
            request, "period_feedback.html", {"errors": check.errors, "conflicts": check.conflicts}
        )

    @router.get("/faelle/{case_id}/loeschen")
    def delete_form(request: Request, case_id: int) -> Response:
        return with_case(request, case_id, "case.html", dialog="delete")

    @router.post("/faelle/{case_id}/loeschen")
    def delete_case(request: Request, case_id: int) -> Response:
        try:
            cases.delete_case(store, case_id)
        except cases.NotFound as error:
            return not_found(request, error)
        return RedirectResponse("/", status_code=303)

    return router
