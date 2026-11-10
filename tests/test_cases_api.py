"""Cases and their treatment period through the JSON API (ADR 0002, ADR 0010).

The physician's pages call the same case operations; `tests/test_case_pages.py`
covers what she sees. Visits arrive with ticket 06, so the encounters a case has
beyond its assessment come from the seeded fictional cast.
"""

import pytest

from lindra import cast

NEW_CASE = {
    "case_number": "FIK-2026-100",
    "patient_name": "Marta Lindqvist",
    "label": "Kopfschmerz",
    "assessment_date": "2026-11-09",
    "assessment_time": "10:30",
    "period_start": "2026-11-09",
    "period_end": "2026-11-20",
}


def create(client, **changes):
    return client.post("/api/cases", json={**NEW_CASE, **changes})


def numbers(client):
    return [c["case_number"] for c in client.get("/api/cases").json()["cases"]]


def seeded_case(client, number):
    client.post("/api/seed")
    listed = client.get("/api/cases").json()["cases"]
    return next(c for c in listed if c["case_number"] == number)


# ---- the token guards every case route ----


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/cases"),
        ("POST", "/api/cases"),
        ("GET", "/api/cases/1"),
        ("PUT", "/api/cases/1/period"),
        ("DELETE", "/api/cases/1"),
    ],
)
def test_case_routes_refuse_requests_without_the_token(anonymous, method, path):
    response = anonymous.request(method, path)

    assert response.status_code == 401
    assert response.json() == {"detail": "Anmeldung erforderlich"}


def test_a_wrong_token_does_not_open_the_case_list(anonymous):
    response = anonymous.get("/api/cases", headers={"Authorization": "Bearer wrong"})

    assert response.status_code == 401


# ---- creating a case ----


def test_a_new_installation_has_no_cases(api_client):
    assert api_client.get("/api/cases").json() == {"cases": []}


def test_a_case_is_created_and_listed(api_client):
    response = create(api_client)

    assert response.status_code == 201
    created = response.json()
    assert created["case_number"] == "FIK-2026-100"
    assert created["patient_name"] == "Marta Lindqvist"
    assert created["label"] == "Kopfschmerz"
    assert created["period_start"] == "2026-11-09"
    assert created["period_end"] == "2026-11-20"
    assert numbers(api_client) == ["FIK-2026-100"]


def test_the_label_is_optional(api_client):
    response = create(api_client, label="")

    assert response.status_code == 201
    assert response.json()["label"] == ""


def test_a_created_case_has_its_admission_assessment_with_date_and_time(api_client):
    created = create(api_client).json()

    overview = api_client.get(f"/api/cases/{created['id']}").json()

    assert [e["kind"] for e in overview["encounters"]] == ["assessment"]
    assert overview["encounters"][0]["label"] == "Aufnahmeassessment"
    assert overview["encounters"][0]["occurred_at"] == "2026-11-09T10:30"


def test_the_period_may_be_a_single_day(api_client):
    response = create(api_client, period_start="2026-11-09", period_end="2026-11-09")

    assert response.status_code == 201


def test_the_assessment_may_lie_on_the_first_and_on_the_last_day(api_client):
    first = create(api_client, case_number="A-1", assessment_date="2026-11-09")
    last = create(api_client, case_number="A-2", assessment_date="2026-11-20")

    assert first.status_code == 201
    assert last.status_code == 201


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("case_number", "Fallnummer angeben"),
        ("patient_name", "Patientenname angeben"),
        ("assessment_date", "Datum des Assessments angeben"),
        ("assessment_time", "Uhrzeit des Assessments angeben"),
        ("period_start", "Behandlungsbeginn angeben"),
        ("period_end", "Behandlungsende angeben"),
    ],
)
def test_every_required_field_is_refused_when_missing_or_blank(api_client, field, message):
    for value in ("", "   "):
        response = create(api_client, **{field: value})

        assert response.status_code == 422
        assert response.json()["errors"] == {field: message}
    assert numbers(api_client) == []


def test_a_field_that_is_absent_counts_as_missing(api_client):
    body = {k: v for k, v in NEW_CASE.items() if k != "patient_name"}

    response = api_client.post("/api/cases", json=body)

    assert response.status_code == 422
    assert response.json()["errors"] == {"patient_name": "Patientenname angeben"}


def test_all_missing_fields_are_reported_together(api_client):
    response = api_client.post("/api/cases", json={})

    assert response.status_code == 422
    assert set(response.json()["errors"]) == {
        "case_number",
        "patient_name",
        "assessment_date",
        "assessment_time",
        "period_start",
        "period_end",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("assessment_date", "09.11.2026"),
        ("assessment_date", "2026-02-30"),
        ("assessment_time", "25:00"),
        ("assessment_time", "abends"),
        ("period_start", "morgen"),
        ("period_end", "2026-13-01"),
    ],
)
def test_a_date_or_time_that_does_not_exist_is_refused(api_client, field, value):
    response = create(api_client, **{field: value})

    assert response.status_code == 422
    assert field in response.json()["errors"]


@pytest.mark.parametrize(
    ("field", "limit"), [("case_number", 40), ("patient_name", 120), ("label", 80)]
)
def test_a_text_field_has_a_length_limit(api_client, field, limit):
    assert create(api_client, **{field: "x" * limit}).status_code == 201
    api_client.delete(f"/api/cases/{api_client.get('/api/cases').json()['cases'][0]['id']}")

    response = create(api_client, **{field: "x" * (limit + 1)})

    assert response.status_code == 422
    assert response.json()["errors"] == {field: f"Höchstens {limit} Zeichen"}


def test_an_end_before_the_start_is_refused(api_client):
    response = create(api_client, period_start="2026-11-20", period_end="2026-11-09")

    assert response.status_code == 422
    assert response.json()["errors"] == {
        "period_end": "Behandlungsende liegt vor Behandlungsbeginn"
    }
    assert numbers(api_client) == []


@pytest.mark.parametrize("date", ["2026-11-08", "2026-11-21"])
def test_an_assessment_outside_the_period_is_refused(api_client, date):
    response = create(api_client, assessment_date=date)

    assert response.status_code == 422
    assert response.json()["errors"] == {
        "assessment_date": "Das Assessment muss im Behandlungszeitraum liegen"
    }


def test_an_assessment_outside_a_reversed_period_reports_the_period_only(api_client):
    response = create(
        api_client, period_start="2026-11-20", period_end="2026-11-09", assessment_date="2026-11-25"
    )

    assert set(response.json()["errors"]) == {"period_end"}


def test_a_case_number_is_used_once_whatever_its_case(api_client):
    create(api_client)

    response = create(api_client, case_number="fik-2026-100", patient_name="Jemand anderes")

    assert response.status_code == 422
    assert response.json()["errors"] == {"case_number": "Diese Fallnummer gibt es schon"}
    assert numbers(api_client) == ["FIK-2026-100"]


def test_surrounding_blanks_are_not_kept(api_client):
    created = create(api_client, case_number="  FIK-7  ", patient_name=" Marta Lindqvist ").json()

    assert created["case_number"] == "FIK-7"
    assert created["patient_name"] == "Marta Lindqvist"


def test_cases_are_listed_by_case_number(api_client):
    create(api_client, case_number="FIK-2026-300")
    create(api_client, case_number="FIK-2026-200")

    assert numbers(api_client) == ["FIK-2026-200", "FIK-2026-300"]


# ---- the overview ----


def test_the_overview_shows_number_name_label_period_and_encounters(api_client):
    case = seeded_case(api_client, "FIK-2026-001")

    overview = api_client.get(f"/api/cases/{case['id']}").json()

    first = cast.load_cast().cases[0]
    assert overview["case_number"] == first.case_number
    assert overview["patient_name"] == first.patient_name
    assert overview["label"] == first.label
    assert overview["period_start"] == first.period_start.isoformat()
    assert overview["period_end"] == first.period_end.isoformat()
    kinds = [e["kind"] for e in overview["encounters"]]
    assert kinds.count("assessment") == 1
    assert kinds.count("visit") == len([e for e in first.encounters if e.kind == "visit"])
    assert overview["encounters"][0]["kind"] == "assessment"
    assert [e["occurred_at"] for e in overview["encounters"]] == sorted(
        e["occurred_at"] for e in overview["encounters"]
    )


def test_an_unknown_case_is_not_found(api_client):
    response = api_client.get("/api/cases/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Fall nicht gefunden"}


# ---- correcting the period ----


def test_a_period_that_keeps_every_encounter_is_saved_and_listed(api_client):
    created = create(api_client).json()

    response = api_client.put(
        f"/api/cases/{created['id']}/period",
        json={"period_start": "2026-11-05", "period_end": "2026-11-30"},
    )

    assert response.status_code == 200
    assert response.json()["period_start"] == "2026-11-05"
    listed = api_client.get("/api/cases").json()["cases"][0]
    assert (listed["period_start"], listed["period_end"]) == ("2026-11-05", "2026-11-30")


def test_a_period_that_would_strand_the_assessment_is_refused_and_names_it(api_client):
    created = create(api_client).json()

    response = api_client.put(
        f"/api/cases/{created['id']}/period",
        json={"period_start": "2026-11-10", "period_end": "2026-11-20"},
    )

    assert response.status_code == 409
    body = response.json()
    assert [(c["label"], c["occurred_at"]) for c in body["conflicts"]] == [
        ("Aufnahmeassessment", "2026-11-09T10:30")
    ]
    after = api_client.get(f"/api/cases/{created['id']}").json()
    assert (after["period_start"], after["period_end"]) == ("2026-11-09", "2026-11-20")


def test_a_period_that_would_strand_visits_names_each_with_its_date(api_client):
    case = seeded_case(api_client, "FIK-2026-001")
    before = api_client.get(f"/api/cases/{case['id']}").json()
    visits = [e for e in before["encounters"] if e["kind"] == "visit"]
    last_visit_day = max(v["occurred_at"][:10] for v in visits)

    response = api_client.put(
        f"/api/cases/{case['id']}/period",
        json={"period_start": before["period_start"], "period_end": "2026-10-05"},
    )

    assert response.status_code == 409
    named = response.json()["conflicts"]
    assert {c["id"] for c in named} == {v["id"] for v in visits}
    assert all(c["label"] == "Visite" for c in named)
    assert max(c["occurred_at"][:10] for c in named) == last_visit_day
    assert api_client.get(f"/api/cases/{case['id']}").json() == before


def test_a_refused_change_leaves_every_encounter_where_it_was(api_client):
    case = seeded_case(api_client, "FIK-2026-002")
    before = api_client.get(f"/api/cases/{case['id']}").json()

    api_client.put(
        f"/api/cases/{case['id']}/period",
        json={"period_start": "2026-10-20", "period_end": "2026-10-21"},
    )

    assert api_client.get(f"/api/cases/{case['id']}").json() == before


def test_a_period_with_the_end_before_the_start_is_refused(api_client):
    created = create(api_client).json()

    response = api_client.put(
        f"/api/cases/{created['id']}/period",
        json={"period_start": "2026-11-20", "period_end": "2026-11-09"},
    )

    assert response.status_code == 422
    assert "period_end" in response.json()["errors"]


def test_a_period_with_a_missing_date_is_refused(api_client):
    created = create(api_client).json()

    response = api_client.put(
        f"/api/cases/{created['id']}/period", json={"period_start": "2026-11-09"}
    )

    assert response.status_code == 422
    assert response.json()["errors"] == {"period_end": "Behandlungsende angeben"}


def test_correcting_the_period_of_an_unknown_case_is_not_found(api_client):
    response = api_client.put(
        "/api/cases/999/period", json={"period_start": "2026-11-09", "period_end": "2026-11-20"}
    )

    assert response.status_code == 404


# ---- deleting a case ----


def test_deleting_a_case_removes_it_and_nothing_else(api_client):
    api_client.post("/api/seed")
    listed = api_client.get("/api/cases").json()["cases"]
    doomed, *others = listed
    kept = {c["case_number"]: api_client.get(f"/api/cases/{c['id']}").json() for c in others}

    response = api_client.delete(f"/api/cases/{doomed['id']}")

    assert response.status_code == 204
    assert api_client.get(f"/api/cases/{doomed['id']}").status_code == 404
    assert numbers(api_client) == sorted(kept)
    for case in api_client.get("/api/cases").json()["cases"]:
        assert api_client.get(f"/api/cases/{case['id']}").json() == kept[case["case_number"]]


def test_deleting_an_unknown_case_is_not_found(api_client):
    assert api_client.delete("/api/cases/999").status_code == 404


def test_a_number_can_be_used_again_after_its_case_is_deleted(api_client):
    created = create(api_client).json()
    api_client.delete(f"/api/cases/{created['id']}")

    assert create(api_client).status_code == 201


# ---- the seed hook fills case storage (ADR 0007) ----


def test_seeding_stores_the_three_fictional_cases(api_client):
    report = api_client.post("/api/seed").json()

    assert report["stored"] is True
    assert numbers(api_client) == sorted(c.case_number for c in cast.load_cast().cases)


def test_a_seeded_case_has_the_assessment_and_the_visits_of_the_cast(api_client):
    case = seeded_case(api_client, "FIK-2026-002")

    overview = api_client.get(f"/api/cases/{case['id']}").json()

    expected = [e for e in cast.load_cast().cases[1].encounters]
    assert [e["occurred_at"][:10] for e in overview["encounters"]] == sorted(
        e.date.isoformat() for e in expected
    )


def test_seeding_twice_leaves_one_copy_of_each_case(api_client):
    api_client.post("/api/seed")
    first = api_client.get("/api/cases").json()

    api_client.post("/api/seed")

    assert len(numbers(api_client)) == 3
    assert [c["case_number"] for c in api_client.get("/api/cases").json()["cases"]] == [
        c["case_number"] for c in first["cases"]
    ]


def test_seeding_restores_a_fictional_case_the_physician_deleted(api_client):
    case = seeded_case(api_client, "FIK-2026-003")
    api_client.delete(f"/api/cases/{case['id']}")
    assert "FIK-2026-003" not in numbers(api_client)

    api_client.post("/api/seed")

    assert "FIK-2026-003" in numbers(api_client)


def test_seeding_puts_a_corrected_period_back_to_the_cast(api_client):
    case = seeded_case(api_client, "FIK-2026-001")
    api_client.put(
        f"/api/cases/{case['id']}/period",
        json={"period_start": "2026-09-01", "period_end": "2026-12-31"},
    )

    api_client.post("/api/seed")

    listed = next(
        c
        for c in api_client.get("/api/cases").json()["cases"]
        if c["case_number"] == "FIK-2026-001"
    )
    assert listed["period_start"] == "2026-10-05"


def test_seeding_keeps_the_cases_the_physician_created(api_client):
    create(api_client)

    api_client.post("/api/seed")

    assert "FIK-2026-100" in numbers(api_client)
    assert len(numbers(api_client)) == 4


def test_the_environment_report_needs_the_cases_to_be_present(api_client):
    case = seeded_case(api_client, "FIK-2026-001")
    assert api_client.get("/api/environment").json()["seed"]["ran"] is True

    api_client.delete(f"/api/cases/{case['id']}")

    assert api_client.get("/api/environment").json()["seed"] == {"ran": False}


def test_the_seed_report_names_the_stored_cases(api_client):
    report = api_client.post("/api/seed").json()

    assert report["totals"]["cases"] == 3
    assert api_client.get("/api/environment").json()["seed"]["stored"] is True


def test_cases_survive_a_restart_on_the_same_volume(tmp_path):
    from fastapi.testclient import TestClient

    from lindra.app import create_app
    from lindra.config import Settings
    from tests.conftest import TOKEN

    headers = {"Authorization": f"Bearer {TOKEN}"}
    first = TestClient(create_app(Settings(token=TOKEN, data_dir=tmp_path)), headers=headers)
    first.post("/api/cases", json=NEW_CASE)

    restarted = TestClient(create_app(Settings(token=TOKEN, data_dir=tmp_path)), headers=headers)

    assert numbers(restarted) == ["FIK-2026-100"]
