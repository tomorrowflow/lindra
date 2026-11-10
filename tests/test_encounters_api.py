"""Encounters through the JSON API: visits in the treatment period and per-encounter notes.

The application's clock stands at 10.11.2026 14:30 (`tests/conftest.py`). The case below
runs from 9.11. to 20.11., so "now" lies inside its period; the fictional case
FIK-2026-002 ran in October, so "now" lies after its period.
"""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from lindra.app import create_app
from lindra.config import Settings
from tests.conftest import NOW, TOKEN
from tests.test_cases_api import create, seeded_case

VISIT = {"visit_date": "2026-11-12", "visit_time": "08:15"}


def make_case(client, **changes):
    return create(client, **changes).json()


def visit_path(case):
    return f"/api/cases/{case['id']}/visits"


def encounter_path(case, encounter):
    return f"/api/cases/{case['id']}/encounters/{encounter['id']}"


def add_visit(client, case, **changes):
    return client.post(visit_path(case), json={**VISIT, **changes})


def stamps(client, case):
    shown = client.get(f"/api/cases/{case['id']}").json()
    return [(e["kind"], e["occurred_at"]) for e in shown["encounters"]]


def assessment_of(client, case):
    shown = client.get(f"/api/cases/{case['id']}").json()
    return next(e for e in shown["encounters"] if e["kind"] == "assessment")


def save(client, case, encounter, notes):
    return client.put(f"{encounter_path(case, encounter)}/notes", json={"notes": notes})


# ---- the token guards every encounter route ----


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/cases/1/visits"),
        ("GET", "/api/cases/1/encounters/1"),
        ("PUT", "/api/cases/1/encounters/1/notes"),
    ],
)
def test_encounter_routes_refuse_requests_without_the_token(anonymous, method, path):
    response = anonymous.request(method, path)

    assert response.status_code == 401
    assert response.json() == {"detail": "Anmeldung erforderlich"}


# ---- the assessment and its visits ----


def test_a_case_has_exactly_one_assessment_dated_at_its_creation(api_client):
    case = make_case(api_client)

    assert [e["kind"] for e in case["encounters"]] == ["assessment"]
    assert case["encounters"][0]["occurred_at"] == "2026-11-09T10:30"
    assert case["encounters"][0]["label"] == "Aufnahmeassessment"


def test_a_visit_inside_the_period_is_created_with_its_date_and_time(api_client):
    case = make_case(api_client)

    response = add_visit(api_client, case)

    assert response.status_code == 201
    assert response.json()["kind"] == "visit"
    assert response.json()["label"] == "Visite"
    assert response.json()["occurred_at"] == "2026-11-12T08:15"
    assert stamps(api_client, case) == [
        ("assessment", "2026-11-09T10:30"),
        ("visit", "2026-11-12T08:15"),
    ]


def test_a_case_takes_any_number_of_visits_also_on_one_day(api_client):
    case = make_case(api_client)

    for hour in ("07:00", "13:00", "18:45"):
        assert add_visit(api_client, case, visit_time=hour).status_code == 201

    kinds = [kind for kind, _ in stamps(api_client, case)]
    assert kinds == ["assessment", "visit", "visit", "visit"]


def test_a_visit_may_lie_on_the_first_and_on_the_last_day_of_the_period(api_client):
    case = make_case(api_client)

    assert add_visit(api_client, case, visit_date="2026-11-09").status_code == 201
    assert add_visit(api_client, case, visit_date="2026-11-20").status_code == 201


@pytest.mark.parametrize("day", ["2026-11-08", "2026-11-21", "2025-11-12", "2026-12-12"])
def test_a_visit_outside_the_period_is_refused_and_nothing_is_added(api_client, day):
    case = make_case(api_client)

    response = add_visit(api_client, case, visit_date=day)

    assert response.status_code == 422
    assert response.json()["errors"] == {
        "visit_date": "Die Visite muss im Behandlungszeitraum 09.11.2026 bis 20.11.2026 liegen"
    }
    assert stamps(api_client, case) == [("assessment", "2026-11-09T10:30")]


def test_a_visit_before_now_but_inside_the_period_is_backdated_and_accepted(api_client):
    case = make_case(api_client)
    backdated = {"visit_date": "2026-11-09", "visit_time": "16:00"}
    assert backdated["visit_date"] < NOW.date().isoformat()

    response = add_visit(api_client, case, **backdated)

    assert response.status_code == 201
    assert response.json()["occurred_at"] == "2026-11-09T16:00"


def test_visits_are_listed_by_date_whatever_the_order_they_were_created_in(api_client):
    case = make_case(api_client)
    add_visit(api_client, case, visit_date="2026-11-18", visit_time="09:00")
    add_visit(api_client, case, visit_date="2026-11-10", visit_time="14:30")
    add_visit(api_client, case, visit_date="2026-11-14", visit_time="11:00")

    assert stamps(api_client, case) == [
        ("assessment", "2026-11-09T10:30"),
        ("visit", "2026-11-10T14:30"),
        ("visit", "2026-11-14T11:00"),
        ("visit", "2026-11-18T09:00"),
    ]


def test_a_backdated_visit_sorts_before_a_seeded_later_visit(api_client):
    cast_case = seeded_case(api_client, "FIK-2026-002")
    before = [(e["kind"], e["occurred_at"][:10]) for e in cast_case["encounters"]]
    assert before == [
        ("assessment", "2026-10-12"),
        ("visit", "2026-10-14"),
        ("visit", "2026-10-16"),
    ]

    response = add_visit(api_client, cast_case, visit_date="2026-10-13", visit_time="08:00")

    assert response.status_code == 201
    shown = api_client.get(f"/api/cases/{cast_case['id']}").json()
    assert [e["occurred_at"][:10] for e in shown["encounters"]] == [
        "2026-10-12",
        "2026-10-13",
        "2026-10-14",
        "2026-10-16",
    ]


def test_the_visit_date_and_time_are_required(api_client):
    case = make_case(api_client)

    response = api_client.post(visit_path(case), json={})

    assert response.status_code == 422
    assert response.json()["errors"] == {
        "visit_date": "Datum der Visite angeben",
        "visit_time": "Uhrzeit der Visite angeben",
    }


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("visit_date", "2026-02-30", "Kein gültiges Datum"),
        ("visit_date", "12.11.2026", "Kein gültiges Datum"),
        ("visit_time", "25:00", "Keine gültige Uhrzeit"),
        ("visit_time", "8:15", "Keine gültige Uhrzeit"),
    ],
)
def test_a_date_or_time_that_does_not_exist_is_refused(api_client, field, value, message):
    case = make_case(api_client)

    response = add_visit(api_client, case, **{field: value})

    assert response.status_code == 422
    assert response.json()["errors"] == {field: message}


def test_a_visit_for_an_unknown_case_is_not_found(api_client):
    response = api_client.post("/api/cases/999/visits", json=VISIT)

    assert response.status_code == 404
    assert response.json() == {"detail": "Fall nicht gefunden"}


def test_a_period_correction_names_a_visit_created_here(api_client):
    case = make_case(api_client)
    add_visit(api_client, case, visit_date="2026-11-18")

    response = api_client.put(
        f"/api/cases/{case['id']}/period",
        json={"period_start": "2026-11-09", "period_end": "2026-11-15"},
    )

    assert response.status_code == 409
    assert [c["kind"] for c in response.json()["conflicts"]] == ["visit"]


# ---- notes: one body per encounter, autosaved with a revision ----


def test_a_new_encounter_has_empty_notes_at_revision_zero(api_client):
    case = make_case(api_client)

    shown = api_client.get(encounter_path(case, assessment_of(api_client, case))).json()

    assert shown["notes"] == ""
    assert shown["notes_revision"] == 0


def test_a_saved_change_advances_the_notes_revision_by_one(api_client):
    case = make_case(api_client)
    encounter = assessment_of(api_client, case)

    first = save(api_client, case, encounter, "Seit drei Jahren Rückenschmerz.")
    second = save(api_client, case, encounter, "Seit drei Jahren Rückenschmerz, links betont.")

    assert first.status_code == 200
    assert first.json()["notes_revision"] == 1
    assert second.json()["notes_revision"] == 2
    assert second.json()["notes"] == "Seit drei Jahren Rückenschmerz, links betont."


def test_saved_notes_are_there_when_the_encounter_is_opened_again(api_client):
    case = make_case(api_client)
    encounter = assessment_of(api_client, case)
    save(api_client, case, encounter, "Notiz")

    shown = api_client.get(encounter_path(case, encounter)).json()

    assert shown["notes"] == "Notiz"
    assert shown["notes_revision"] == 1


def test_notes_are_kept_exactly_as_typed_or_pasted(api_client):
    case = make_case(api_client)
    encounter = assessment_of(api_client, case)
    typed = "  Zeile eins\r\n\r\n\tZeile zwei, mit Umlauten: ä ö ü ß  \n"

    save(api_client, case, encounter, typed)

    assert api_client.get(encounter_path(case, encounter)).json()["notes"] == typed


def test_emptying_the_notes_is_a_saved_change_too(api_client):
    case = make_case(api_client)
    encounter = assessment_of(api_client, case)
    save(api_client, case, encounter, "Notiz")

    emptied = save(api_client, case, encounter, "")

    assert emptied.json()["notes"] == ""
    assert emptied.json()["notes_revision"] == 2


def test_saving_the_same_text_again_does_not_advance_the_revision(api_client):
    case = make_case(api_client)
    encounter = assessment_of(api_client, case)
    save(api_client, case, encounter, "Notiz")

    again = save(api_client, case, encounter, "Notiz")

    assert again.status_code == 200
    assert again.json()["notes_revision"] == 1


def test_each_encounter_keeps_its_own_notes_and_revision(api_client):
    case = make_case(api_client)
    assessment = assessment_of(api_client, case)
    visit = add_visit(api_client, case).json()
    save(api_client, case, assessment, "Assessment-Notiz")
    save(api_client, case, assessment, "Assessment-Notiz, ergänzt")

    save(api_client, case, visit, "Visiten-Notiz")

    assert api_client.get(encounter_path(case, assessment)).json()["notes"] == (
        "Assessment-Notiz, ergänzt"
    )
    assert api_client.get(encounter_path(case, assessment)).json()["notes_revision"] == 2
    assert api_client.get(encounter_path(case, visit)).json()["notes"] == "Visiten-Notiz"
    assert api_client.get(encounter_path(case, visit)).json()["notes_revision"] == 1


def test_the_case_lists_the_notes_revision_of_each_encounter_without_the_text(api_client):
    case = make_case(api_client)
    save(api_client, case, assessment_of(api_client, case), "Notiz")

    listed = api_client.get(f"/api/cases/{case['id']}").json()["encounters"][0]

    assert listed["notes_revision"] == 1
    assert "notes" not in listed


def test_a_seeded_encounter_arrives_with_the_notes_of_the_cast(api_client):
    cast_case = seeded_case(api_client, "FIK-2026-001")
    first = cast_case["encounters"][0]

    shown = api_client.get(encounter_path(cast_case, first)).json()

    assert shown["notes"].strip()
    assert shown["notes_revision"] == 1


# ---- a failed save leaves the saved notes alone and can be retried ----


@pytest.mark.parametrize("body", [{}, {"notes": None}, {"notes": 5}, {"notes": ["a"]}])
def test_a_save_without_text_is_refused_and_the_saved_notes_stay(api_client, body):
    case = make_case(api_client)
    encounter = assessment_of(api_client, case)
    save(api_client, case, encounter, "Gespeicherte Notiz")

    response = api_client.put(f"{encounter_path(case, encounter)}/notes", json=body)

    assert response.status_code == 422
    assert response.json()["errors"] == {"notes": "Notizen als Text übermitteln"}
    shown = api_client.get(encounter_path(case, encounter)).json()
    assert shown["notes"] == "Gespeicherte Notiz"
    assert shown["notes_revision"] == 1


def test_notes_beyond_the_length_limit_are_refused_and_the_saved_notes_stay(api_client):
    case = make_case(api_client)
    encounter = assessment_of(api_client, case)
    save(api_client, case, encounter, "Gespeicherte Notiz")

    response = save(api_client, case, encounter, "x" * 100_001)

    assert response.status_code == 422
    assert response.json()["errors"] == {"notes": "Höchstens 100000 Zeichen"}
    assert api_client.get(encounter_path(case, encounter)).json()["notes"] == "Gespeicherte Notiz"


def test_a_refused_save_is_retried_with_the_same_text_once_it_can_be_saved(api_client):
    case = make_case(api_client)
    encounter = assessment_of(api_client, case)
    save(api_client, case, encounter, "Gespeicherte Notiz")
    refused = save(api_client, case, encounter, "x" * 100_001)
    assert refused.status_code == 422

    retried = save(api_client, case, encounter, "Gespeicherte Notiz, ergänzt")

    assert retried.status_code == 200
    assert retried.json()["notes"] == "Gespeicherte Notiz, ergänzt"
    assert retried.json()["notes_revision"] == 2


def test_a_retry_after_a_lost_answer_does_not_count_as_a_second_change(api_client):
    # The first request reached the service, its answer did not reach the browser. The
    # browser's retry carries the same text and finds it saved already.
    case = make_case(api_client)
    encounter = assessment_of(api_client, case)
    save(api_client, case, encounter, "Notiz nach dem Verbindungsabbruch")

    retried = save(api_client, case, encounter, "Notiz nach dem Verbindungsabbruch")

    assert retried.status_code == 200
    assert retried.json()["notes_revision"] == 1


def test_a_save_for_an_unknown_encounter_fails_and_names_it(api_client):
    case = make_case(api_client)

    response = api_client.put(f"/api/cases/{case['id']}/encounters/999/notes", json={"notes": "x"})

    assert response.status_code == 404
    assert response.json() == {"detail": "Kontakt nicht gefunden"}


def test_an_encounter_of_another_case_is_not_found_under_this_case(api_client):
    case = make_case(api_client)
    other = make_case(api_client, case_number="FIK-2026-101")
    foreign = assessment_of(api_client, other)

    saved = save(api_client, case, foreign, "Notiz")
    shown = api_client.get(encounter_path(case, foreign))

    assert saved.status_code == 404
    assert shown.status_code == 404
    assert api_client.get(encounter_path(other, foreign)).json()["notes"] == ""


def test_notes_of_an_unknown_case_are_not_found(api_client):
    response = api_client.put("/api/cases/999/encounters/1/notes", json={"notes": "x"})

    assert response.status_code == 404
    assert response.json() == {"detail": "Fall nicht gefunden"}


def test_deleting_a_case_deletes_its_notes_with_it(api_client):
    case = make_case(api_client)
    encounter = assessment_of(api_client, case)
    save(api_client, case, encounter, "Notiz")

    api_client.delete(f"/api/cases/{case['id']}")
    recreated = make_case(api_client)

    shown = api_client.get(encounter_path(recreated, assessment_of(api_client, recreated))).json()
    assert shown["notes"] == ""


def test_a_volume_from_before_the_notes_opens_with_empty_notes(tmp_path):
    legacy = sqlite3.connect(tmp_path / "lindra.db")
    legacy.executescript(
        """
        CREATE TABLE cases (
            id INTEGER PRIMARY KEY,
            case_number TEXT NOT NULL UNIQUE COLLATE NOCASE,
            patient_name TEXT NOT NULL,
            label TEXT NOT NULL DEFAULT '',
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL
        );
        CREATE TABLE encounters (
            id INTEGER PRIMARY KEY,
            case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            kind TEXT NOT NULL CHECK (kind IN ('assessment', 'visit')),
            occurred_at TEXT NOT NULL
        );
        INSERT INTO cases VALUES (1, 'FIK-2026-100', 'Marta', '', '2026-11-09', '2026-11-20');
        INSERT INTO encounters VALUES (1, 1, 'assessment', '2026-11-09T10:30');
        """
    )
    legacy.commit()
    legacy.close()
    client = TestClient(
        create_app(Settings(token=TOKEN, data_dir=tmp_path)),
        headers={"Authorization": f"Bearer {TOKEN}"},
    )

    opened = client.get("/api/cases/1/encounters/1").json()
    saved = client.put("/api/cases/1/encounters/1/notes", json={"notes": "Notiz"}).json()

    assert (opened["notes"], opened["notes_revision"]) == ("", 0)
    assert (saved["notes"], saved["notes_revision"]) == ("Notiz", 1)
