"""German dates for the pages: 05.10.2026, 05.10.2026 09:00, 05.10.2026 bis 16.10.2026."""

from __future__ import annotations

from datetime import date, datetime


def german_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def german_datetime(value: datetime) -> str:
    return value.strftime("%d.%m.%Y %H:%M")


def german_period(start: date, end: date) -> str:
    return f"{german_date(start)} bis {german_date(end)}"
