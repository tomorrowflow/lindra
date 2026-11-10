"""The case operations the pages and the JSON API share (ADR 0010).

Input arrives as raw strings from a form or a JSON body. It is checked once here,
at the boundary; the store and the periods module receive typed values.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any

from lindra import periods
from lindra.store import Case, DuplicateCaseNumber, Encounter, Store

ASSESSMENT = "assessment"
VISIT = "visit"
ENCOUNTER_LABELS = {ASSESSMENT: "Aufnahmeassessment", VISIT: "Visite"}

MAX_LENGTHS = {"case_number": 40, "patient_name": 120, "label": 80}

MISSING = {
    "case_number": "Fallnummer angeben",
    "patient_name": "Patientenname angeben",
    "assessment_date": "Datum des Assessments angeben",
    "assessment_time": "Uhrzeit des Assessments angeben",
    "period_start": "Behandlungsbeginn angeben",
    "period_end": "Behandlungsende angeben",
}
INVALID_DATE = "Kein gültiges Datum"
INVALID_TIME = "Keine gültige Uhrzeit"
ASSESSMENT_OUTSIDE = "Das Assessment muss im Behandlungszeitraum liegen"
DUPLICATE_NUMBER = "Diese Fallnummer gibt es schon"
NOT_FOUND = "Fall nicht gefunden"

DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
TIME_PATTERN = re.compile(r"\d{2}:\d{2}")


class Invalid(Exception):
    """The input breaks a rule. `errors` maps a field name to its message."""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__(errors)
        self.errors = errors


class NotFound(Exception):
    """No case has this id."""


class PeriodConflict(Exception):
    """The new period would leave these encounters outside."""

    def __init__(self, conflicts: list[Encounter]) -> None:
        super().__init__(conflicts)
        self.conflicts = conflicts


@dataclass(frozen=True)
class NewCase:
    case_number: str
    patient_name: str
    label: str
    assessment_at: datetime
    period_start: date
    period_end: date


@dataclass(frozen=True)
class PeriodCheck:
    errors: dict[str, str]
    conflicts: list[Encounter]

    @property
    def ok(self) -> bool:
        return not self.errors and not self.conflicts


def text(raw: Mapping[str, Any], field: str) -> str:
    value = raw.get(field)
    return value.strip() if isinstance(value, str) else ""


def parse_date(value: str) -> date | None:
    if not DATE_PATTERN.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def parse_time(value: str) -> time | None:
    if not TIME_PATTERN.fullmatch(value):
        return None
    try:
        return time.fromisoformat(value)
    except ValueError:
        return None


def read_date(raw: Mapping[str, Any], field: str, errors: dict[str, str]) -> date | None:
    value = text(raw, field)
    if not value:
        errors[field] = MISSING[field]
        return None
    parsed = parse_date(value)
    if parsed is None:
        errors[field] = INVALID_DATE
    return parsed


def read_period(raw: Mapping[str, Any], errors: dict[str, str]) -> tuple[date, date] | None:
    start = read_date(raw, "period_start", errors)
    end = read_date(raw, "period_end", errors)
    if start is None or end is None:
        return None
    problem = periods.order_problem(start, end)
    if problem:
        errors["period_end"] = problem
        return None
    return start, end


def parse_new_case(raw: Mapping[str, Any]) -> NewCase:
    errors: dict[str, str] = {}
    values = {field: text(raw, field) for field in MAX_LENGTHS}
    for field in ("case_number", "patient_name"):
        if not values[field]:
            errors[field] = MISSING[field]
    for field, limit in MAX_LENGTHS.items():
        if len(values[field]) > limit:
            errors[field] = f"Höchstens {limit} Zeichen"

    period = read_period(raw, errors)
    assessment_day = read_date(raw, "assessment_date", errors)
    assessment_time = None
    time_text = text(raw, "assessment_time")
    if not time_text:
        errors["assessment_time"] = MISSING["assessment_time"]
    else:
        assessment_time = parse_time(time_text)
        if assessment_time is None:
            errors["assessment_time"] = INVALID_TIME
    if period and assessment_day and not period[0] <= assessment_day <= period[1]:
        errors["assessment_date"] = ASSESSMENT_OUTSIDE

    if errors or period is None or assessment_day is None or assessment_time is None:
        raise Invalid(errors)
    return NewCase(
        case_number=values["case_number"],
        patient_name=values["patient_name"],
        label=values["label"],
        assessment_at=datetime.combine(assessment_day, assessment_time),
        period_start=period[0],
        period_end=period[1],
    )


def create_case(store: Store, raw: Mapping[str, Any]) -> Case:
    new = parse_new_case(raw)
    with store.write() as tx:
        try:
            case_id = tx.add_case(
                new.case_number, new.patient_name, new.label, new.period_start, new.period_end
            )
        except DuplicateCaseNumber as error:
            raise Invalid({"case_number": DUPLICATE_NUMBER}) from error
        tx.add_encounter(case_id, ASSESSMENT, new.assessment_at)
        case = tx.get_case(case_id)
    assert case is not None
    return case


def list_cases(store: Store) -> list[Case]:
    with store.read() as tx:
        return tx.list_cases()


def get_case(store: Store, case_id: int) -> Case:
    with store.read() as tx:
        case = tx.get_case(case_id)
    if case is None:
        raise NotFound(NOT_FOUND)
    return case


def check_period(store: Store, case_id: int, raw: Mapping[str, Any]) -> PeriodCheck:
    """What a period change would run into, without changing anything."""
    case = get_case(store, case_id)
    errors: dict[str, str] = {}
    period = read_period(raw, errors)
    if period is None:
        return PeriodCheck(errors, [])
    return PeriodCheck({}, periods.conflicting(*period, case.encounters))


def change_period(store: Store, case_id: int, raw: Mapping[str, Any]) -> Case:
    """Correct the period; refused, with nothing changed, when an encounter would fall outside."""
    errors: dict[str, str] = {}
    period = read_period(raw, errors)
    if period is None:
        # An unknown case answers before bad input does.
        get_case(store, case_id)
        raise Invalid(errors)
    with store.write() as tx:
        case = tx.get_case(case_id)
        if case is None:
            raise NotFound(NOT_FOUND)
        conflicts = periods.conflicting(*period, case.encounters)
        if conflicts:
            raise PeriodConflict(conflicts)
        tx.set_period(case_id, *period)
        changed = tx.get_case(case_id)
    assert changed is not None
    return changed


def delete_case(store: Store, case_id: int) -> None:
    with store.write() as tx:
        if not tx.delete_case(case_id):
            raise NotFound(NOT_FOUND)
