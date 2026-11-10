"""The treatment period rules of ADR 0010, as pure functions.

A period is inclusive at both ends and counts whole days: the time of day of an
encounter never moves it out of its day.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from typing import Protocol


class Dated(Protocol):
    occurred_at: datetime


def order_problem(start: date, end: date) -> str | None:
    """Why the period is not valid, or None."""
    if end < start:
        return "Behandlungsende liegt vor Behandlungsbeginn"
    return None


def contains(start: date, end: date, day: date) -> bool:
    return start <= day <= end


def default_visit_at(now: datetime, start: date, end: date) -> datetime | None:
    """Where a new visit starts out: now, to the minute, when now lies in the period.

    Outside the period there is no default, so the physician never accepts a date
    that was only a guess.
    """
    if not contains(start, end, now.date()):
        return None
    return now.replace(second=0, microsecond=0)


def conflicting[E: Dated](start: date, end: date, encounters: Iterable[E]) -> list[E]:
    """The encounters outside the period, earliest first."""
    outside = (e for e in encounters if not contains(start, end, e.occurred_at.date()))
    return sorted(outside, key=lambda e: e.occurred_at)
