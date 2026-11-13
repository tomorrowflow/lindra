"""The review steps of an encounter: one step per section, then Übernehmen or Übergabe (ADR 0008).

The steps are server-rendered pages. Accepting and discarding are plain form posts that
redirect back; generating, editing and copying are small scripts that call the JSON API
(`lindra/review_api.py`) so the physician can keep reading and writing meanwhile.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from lindra import badges, cases, review
from lindra.store import Case, Store

FINAL_STEP = "abschluss"


@dataclass(frozen=True)
class Step:
    number: int
    label: str
    url: str
    badges: tuple[badges.Badge, ...] = ()


def encounter_base(case: Case, encounter_id: int) -> str:
    return f"/faelle/{case.id}/kontakte/{encounter_id}"


def build_steps(case: Case, current: review.EncounterReview) -> list[Step]:
    """The steps of an encounter in order: notes, one per section, then the final step."""
    base = encounter_base(case, current.encounter.id)
    steps = [Step(1, "Notizen", f"{base}/notizen")]
    for index, title in enumerate(current.titles):
        found = tuple(badges.section_badges(current, index))
        steps.append(Step(index + 2, title, f"{base}/abschnitte/{index + 1}", found))
    final = "Übernehmen" if current.proposal else "Übergabe"
    steps.append(Step(len(steps) + 1, final, f"{base}/{FINAL_STEP}"))
    return steps


def step_context(
    case: Case,
    current: review.EncounterReview,
    generations: review.Generations,
    active: int,
) -> dict[str, Any]:
    """What every step of an encounter needs: the sidebar steps, the neighbours of the active
    step and what the generation is doing. `active` is the step number."""
    steps = build_steps(case, current)
    return {
        "encounter": current.encounter,
        "selected_encounter_id": current.encounter.id,
        "rev": current,
        "steps": steps,
        "active": active,
        "previous_step": steps[active - 2] if active > 1 else None,
        "next_step": steps[active] if active < len(steps) else None,
        "generation": generations.state(current.encounter.id),
    }


def build_router(
    store: Store, templates: Jinja2Templates, generations: review.Generations
) -> APIRouter:
    router = APIRouter()

    def render(
        request: Request,
        template: str,
        case: Case,
        current: review.EncounterReview,
        active: int,
        *,
        status_code: int = 200,
        **context: Any,
    ) -> Response:
        return templates.TemplateResponse(
            request,
            template,
            {
                "cases": cases.list_cases(store),
                "case": case,
                "selected_id": case.id,
                **step_context(case, current, generations, active),
                **context,
            },
            status_code=status_code,
        )

    def missing(request: Request, case_id: int, error: cases.NotFound) -> Response:
        """The case overview with the reason, or the start screen when the case is gone."""
        listed = cases.list_cases(store)
        try:
            case = cases.get_case(store, case_id)
        except cases.NotFound:
            context = {"cases": listed, "case": None, "selected_id": None, "notice": str(error)}
            return templates.TemplateResponse(request, "start.html", context, status_code=404)
        context = {"cases": listed, "case": case, "selected_id": case.id, "notice": str(error)}
        return templates.TemplateResponse(request, "case.html", context, status_code=404)

    def open_step(request: Request, case_id: int, encounter_id: int):
        """The case and the encounter's review, or the response that says why not."""
        try:
            case = cases.get_case(store, case_id)
            return case, review.open_review(store, case_id, encounter_id)
        except cases.NotFound as error:
            return missing(request, case_id, error)

    @router.get("/faelle/{case_id}/kontakte/{encounter_id}/abschnitte/{number}")
    def section_step(request: Request, case_id: int, encounter_id: int, number: int) -> Response:
        opened = open_step(request, case_id, encounter_id)
        if isinstance(opened, Response):
            return opened
        case, current = opened
        try:
            index = review.section_index(current, number)
        except cases.NotFound as error:
            return missing(request, case_id, error)
        return render(request, "section.html", case, current, number + 1, index=index)

    @router.get("/faelle/{case_id}/kontakte/{encounter_id}/abschnitte/{number}/kopf")
    def section_head(request: Request, case_id: int, encounter_id: int, number: int) -> Response:
        """The title badges and state line of a section, which the page refreshes after a
        hand edit without reloading."""
        opened = open_step(request, case_id, encounter_id)
        if isinstance(opened, Response):
            return opened
        case, current = opened
        try:
            index = review.section_index(current, number)
        except cases.NotFound as error:
            return Response(str(error), status_code=404)
        context = {"rev": current, "index": index, "case": case, "encounter": current.encounter}
        return templates.TemplateResponse(request, "section_head.html", context)

    @router.get("/faelle/{case_id}/kontakte/{encounter_id}/abschnitte/{number}/herkunft")
    def section_origins(request: Request, case_id: int, encounter_id: int, number: int) -> Response:
        """Where each paragraph of the current draft comes from, which the page refreshes after
        a hand edit so a rewritten paragraph loses its reference without a reload."""
        opened = open_step(request, case_id, encounter_id)
        if isinstance(opened, Response):
            return opened
        _, current = opened
        try:
            index = review.section_index(current, number)
        except cases.NotFound as error:
            return Response(str(error), status_code=404)
        return templates.TemplateResponse(
            request, "section_origins.html", {"rev": current, "index": index}
        )

    @router.get("/faelle/{case_id}/kontakte/{encounter_id}/" + FINAL_STEP)
    def final_step(request: Request, case_id: int, encounter_id: int) -> Response:
        opened = open_step(request, case_id, encounter_id)
        if isinstance(opened, Response):
            return opened
        case, current = opened
        return render(request, "final.html", case, current, len(build_steps(case, current)))

    @router.post("/faelle/{case_id}/kontakte/{encounter_id}/" + FINAL_STEP + "/uebernehmen")
    def accept(request: Request, case_id: int, encounter_id: int) -> Response:
        opened = open_step(request, case_id, encounter_id)
        if isinstance(opened, Response):
            return opened
        case, _ = opened
        try:
            review.accept(store, case_id, encounter_id)
        except review.Refused as error:
            current = review.open_review(store, case_id, encounter_id)
            active = len(build_steps(case, current))
            return render(
                request, "final.html", case, current, active, status_code=409, notice=str(error)
            )
        return RedirectResponse(f"{encounter_base(case, encounter_id)}/{FINAL_STEP}", 303)

    @router.post("/faelle/{case_id}/kontakte/{encounter_id}/" + FINAL_STEP + "/verwerfen")
    def discard(
        request: Request,
        case_id: int,
        encounter_id: int,
        back: Annotated[str, Form()] = "",
    ) -> Response:
        opened = open_step(request, case_id, encounter_id)
        if isinstance(opened, Response):
            return opened
        case, _ = opened
        review.discard(store, case_id, encounter_id)
        base = encounter_base(case, encounter_id)
        # Back to the step the physician came from, but only within this encounter.
        target = back if back.startswith(f"{base}/") else f"{base}/notizen"
        return RedirectResponse(target, 303)

    return router
