"""The seeded cast carries the changed-background state (ADR 0010, ADR 0007).

One case of the cast has an assessment change accepted after a visit's draft: after `reset`
that visit shows "Hintergrund seit Erstellung geändert". The other cases come as notes only, so
the physician can generate from nothing. Everything is read through the HTTP API.
"""

from lindra import cast


def seeded(api_client):
    api_client.post("/api/seed")
    shown = {}
    for case in api_client.get("/api/cases").json()["cases"]:
        shown[case["case_number"]] = case
    return shown


def by_date(case):
    return {e["occurred_at"][:10]: e for e in case["encounters"]}


def test_the_visit_before_the_assessment_change_shows_the_changed_background(api_client):
    encounters = by_date(seeded(api_client)["FIK-2026-002"])

    visit = encounters["2026-10-16"]
    assert visit["background_changed"] is True
    assert visit["has_draft"] is True
    assert visit["acceptances"] == 1
    assert encounters["2026-10-12"]["background_changed"] is False


def test_the_assessment_of_that_case_was_accepted_twice_and_holds_its_draft(api_client):
    case = seeded(api_client)["FIK-2026-002"]
    assessment = by_date(case)["2026-10-12"]

    assert assessment["acceptances"] == 2
    assert assessment["has_draft"] is True
    assert assessment["proposal"] == "none"
    shown = api_client.get(f"/api/cases/{case['id']}/encounters/{assessment['id']}/draft").json()
    assert shown["sections"][3]["text"].startswith("Migräne")


def test_the_seeded_visit_keeps_its_text_and_its_historical_reference(api_client):
    case = seeded(api_client)["FIK-2026-002"]
    visit = by_date(case)["2026-10-16"]
    assessment = by_date(case)["2026-10-12"]

    shown = api_client.get(f"/api/cases/{case['id']}/encounters/{visit['id']}/draft").json()

    assert shown["background_changed"] is True
    assert shown["background_changed_label"] == "Hintergrund seit Erstellung geändert"
    assert shown["draft_background"] == 1 and shown["background_revision"] == 2
    first = shown["sections"][0]
    assert "Sumatriptan wirksam" in first["text"]
    history = first["paragraphs"][1]
    assert history["origin"] == "background"
    assert history["references"][0]["encounter"] == {
        "id": assessment["id"],
        "label": "Aufnahmeassessment, 12.10.2026 09:00",
    }
    assert shown["proposal"] is None


def test_the_backdated_visit_of_that_case_holds_a_pending_proposal_it_can_accept(api_client):
    case = seeded(api_client)["FIK-2026-002"]
    backdated = by_date(case)["2026-10-14"]

    assert backdated["proposal"] == "pending"
    assert backdated["has_draft"] is False
    base = f"/api/cases/{case['id']}/encounters/{backdated['id']}"
    proposal = api_client.get(f"{base}/draft").json()["proposal"]
    assert proposal["outdated"] is False and proposal["background_revision"] == 2
    assert api_client.post(f"{base}/proposal/accept").status_code == 200


def test_the_other_cases_come_as_notes_only(api_client):
    shown = seeded(api_client)

    for number in ("FIK-2026-001", "FIK-2026-003"):
        for encounter in shown[number]["encounters"]:
            assert encounter["has_draft"] is False
            assert encounter["proposal"] == "none"
            assert encounter["acceptances"] == 0
            assert encounter["background_changed"] is False


def test_the_seed_report_names_the_visits_that_show_the_changed_background(api_client):
    report = api_client.post("/api/seed").json()
    shown = seeded(api_client)

    for case in report["cases"]:
        changed = [e for e in shown[case["case_number"]]["encounters"] if e["background_changed"]]
        assert len(changed) == len(case["changed_background"])
    assert report["totals"]["changed_background"] == 1


def test_seeding_again_converges_to_the_same_state(api_client):
    first = seeded(api_client)["FIK-2026-002"]
    api_client.post("/api/seed")
    second = next(
        c
        for c in api_client.get("/api/cases").json()["cases"]
        if c["case_number"] == "FIK-2026-002"
    )

    def state(case):
        return [
            (e["occurred_at"], e["acceptances"], e["background_changed"], e["proposal"])
            for e in case["encounters"]
        ]

    assert state(first) == state(second)


def test_every_cast_case_that_changes_background_is_the_one_the_seed_stores(api_client):
    shown = seeded(api_client)

    changed = [
        case.case_number
        for case in cast.load_cast().cases
        if any(e["background_changed"] for e in shown[case.case_number]["encounters"])
    ]

    assert changed == [
        case.case_number for case in cast.load_cast().cases if cast.changed_background(case)
    ]
