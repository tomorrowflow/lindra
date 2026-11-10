"""Period conflict detection (ADR 0010): a pure function, tested without HTTP.

The HTTP behaviour built on it (refusal with the conflicting encounters named) is in
`tests/test_cases_api.py`.
"""

from dataclasses import dataclass
from datetime import date, datetime

from lindra import periods


@dataclass(frozen=True)
class Encounter:
    name: str
    occurred_at: datetime


ASSESSMENT = Encounter("Aufnahmeassessment", datetime(2026, 10, 5, 9, 0))
FIRST_VISIT = Encounter("Visite 1", datetime(2026, 10, 9, 14, 30))
LAST_VISIT = Encounter("Visite 2", datetime(2026, 10, 16, 8, 0))
ENCOUNTERS = [LAST_VISIT, ASSESSMENT, FIRST_VISIT]


def test_a_period_around_every_encounter_has_no_conflict():
    assert periods.conflicting(date(2026, 10, 1), date(2026, 10, 31), ENCOUNTERS) == []


def test_both_ends_of_the_period_are_inclusive():
    assert periods.conflicting(date(2026, 10, 5), date(2026, 10, 16), ENCOUNTERS) == []


def test_an_encounter_before_the_new_start_conflicts():
    assert periods.conflicting(date(2026, 10, 6), date(2026, 10, 31), ENCOUNTERS) == [ASSESSMENT]


def test_an_encounter_after_the_new_end_conflicts():
    assert periods.conflicting(date(2026, 10, 1), date(2026, 10, 15), ENCOUNTERS) == [LAST_VISIT]


def test_every_stranded_encounter_is_named_in_date_order():
    stranded = periods.conflicting(date(2026, 10, 7), date(2026, 10, 12), ENCOUNTERS)

    assert stranded == [ASSESSMENT, LAST_VISIT]


def test_the_time_of_day_never_moves_an_encounter_out_of_its_day():
    late = Encounter("Visite spät", datetime(2026, 10, 16, 23, 59))

    assert periods.conflicting(date(2026, 10, 16), date(2026, 10, 16), [late]) == []


def test_a_one_day_period_is_valid_and_an_end_before_the_start_is_not():
    assert periods.order_problem(date(2026, 10, 5), date(2026, 10, 5)) is None
    assert periods.order_problem(date(2026, 10, 6), date(2026, 10, 5)) is not None
