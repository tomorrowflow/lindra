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


def conflicting[E: Dated](start: date, end: date, encounters: Iterable[E]) -> list[E]:
    """The encounters outside the period, earliest first."""
    outside = (e for e in encounters if not start <= e.occurred_at.date() <= end)
    return sorted(outside, key=lambda e: e.occurred_at)
