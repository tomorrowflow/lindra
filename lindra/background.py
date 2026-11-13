"""The background of a visit (ADR 0010), as pure functions.

A visit's draft may draw on what the physician accepted earlier in the case: the admission
assessment and the visits dated before this one. A later visit and a pending proposal are
never background, so a backdated visit reads as of its own date. The background revision is
the sum of the acceptance counters of those encounters; a draft or proposal bound to a
revision that no longer matches was generated from other background.

The assessment itself has no background.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Protocol

BACKGROUND_PREFIX = "encounter:"


class Dated(Protocol):
    id: int
    kind: str
    occurred_at: datetime
    acceptances: int


def background_of[E: Dated](target: Dated, encounters: Iterable[E]) -> list[E]:
    """The encounters a visit may draw on, earliest first: the admission assessment, wherever
    it lies, and every visit dated strictly earlier than this one. Whether an encounter has
    anything accepted to draw on is a question for `accepted`."""
    if target.kind != "visit":
        return []
    found = [
        e
        for e in encounters
        if e.id != target.id and (e.kind == "assessment" or e.occurred_at < target.occurred_at)
    ]
    return sorted(found, key=lambda e: (e.occurred_at, e.id))


def accepted[E: Dated](background: Iterable[E]) -> list[E]:
    """The background encounters whose draft was accepted at least once."""
    return [e for e in background if e.acceptances > 0]


def revision(target: Dated, encounters: Iterable[Dated]) -> int:
    """The background revision of a visit: how often its background was accepted."""
    return sum(e.acceptances for e in background_of(target, encounters))


def source_key(encounter_id: int) -> str:
    """The input-reference source that names a background encounter."""
    return f"{BACKGROUND_PREFIX}{encounter_id}"


def encounter_of(source: str) -> int | None:
    """The encounter a reference source names, or None for any other source."""
    if not source.startswith(BACKGROUND_PREFIX):
        return None
    number = source.removeprefix(BACKGROUND_PREFIX)
    return int(number) if number.isdigit() and number.isascii() else None
