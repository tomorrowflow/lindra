"""Case storage: one SQLite file on the data volume (ADR 0005).

Every request opens its own short connection. Writes run in one immediate
transaction, so a check and the change that depends on it cannot be separated.
Deleting a case removes its encounters with it; nothing else is touched.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path

from lindra import background

DATABASE_FILE = "lindra.db"
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M"

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY,
    case_number TEXT NOT NULL UNIQUE COLLATE NOCASE,
    patient_name TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS encounters (
    id INTEGER PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('assessment', 'visit')),
    occurred_at TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    notes_revision INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS one_assessment_per_case
    ON encounters (case_id) WHERE kind = 'assessment';
-- The dictations already appended to an encounter's notes, so a repeated accept adds nothing.
CREATE TABLE IF NOT EXISTS accepted_dictations (
    encounter_id INTEGER NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    dictation_id TEXT NOT NULL,
    PRIMARY KEY (encounter_id, dictation_id)
);
"""

# Columns added after the first release of the schema; a volume created before
# them gets them when the service starts. (name, definition)
ADDED_COLUMNS = (
    ("notes", "TEXT NOT NULL DEFAULT ''"),
    ("notes_revision", "INTEGER NOT NULL DEFAULT 0"),
    # The accepted draft as JSON; empty until a proposal is accepted or a section is written.
    ("draft", "TEXT NOT NULL DEFAULT ''"),
    # The notes revision the draft was last accepted at; null while only written by hand.
    ("draft_revision", "INTEGER"),
    # The pending proposal as JSON, bound to the notes revision it was generated from.
    ("proposal", "TEXT NOT NULL DEFAULT ''"),
    ("proposal_revision", "INTEGER"),
    # The encounter's clarification list as JSON, adopted from a proposal on acceptance.
    ("clarifications", "TEXT NOT NULL DEFAULT '[]'"),
    ("acceptances", "INTEGER NOT NULL DEFAULT 0"),
    # The background revision of a visit when its draft was accepted and when its pending
    # proposal was generated (ADR 0010); null for the assessment, which has no background,
    # and while a visit's draft was only written by hand.
    ("draft_background", "INTEGER"),
    ("proposal_background", "INTEGER"),
)
# What a case listing reads of an encounter: everything but the notes and the draft texts,
# which can be long and belong to the one encounter being opened.
ENCOUNTER_COLUMNS = (
    "id, kind, occurred_at, notes_revision,"
    " trim(notes, ' ' || char(9) || char(10) || char(13)) != '' AS has_notes,"
    " draft != '' AS has_draft, draft_revision, proposal_revision, acceptances,"
    " draft_background, proposal_background"
)


class DuplicateCaseNumber(Exception):
    """The case number is already used by another case."""


@dataclass(frozen=True)
class Encounter:
    id: int
    kind: str
    occurred_at: datetime
    notes_revision: int = 0
    has_notes: bool = False
    has_draft: bool = False
    draft_revision: int | None = None
    proposal_revision: int | None = None
    acceptances: int = 0
    draft_background: int | None = None
    proposal_background: int | None = None
    # What the background of a visit is now: the acceptances of the assessment and of the visits
    # dated earlier. Always 0 for the assessment.
    background_revision: int = 0

    @property
    def has_proposal(self) -> bool:
        return self.proposal_revision is not None

    @property
    def proposal_notes_outdated(self) -> bool:
        """The pending proposal was generated from notes that have changed since (ADR 0008)."""
        return self.has_proposal and self.proposal_revision != self.notes_revision

    @property
    def proposal_background_outdated(self) -> bool:
        """The pending proposal was generated from a background that was accepted again since
        (ADR 0010)."""
        return (
            self.has_proposal
            and self.proposal_background is not None
            and self.proposal_background != self.background_revision
        )

    @property
    def proposal_outdated(self) -> bool:
        return self.proposal_notes_outdated or self.proposal_background_outdated

    @property
    def background_changed(self) -> bool:
        """The draft was accepted at another background revision than the current one. Its text
        stays; only an explicit regeneration uses the new background."""
        return (
            self.draft_background is not None and self.draft_background != self.background_revision
        )

    @property
    def draft_possibly_outdated(self) -> bool:
        """The notes moved past the revision the draft was last accepted at. A draft that was
        only written by hand has no revision and is never marked."""
        return self.draft_revision is not None and self.draft_revision < self.notes_revision


@dataclass(frozen=True)
class Review:
    """What an encounter holds of its draft, as the JSON text it is stored as."""

    draft: str = ""
    proposal: str = ""
    clarifications: str = "[]"


@dataclass(frozen=True)
class OpenedEncounter:
    encounter: Encounter
    notes: str
    review: Review = Review()


@dataclass(frozen=True)
class AcceptedDraft:
    """An encounter that was accepted at least once, with its current draft as stored."""

    encounter: Encounter
    draft: str


@dataclass(frozen=True)
class Case:
    id: int
    case_number: str
    patient_name: str
    label: str
    period_start: date
    period_end: date
    encounters: tuple[Encounter, ...] = ()


class Tx:
    """The operations of one transaction."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def list_cases(self) -> list[Case]:
        """Every case with its encounters, ordered by case number."""
        rows = self.connection.execute("SELECT * FROM cases ORDER BY case_number")
        return [self.with_encounters(row) for row in rows.fetchall()]

    def get_case(self, case_id: int) -> Case | None:
        row = self.connection.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        return self.with_encounters(row) if row else None

    def encounters_of(self, case_id: int) -> tuple[Encounter, ...]:
        """The case's encounters by date, each with the background revision it has now."""
        found = self.connection.execute(
            f"SELECT {ENCOUNTER_COLUMNS} FROM encounters WHERE case_id = ?"
            " ORDER BY occurred_at, id",
            (case_id,),
        )
        encounters = [encounter_from(e) for e in found]
        return tuple(
            replace(e, background_revision=background.revision(e, encounters)) for e in encounters
        )

    def with_encounters(self, row: sqlite3.Row) -> Case:
        return Case(
            id=row["id"],
            case_number=row["case_number"],
            patient_name=row["patient_name"],
            label=row["label"],
            period_start=date.fromisoformat(row["period_start"]),
            period_end=date.fromisoformat(row["period_end"]),
            encounters=self.encounters_of(row["id"]),
        )

    def add_case(
        self, case_number: str, patient_name: str, label: str, start: date, end: date
    ) -> int:
        try:
            cursor = self.connection.execute(
                "INSERT INTO cases (case_number, patient_name, label, period_start, period_end)"
                " VALUES (?, ?, ?, ?, ?)",
                (case_number, patient_name, label, start.isoformat(), end.isoformat()),
            )
        except sqlite3.IntegrityError as error:
            raise DuplicateCaseNumber(case_number) from error
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    def add_encounter(self, case_id: int, kind: str, occurred_at: datetime) -> int:
        cursor = self.connection.execute(
            "INSERT INTO encounters (case_id, kind, occurred_at) VALUES (?, ?, ?)",
            (case_id, kind, occurred_at.strftime(TIMESTAMP_FORMAT)),
        )
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    def get_encounter(self, case_id: int, encounter_id: int) -> OpenedEncounter | None:
        """One encounter of this case with its notes; None when the case has no such encounter."""
        row = self.connection.execute(
            f"SELECT {ENCOUNTER_COLUMNS}, notes, draft, proposal, clarifications"
            " FROM encounters WHERE id = ? AND case_id = ?",
            (encounter_id, case_id),
        ).fetchone()
        if row is None:
            return None
        review = Review(row["draft"], row["proposal"], row["clarifications"])
        encounter = next(e for e in self.encounters_of(case_id) if e.id == encounter_id)
        return OpenedEncounter(encounter, row["notes"], review)

    def accepted_background(self, case_id: int, encounter_id: int) -> list[AcceptedDraft]:
        """The drafts a visit may draw on: of the encounters in its background that were
        accepted at least once, earliest first, as the JSON text they are stored as."""
        encounters = self.encounters_of(case_id)
        target = next(e for e in encounters if e.id == encounter_id)
        found = []
        for earlier in background.accepted(background.background_of(target, encounters)):
            row = self.connection.execute(
                "SELECT draft FROM encounters WHERE id = ?", (earlier.id,)
            ).fetchone()
            found.append(AcceptedDraft(earlier, row["draft"]))
        return found

    def set_notes(self, case_id: int, encounter_id: int, notes: str) -> None:
        """Save the notes; the revision advances only when the text changed."""
        self.connection.execute(
            "UPDATE encounters SET notes = ?, notes_revision = notes_revision + 1"
            " WHERE id = ? AND case_id = ? AND notes != ?",
            (notes, encounter_id, case_id, notes),
        )

    def record_dictation(self, encounter_id: int, dictation_id: str) -> bool:
        """Remember that this dictation is appended to the encounter's notes. False when it was
        remembered before, which means the append happened already."""
        cursor = self.connection.execute(
            "INSERT OR IGNORE INTO accepted_dictations (encounter_id, dictation_id) VALUES (?, ?)",
            (encounter_id, dictation_id),
        )
        return cursor.rowcount == 1

    def set_proposal(
        self,
        encounter_id: int,
        proposal: str,
        notes_revision: int,
        background_revision: int | None = None,
    ) -> None:
        """Hold a proposal next to the draft; a pending one is replaced."""
        self.connection.execute(
            "UPDATE encounters SET proposal = ?, proposal_revision = ?, proposal_background = ?"
            " WHERE id = ?",
            (proposal, notes_revision, background_revision, encounter_id),
        )

    def clear_proposal(self, encounter_id: int) -> None:
        self.connection.execute(
            "UPDATE encounters SET proposal = '', proposal_revision = NULL,"
            " proposal_background = NULL WHERE id = ?",
            (encounter_id,),
        )

    def set_draft(self, encounter_id: int, draft: str) -> None:
        """Store the draft after a hand edit; it keeps the revision it was accepted at."""
        self.connection.execute(
            "UPDATE encounters SET draft = ? WHERE id = ?",
            (draft, encounter_id),
        )

    def accept_proposal(
        self,
        encounter_id: int,
        draft: str,
        notes_revision: int,
        clarifications: str,
        background_revision: int | None = None,
    ) -> None:
        """One step: the merged draft and the proposal's clarification list replace the
        current ones, the proposal is gone and the acceptance counter advances. The draft is
        now accepted at the proposal's notes and background revisions."""
        self.connection.execute(
            "UPDATE encounters SET draft = ?, draft_revision = ?, draft_background = ?,"
            " clarifications = ?, proposal = '', proposal_revision = NULL,"
            " proposal_background = NULL, acceptances = acceptances + 1 WHERE id = ?",
            (draft, notes_revision, background_revision, clarifications, encounter_id),
        )

    def set_period(self, case_id: int, start: date, end: date) -> None:
        self.connection.execute(
            "UPDATE cases SET period_start = ?, period_end = ? WHERE id = ?",
            (start.isoformat(), end.isoformat(), case_id),
        )

    def delete_case(self, case_id: int) -> bool:
        cursor = self.connection.execute("DELETE FROM cases WHERE id = ?", (case_id,))
        return cursor.rowcount > 0

    def delete_case_number(self, case_number: str) -> None:
        self.connection.execute("DELETE FROM cases WHERE case_number = ?", (case_number,))

    def has_case_numbers(self, case_numbers: list[str]) -> bool:
        found = {
            row["case_number"].lower()
            for row in self.connection.execute("SELECT case_number FROM cases")
        }
        return all(number.lower() in found for number in case_numbers)


def encounter_from(row: sqlite3.Row) -> Encounter:
    return Encounter(
        row["id"],
        row["kind"],
        datetime.strptime(row["occurred_at"], TIMESTAMP_FORMAT),
        row["notes_revision"],
        bool(row["has_notes"]),
        bool(row["has_draft"]),
        row["draft_revision"],
        row["proposal_revision"],
        row["acceptances"],
        row["draft_background"],
        row["proposal_background"],
    )


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = self.connect()
        try:
            connection.executescript(SCHEMA)
            present = {row["name"] for row in connection.execute("PRAGMA table_info(encounters)")}
            for name, definition in ADDED_COLUMNS:
                if name not in present:
                    connection.execute(f"ALTER TABLE encounters ADD COLUMN {name} {definition}")
        finally:
            connection.close()

    def connect(self) -> sqlite3.Connection:
        # Autocommit mode: `write` opens its transaction explicitly.
        connection = sqlite3.connect(self.path, isolation_level=None, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def read(self) -> Iterator[Tx]:
        connection = self.connect()
        try:
            yield Tx(connection)
        finally:
            connection.close()

    @contextmanager
    def write(self) -> Iterator[Tx]:
        """One transaction: committed when the block ends, rolled back when it raises."""
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield Tx(connection)
            except BaseException:
                connection.execute("ROLLBACK")
                raise
            connection.execute("COMMIT")
        finally:
            connection.close()
