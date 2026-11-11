"""The seed hook `scripts/env.py reset` calls (ADR 0007).

It seeds the fictional cast and nothing else. It validates the cast, then
replaces the cast's cases in case storage: each fictional case is deleted by its
case number and stored again with its assessment and visits and their notes (each
at notes revision 1, as if saved once). Cases the physician
created under other numbers stay. The report goes to a marker file on the data
volume so `check` can confirm the hook ran, also after a restart, and counts
only while every cast case is still in storage.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, time
from pathlib import Path
from typing import Any

from lindra import background, cast, drafts, review, standins
from lindra.store import Store, Tx

REPORT_FILE = "seed-report.json"
# The cast gives each encounter a date; the seeded encounters happen at this time.
SEEDED_TIME = time(9, 0)


class InvalidCast(RuntimeError):
    """The cast breaks a rule of ADR 0006 or ADR 0010; nothing is seeded."""


def run(store: Store, data_dir: Path) -> dict[str, Any]:
    """Validate the cast, store its cases, record the report and return it. Safe to repeat."""
    fictional = cast.load_cast()
    problems = cast.validate_cast(fictional)
    if problems:
        raise InvalidCast("; ".join(problems))
    store_cast(store, fictional)
    report = build_report(fictional)
    write_report(data_dir, report)
    return report


def store_cast(store: Store, fictional: cast.Cast) -> None:
    """Replace the cast's cases in one transaction: all of them or none.

    A case whose timeline has a change of background (`cast.changed_background`) is stored as
    that timeline left it, through the same operations the physician uses, so its visit shows
    "Hintergrund seit Erstellung geändert". The other cases come as notes only: the physician
    generates their drafts herself, and the evaluation measures that."""
    with store.write() as tx:
        for case in fictional.cases:
            tx.delete_case_number(case.case_number)
            case_id = tx.add_case(
                case.case_number,
                case.patient_name,
                case.label,
                case.period_start,
                case.period_end,
            )
            ids: dict[str, int] = {}
            for encounter in case.encounters:
                encounter_id = tx.add_encounter(
                    case_id, encounter.kind, datetime.combine(encounter.date, SEEDED_TIME)
                )
                tx.set_notes(case_id, encounter_id, encounter.notes)
                ids[encounter.key] = encounter_id
            if cast.changed_background(case):
                replay_timeline(tx, case_id, case, ids)


def replay_timeline(tx: Tx, case_id: int, case: cast.Case, ids: dict[str, int]) -> None:
    """Apply the case's timeline in order: a "generate" holds the encounter's expected draft
    as its proposal, an "accept" accepts the pending proposal (generating it first when the
    timeline names none, as for the assessment)."""
    by_key = {e.key: e for e in case.encounters}
    keys = {encounter_id: key for key, encounter_id in ids.items()}
    for what, key in case.timeline:
        encounter_id = ids[key]
        if what == "generate" or tx.get_encounter(case_id, encounter_id).review.proposal == "":
            hold_expected(tx, case_id, by_key[key], encounter_id, keys)
        if what == "accept":
            review.accept_in(tx, case_id, encounter_id)


def hold_expected(
    tx: Tx, case_id: int, encounter: cast.Encounter, encounter_id: int, keys: dict[int, str]
) -> None:
    """Hold the draft the fixture model returns for this encounter as its proposal. The
    background it draws on is what was accepted in the case by now."""
    earlier = {
        keys[accepted.encounter.id]: background.source_key(accepted.encounter.id)
        for accepted in tx.accepted_background(case_id, encounter_id)
    }
    generated = drafts.parse_generated(standins.expected_result(encounter, earlier), encounter.kind)
    current = tx.get_encounter(case_id, encounter_id).encounter
    proposal = drafts.Proposal(
        current.notes_revision,
        generated.sections,
        generated.clarifications,
        current.background_revision if encounter.kind == "visit" else None,
    )
    review.hold(tx, case_id, encounter_id, proposal)


def build_report(fictional: cast.Cast) -> dict[str, Any]:
    cases = []
    for case in fictional.cases:
        visits = [e for e in case.encounters if e.kind == "visit"]
        cases.append(
            {
                "case_number": case.case_number,
                "patient_name": case.patient_name,
                "period": {
                    "start": case.period_start.isoformat(),
                    "end": case.period_end.isoformat(),
                },
                "encounters": len(case.encounters),
                "visits": len(visits),
                "backdated_visits": sum(1 for v in visits if v.date < v.entered_on),
                "changed_background": list(cast.changed_background(case)),
                "clarification_items": sum(len(e.clarifications) for e in case.encounters),
                "audio": sum(len(e.audio) for e in case.encounters),
            }
        )
    return {
        "ran": True,
        "stored": True,
        "digest": cast.cast_digest(fictional),
        "cases": cases,
        "totals": {
            "cases": len(cases),
            "encounters": sum(c["encounters"] for c in cases),
            "visits": sum(c["visits"] for c in cases),
            "backdated_visits": sum(c["backdated_visits"] for c in cases),
            "changed_background": sum(len(c["changed_background"]) for c in cases),
            "clarification_items": sum(c["clarification_items"] for c in cases),
            "audio": sum(c["audio"] for c in cases),
        },
    }


def write_report(data_dir: Path, report: dict[str, Any]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / REPORT_FILE
    scratch = data_dir / f"{REPORT_FILE}.tmp"
    scratch.write_text(json.dumps(report, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    os.replace(scratch, target)


def read_report(store: Store, data_dir: Path) -> dict[str, Any]:
    """The last report, or `{"ran": False}` when the cast is not seeded on this volume.

    A report of an older cast counts as not run, so a redeploy that changed the cast
    makes `up` seed again and `check` fail until it does. So does a cast case that is
    no longer in storage, for example one the physician deleted.
    """
    try:
        report = json.loads((data_dir / REPORT_FILE).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"ran": False}
    fictional = cast.load_cast()
    if report.get("digest") != cast.cast_digest(fictional):
        return {"ran": False}
    with store.read() as tx:
        if not tx.has_case_numbers([case.case_number for case in fictional.cases]):
            return {"ran": False}
    return report
