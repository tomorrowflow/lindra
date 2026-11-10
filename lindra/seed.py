"""The seed hook `scripts/env.py reset` calls (ADR 0007).

It seeds the fictional cast and nothing else. Until case storage exists
(ticket 05) it validates the cast and reports it without storing it; the report
goes to a marker file on the data volume so `check` can confirm the hook ran,
also after a restart. Ticket 05 stores the cases at the marked place in `run`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from lindra import cast

REPORT_FILE = "seed-report.json"


class InvalidCast(RuntimeError):
    """The cast breaks a rule of ADR 0006 or ADR 0010; nothing is seeded."""


def run(data_dir: Path) -> dict[str, Any]:
    """Validate the cast, record the report and return it. Safe to repeat."""
    fictional = cast.load_cast()
    problems = cast.validate_cast(fictional)
    if problems:
        raise InvalidCast("; ".join(problems))
    # Ticket 05 replaces the cast in case storage here. Until then nothing is stored.
    report = build_report(fictional)
    write_report(data_dir, report)
    return report


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
        "stored": False,
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


def read_report(data_dir: Path) -> dict[str, Any]:
    """The last report, or `{"ran": False}` when the hook has not run on this volume.

    A report of an older cast counts as not run, so a redeploy that changed the cast
    makes `up` seed again and `check` fail until it does.
    """
    try:
        report = json.loads((data_dir / REPORT_FILE).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"ran": False}
    if report.get("digest") != cast.cast_digest(cast.load_cast()):
        return {"ran": False}
    return report
