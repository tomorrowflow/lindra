"""A visit's draft and its background through the JSON API (ADR 0008, ADR 0010).

A visit has four sections and is generated from its own notes plus its background: the
accepted draft of the assessment and the accepted drafts of visits dated earlier. A pending
proposal and a later visit are never background. Each visit carries a background revision, the
sum of the acceptance counters of its background. A proposal generated on an older revision
cannot be accepted, and a draft accepted on an older revision is marked, its text kept.

Every test uses the fixture text model, keyed to the fictional cast. `build` creates a cast
case through the API with no draft anywhere, so the tests control which encounter was accepted
when. A recording model shows what the model was sent. These tests prove the workflow Lindra
enforces itself, not the medical fidelity of any model.
"""

import pytest
from fastapi.testclient import TestClient

from lindra import cast
from lindra.app import create_app
from lindra.cast import VISIT_SECTIONS
from lindra.config import Settings
from lindra.standins import FixtureTextModel
from tests.conftest import NOW, TOKEN

VERLAUF, BEFUNDE, EINSCHAETZUNG, VORGEHEN = VISIT_SECTIONS

BACKGROUND_CHANGED = "Hintergrund seit Erstellung geändert"
OUTDATED_BY_BACKGROUND = "Veraltet: Hintergrund seit diesem Vorschlag geändert"
OUTDATED_BY_NOTES = "Veraltet: Notizen seit diesem Vorschlag geändert"
OUTDATED_BY_BOTH = "Veraltet: Notizen und Hintergrund seit diesem Vorschlag geändert"


class Recording:
    """The fixture model that remembers every request it was sent."""

    def __init__(self):
        self.inner = FixtureTextModel(cast.load_cast())
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return self.inner.generate(request)


def client_with(tmp_path, model=None):
    app = create_app(Settings(token=TOKEN, data_dir=tmp_path), clock=lambda: NOW, text_model=model)
    return TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"})


@pytest.fixture
def model():
    return Recording()


@pytest.fixture
def client(tmp_path, model):
    return client_with(tmp_path, model)


class Contact:
    """One encounter of a case with the paths the physician's browser would call."""

    def __init__(self, client, base, key):
        self.client = client
        self.base = base
        self.key = key
        self.id = int(base.rsplit("/", 1)[1])

    def get(self, suffix=""):
        return self.client.get(self.base + suffix)

    def draft(self):
        return self.get("/draft").json()

    def encounter(self):
        return self.get().json()

    def save_notes(self, text):
        return self.client.put(f"{self.base}/notes", json={"notes": text})

    def generate(self):
        return self.client.post(f"{self.base}/generate")

    def accept(self):
        return self.client.post(f"{self.base}/proposal/accept")

    def discard(self):
        return self.client.delete(f"{self.base}/proposal")

    def edit(self, number, text):
        return self.client.put(f"{self.base}/draft/sections/{number}", json={"text": text})

    def copied(self, number):
        return self.client.post(f"{self.base}/draft/sections/{number}/copied")

    def handover(self):
        return self.get("/handover").json()

    def accepted(self):
        """Generate and accept in one go, as the physician does when the proposal is right."""
        assert self.generate().status_code == 200
        response = self.accept()
        assert response.status_code == 200, response.text
        return response.json()


class Built:
    def __init__(self, client, case_id, contacts):
        self.client = client
        self.case_id = case_id
        self.contacts = contacts

    def __getitem__(self, key):
        return self.contacts[key]

    def listing(self):
        """The case as the sidebar's data shows it, by encounter key."""
        shown = self.client.get(f"/api/cases/{self.case_id}").json()["encounters"]
        return {key: next(e for e in shown if e["id"] == c.id) for key, c in self.contacts.items()}


def build(client, number):
    """A cast case created through the API: the assessment and the visits at the cast's dates,
    each with the cast's notes, and no draft anywhere."""
    fictional = next(c for c in cast.load_cast().cases if c.case_number == number)
    assessment = next(e for e in fictional.encounters if e.kind == "assessment")
    created = client.post(
        "/api/cases",
        json={
            "case_number": fictional.case_number,
            "patient_name": fictional.patient_name,
            "label": fictional.label,
            "assessment_date": assessment.date.isoformat(),
            "assessment_time": "09:00",
            "period_start": fictional.period_start.isoformat(),
            "period_end": fictional.period_end.isoformat(),
        },
    ).json()
    case_id = created["id"]
    contacts = {}
    for encounter in fictional.encounters:
        if encounter.kind == "assessment":
            encounter_id = created["encounters"][0]["id"]
        else:
            visit = client.post(
                f"/api/cases/{case_id}/visits",
                json={"visit_date": encounter.date.isoformat(), "visit_time": "09:00"},
            )
            assert visit.status_code == 201, visit.text
            encounter_id = visit.json()["id"]
        contact = Contact(client, f"/api/cases/{case_id}/encounters/{encounter_id}", encounter.key)
        assert contact.save_notes(encounter.notes).status_code == 200
        contacts[encounter.key] = contact
    return Built(client, case_id, contacts)


def titles(sections):
    return [s["title"] for s in sections]


def texts(sections):
    return [s["text"] for s in sections]


# ---- four sections, nothing padded ----


def test_a_visit_draft_has_exactly_the_four_sections_of_a_visit_in_order(client):
    visit = build(client, "FIK-2026-001")["visit-1"]

    shown = visit.generate().json()

    assert titles(shown["proposal"]["sections"]) == list(VISIT_SECTIONS)
    assert titles(shown["sections"]) == list(VISIT_SECTIONS)
    assert all(s["empty"] for s in shown["sections"])


def test_an_accepted_visit_draft_holds_what_the_notes_say_in_its_four_sections(client):
    visit = build(client, "FIK-2026-001")["visit-1"]

    shown = visit.accepted()

    assert titles(shown["sections"]) == list(VISIT_SECTIONS)
    assert "NRS 5 bis 6" in shown["sections"][0]["text"]
    assert shown["sections"][1]["text"] == "Druckschmerz L4 bis S1 etwas geringer."
    assert shown["sections"][2]["text"] == "Die Bewegungstherapie wird fortgeführt."
    assert shown["sections"][3]["text"] == "Tägliche Gehstrecke um 100 m steigern."


def test_sections_the_notes_do_not_support_stay_empty_and_are_on_the_clarification_list(client):
    visit = build(client, "FIK-2026-003")["visit-1"]

    proposal = visit.generate().json()["proposal"]

    for number in (2, 3, 4):
        section = proposal["sections"][number - 1]
        assert section["paragraphs"] == []
        assert section["text"] == "" and section["empty"]
        assert any(c["section"] == section["title"] for c in proposal["clarifications"])
    accepted = visit.accept().json()
    assert {c["section"] for c in accepted["clarifications"]} >= {BEFUNDE, EINSCHAETZUNG, VORGEHEN}
    assert all(accepted["sections"][i]["empty"] for i in (1, 2, 3))


def test_a_visit_whose_notes_carry_no_decision_leaves_that_section_empty_with_an_item(client):
    contacts = build(client, "FIK-2026-003")
    contacts["assessment"].accepted()
    visit = contacts["visit-1"]

    shown = visit.accepted()

    assert shown["sections"][3]["text"] == ""
    items = [c["text"] for c in shown["clarifications"] if c["section"] == VORGEHEN]
    assert items == ["Für diese Visite ist kein Vorgehen und kein Ziel notiert."]


class CarriesTheAssessmentPlanOver:
    """A model that fills the visit's agreed plan from the background."""

    def __init__(self):
        self.inner = FixtureTextModel(cast.load_cast())

    def generate(self, request):
        raw = self.inner.generate(request)
        if not request.background:
            return raw
        source = request.background[0].source
        raw["sections"][3]["paragraphs"].append(
            {
                "text": "Ziel: Gehstrecke von 500 m auf 2 km.",
                "heading": "",
                "references": [{"source": source, "quote": "Ziel: Gehstrecke von 500 m auf 2 km."}],
            }
        )
        return raw


def test_a_plan_or_goal_is_never_taken_from_the_background_into_a_visit(tmp_path):
    client = client_with(tmp_path, CarriesTheAssessmentPlanOver())
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()

    proposal = contacts["visit-1"].generate().json()["proposal"]

    plan = proposal["sections"][3]
    assert plan["text"] == "Tägliche Gehstrecke um 100 m steigern."
    assert "500 m" not in plan["text"]
    asked = [c["text"] for c in proposal["clarifications"] if c["section"] == VORGEHEN]
    assert any("nicht allein auf die Notizen" in text for text in asked)


class CarriesThePlanOverBesideANotesReference(CarriesTheAssessmentPlanOver):
    """The same, but the paragraph also quotes an unrelated passage of today's notes."""

    def generate(self, request):
        raw = super().generate(request)
        if request.background:
            plan = raw["sections"][3]["paragraphs"][-1]
            quote = "Schmerz im Verlauf unverändert, NRS 5 bis 6"
            plan["references"].insert(0, {"source": "notes", "quote": quote})
        return raw


def test_a_plan_from_the_background_does_not_pass_beside_an_unrelated_notes_reference(tmp_path):
    client = client_with(tmp_path, CarriesThePlanOverBesideANotesReference())
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()

    proposal = contacts["visit-1"].generate().json()["proposal"]

    plan = proposal["sections"][3]
    assert plan["text"] == "Tägliche Gehstrecke um 100 m steigern."
    asked = [c["text"] for c in proposal["clarifications"] if c["section"] == VORGEHEN]
    assert any("nicht allein auf die Notizen" in text for text in asked)


# ---- what the model is sent: its own notes plus the background ----


def test_a_visit_is_generated_from_its_own_notes_and_the_accepted_assessment(client, model):
    contacts = build(client, "FIK-2026-001")
    accepted = contacts["assessment"].accepted()
    model.requests.clear()

    contacts["visit-1"].generate()

    [request] = model.requests
    assert request.kind == "visit"
    assert request.notes == cast.load_cast().cases[0].encounters[1].notes
    [earlier] = request.background
    assert earlier.kind == "assessment"
    assert earlier.source == f"encounter:{contacts['assessment'].id}"
    assert [title for title, _ in earlier.sections] == [
        s["title"] for s in accepted["sections"] if not s["empty"]
    ]
    assert "Ibuprofen 400 mg bei Bedarf" in earlier.text


def test_an_assessment_is_generated_from_its_notes_alone(client, model):
    contacts = build(client, "FIK-2026-001")

    contacts["assessment"].generate()

    [request] = model.requests
    assert request.kind == "assessment" and request.background == ()


def test_a_visit_without_an_accepted_assessment_has_no_background(client, model):
    contacts = build(client, "FIK-2026-001")

    proposal = contacts["visit-1"].generate().json()["proposal"]

    [request] = model.requests
    assert request.background == ()
    assert proposal["background_revision"] == 0
    # The model saw no earlier encounter, so nothing in the draft quotes one.
    origins = [p["origin"] for s in proposal["sections"] for p in s["paragraphs"]]
    assert set(origins) == {"notes"}


def test_the_assessment_is_background_once_its_proposal_is_accepted_not_before(client, model):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].generate()

    contacts["visit-1"].generate()

    assert model.requests[-1].background == ()


def test_a_pending_proposal_of_the_assessment_is_never_background(client, model):
    contacts = build(client, "FIK-2026-001")
    assessment = contacts["assessment"]
    assessment.accepted()
    assessment.edit(1, "Meine Fassung der Sozialanamnese.")
    assessment.generate()
    assert assessment.draft()["proposal"] is not None

    contacts["visit-1"].generate()

    [earlier] = model.requests[-1].background
    assert "Meine Fassung der Sozialanamnese." in earlier.text
    pending = assessment.draft()["proposal"]["sections"][0]["text"]
    assert pending not in earlier.text


def test_a_pending_proposal_of_an_earlier_visit_is_never_background(client, model):
    contacts = build(client, "FIK-2026-002")
    contacts["assessment"].accepted()
    contacts["visit-2"].generate()

    contacts["visit-1"].generate()

    assert [b.kind for b in model.requests[-1].background] == ["assessment"]


def test_an_accepted_earlier_visit_is_background_in_date_order(client, model):
    contacts = build(client, "FIK-2026-002")
    contacts["assessment"].accepted()
    contacts["visit-2"].accepted()

    contacts["visit-1"].generate()

    background = model.requests[-1].background
    assert [b.kind for b in background] == ["assessment", "visit"]
    assert background[1].source == f"encounter:{contacts['visit-2'].id}"
    assert [title for title, _ in background[1].sections][0] == VERLAUF


def test_a_later_visit_is_never_background(client, model):
    contacts = build(client, "FIK-2026-002")
    contacts["assessment"].accepted()
    # visit-1 is dated 16.10., visit-2 14.10.; the later one is accepted.
    contacts["visit-1"].accepted()

    contacts["visit-2"].generate()

    assert [b.kind for b in model.requests[-1].background] == ["assessment"]


def test_a_backdated_visit_sees_only_what_preceded_its_date(client, model):
    contacts = build(client, "FIK-2026-002")
    contacts["assessment"].accepted()
    # visit-2 was entered after visit-1 but dated before it.
    contacts["visit-1"].accepted()
    contacts["visit-2"].accepted()

    proposal = contacts["visit-2"].generate().json()["proposal"]

    [earlier] = model.requests[-1].background
    assert earlier.kind == "assessment"
    assert proposal["background_revision"] == 1
    assert all(
        r["encounter"]["id"] == contacts["assessment"].id
        for s in proposal["sections"]
        for p in s["paragraphs"]
        for r in p["references"]
        if r["encounter"]
    )


def test_a_visit_created_for_an_earlier_date_than_a_visit_that_exists_does_not_see_it(
    client, model
):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()
    contacts["visit-1"].accepted()
    # The assessment's own day, before the visit on 09.10.; the fixture has no draft for it,
    # so the request is all there is to inspect.
    created = client.post(
        f"/api/cases/{contacts.case_id}/visits",
        json={"visit_date": "2026-10-07", "visit_time": "08:00"},
    ).json()
    backdated = Contact(client, f"/api/cases/{contacts.case_id}/encounters/{created['id']}", "x")
    backdated.save_notes("Heute ruhiger.")

    backdated.generate()

    [request] = model.requests[-1:]
    assert request.occurred_at.date().isoformat() == "2026-10-07"
    assert [b.kind for b in request.background] == ["assessment"]


# ---- the background revision ----


def test_a_visit_starts_with_background_revision_zero_and_follows_the_acceptances(client):
    contacts = build(client, "FIK-2026-002")
    assessment, later, backdated = contacts["assessment"], contacts["visit-1"], contacts["visit-2"]

    assert later.draft()["background_revision"] == 0

    assessment.accepted()
    assert later.draft()["background_revision"] == 1

    assessment.accepted()
    assert later.draft()["background_revision"] == 2
    assert backdated.draft()["background_revision"] == 2

    backdated.accepted()
    # visit-2 is dated before visit-1: its acceptance is background of visit-1 only.
    assert later.draft()["background_revision"] == 3
    assert backdated.draft()["background_revision"] == 2

    later.accepted()
    assert backdated.draft()["background_revision"] == 2
    assert assessment.draft()["background_revision"] == 0


def test_the_proposal_stores_the_background_revision_it_was_generated_from(client):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()
    contacts["assessment"].accepted()

    shown = contacts["visit-1"].generate().json()

    assert shown["proposal"]["background_revision"] == 2
    assert shown["background_revision"] == 2


def test_the_draft_stores_the_background_revision_it_was_accepted_at(client):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()
    visit = contacts["visit-1"]

    assert visit.draft()["draft_background"] is None
    shown = visit.accepted()

    assert shown["draft_background"] == 1
    assert shown["proposal"] is None


def test_a_draft_that_was_only_written_by_hand_has_no_background_revision(client):
    visit = build(client, "FIK-2026-001")["visit-1"]

    shown = visit.edit(1, "Von Hand geschrieben.").json()

    assert shown["draft_background"] is None
    assert shown["background_changed"] is False


def test_the_assessment_has_no_background_revision(client):
    assessment = build(client, "FIK-2026-001")["assessment"]

    shown = assessment.accepted()

    assert shown["background_revision"] == 0
    assert shown["draft_background"] is None
    assert assessment.draft()["proposal"] is None


def test_the_case_listing_carries_the_background_revision_of_each_encounter(client):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()

    shown = contacts.listing()

    assert shown["assessment"]["background_revision"] == 0
    assert shown["visit-1"]["background_revision"] == 1


# ---- historical references ----


def test_a_paragraph_drawn_from_the_background_names_the_earlier_encounter_and_its_date(client):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()

    proposal = contacts["visit-1"].generate().json()["proposal"]

    history = proposal["sections"][0]["paragraphs"][1]
    assert history["text"].startswith("Zuvor: Ibuprofen 400 mg bei Bedarf")
    assert history["origin"] == "background"
    [reference] = history["references"]
    assert reference["origin"] == "background"
    assert reference["source"] == f"encounter:{contacts['assessment'].id}"
    assert reference["quote"].startswith("Ibuprofen 400 mg bei Bedarf")
    assert reference["encounter"] == {
        "id": contacts["assessment"].id,
        "label": "Aufnahmeassessment, 05.10.2026 09:00",
    }


def test_the_quoted_passage_is_a_passage_of_the_accepted_draft_of_that_encounter(client):
    contacts = build(client, "FIK-2026-001")
    assessment = contacts["assessment"].accepted()
    proposal = contacts["visit-1"].generate().json()["proposal"]

    [reference] = proposal["sections"][0]["paragraphs"][1]["references"]

    assert reference["quote"] in "\n".join(texts(assessment["sections"]))


def test_a_paragraph_from_today_s_notes_keeps_aus_notizen(client):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()

    proposal = contacts["visit-1"].generate().json()["proposal"]

    today = proposal["sections"][0]["paragraphs"][0]
    assert today["origin"] == "notes"
    assert {r["origin"] for r in today["references"]} == {"notes"}
    assert all(r["encounter"] is None for r in today["references"])
    for number in (1, 2, 3):
        assert {p["origin"] for p in proposal["sections"][number]["paragraphs"]} == {"notes"}


def test_the_historical_reference_stays_in_the_draft_after_acceptance(client):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()

    shown = contacts["visit-1"].accepted()

    assert [p["origin"] for p in shown["sections"][0]["paragraphs"]] == ["notes", "background"]


def test_a_paragraph_the_physician_rewrote_loses_its_historical_reference(client):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()
    visit = contacts["visit-1"]
    shown = visit.accepted()
    text = shown["sections"][0]["text"]

    edited = visit.edit(
        1, text.replace("Zuvor: Ibuprofen 400 mg", "Zuvor: Ibuprofen 500 mg")
    ).json()

    origins = [p["origin"] for p in edited["sections"][0]["paragraphs"]]
    assert origins == ["notes", "hand"]


def test_a_historical_paragraph_the_physician_left_alone_keeps_its_reference(client):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()
    visit = contacts["visit-1"]
    text = visit.accepted()["sections"][0]["text"]

    edited = visit.edit(1, text.replace("Schmerz unverändert", "Schmerz gleich")).json()

    assert [p["origin"] for p in edited["sections"][0]["paragraphs"]] == ["hand", "background"]


# ---- the proposal outdated by its background ----


def test_a_proposal_is_outdated_when_its_background_was_accepted_again_after_it(client):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()
    visit = contacts["visit-1"]
    proposal = visit.generate().json()["proposal"]
    assert proposal["outdated"] is False and proposal["outdated_reason"] is None

    contacts["assessment"].accepted()

    stale = visit.draft()["proposal"]
    assert stale["outdated"] is True
    assert stale["outdated_reason"] == OUTDATED_BY_BACKGROUND
    assert stale["background_outdated"] is True and stale["notes_outdated"] is False
    assert stale["background_revision"] == 1


def test_the_outdated_proposal_is_refused_with_the_reason_and_nothing_changes(client):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()
    visit = contacts["visit-1"]
    visit.generate()
    contacts["assessment"].accepted()
    before = visit.draft()

    response = visit.accept()

    assert response.status_code == 409
    assert response.json() == {"detail": OUTDATED_BY_BACKGROUND}
    assert visit.draft() == before
    assert before["has_draft"] is False and before["acceptances"] == 0


def test_the_outdated_proposal_stays_visible_and_unchanged_nothing_regenerates(client, model):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()
    visit = contacts["visit-1"]
    visit.generate()
    before = visit.draft()["proposal"]["sections"]

    contacts["assessment"].accepted()
    asked = len(model.requests)

    assert visit.draft()["proposal"]["sections"] == before
    assert contacts.listing()["visit-1"]["proposal"] == "outdated"
    assert len(model.requests) == asked


def test_discarding_and_generating_again_uses_the_new_background_and_can_be_accepted(client):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()
    visit = contacts["visit-1"]
    visit.generate()
    contacts["assessment"].accepted()
    visit.discard()

    fresh = visit.generate().json()["proposal"]

    assert fresh["background_revision"] == 2
    assert fresh["outdated"] is False
    assert visit.accept().status_code == 200
    assert visit.draft()["draft_background"] == 2


def test_generating_again_without_discarding_replaces_the_outdated_proposal(client):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()
    visit = contacts["visit-1"]
    visit.generate()
    contacts["assessment"].accepted()

    fresh = visit.generate().json()["proposal"]

    assert fresh["outdated"] is False and fresh["background_revision"] == 2


def test_a_proposal_outdated_by_notes_and_background_names_both(client):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()
    visit = contacts["visit-1"]
    visit.generate()
    visit.save_notes(visit.encounter()["notes"] + " Nachtrag.")
    assert visit.draft()["proposal"]["outdated_reason"] == OUTDATED_BY_NOTES

    contacts["assessment"].accepted()

    stale = visit.draft()["proposal"]
    assert stale["outdated_reason"] == OUTDATED_BY_BOTH
    assert visit.accept().json() == {"detail": OUTDATED_BY_BOTH}


def test_acceptance_is_refused_for_every_background_encounter_that_was_accepted_again(client):
    contacts = build(client, "FIK-2026-002")
    contacts["assessment"].accepted()
    contacts["visit-2"].accepted()
    visit = contacts["visit-1"]
    visit.generate()

    contacts["visit-2"].accepted()

    assert visit.accept().json() == {"detail": OUTDATED_BY_BACKGROUND}


def test_a_later_visit_accepted_after_the_proposal_does_not_outdate_it(client):
    contacts = build(client, "FIK-2026-002")
    contacts["assessment"].accepted()
    backdated = contacts["visit-2"]
    backdated.generate()

    contacts["visit-1"].accepted()

    assert backdated.draft()["proposal"]["outdated"] is False
    assert backdated.accept().status_code == 200


def test_an_assessment_proposal_is_never_outdated_by_background(client):
    contacts = build(client, "FIK-2026-001")
    assessment = contacts["assessment"]
    assessment.generate()

    contacts["visit-1"].accepted()

    assert assessment.draft()["proposal"]["outdated"] is False
    assert assessment.accept().status_code == 200


# ---- the draft marked "Hintergrund seit Erstellung geändert" ----


def test_a_draft_accepted_on_older_background_is_marked_and_its_text_is_kept(client):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()
    visit = contacts["visit-1"]
    before = visit.accepted()
    assert before["background_changed"] is False and before["background_changed_label"] is None

    contacts["assessment"].accepted()

    after = visit.draft()
    assert after["background_changed"] is True
    assert after["background_changed_label"] == BACKGROUND_CHANGED
    assert after["draft_background"] == 1 and after["background_revision"] == 2
    assert after["sections"] == before["sections"]
    assert after["possibly_outdated"] is False
    assert after["proposal"] is None


def test_the_sidebar_data_shows_the_background_marker_on_the_visit_only(client):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()
    contacts["visit-1"].accepted()
    assert not any(e["background_changed"] for e in contacts.listing().values())

    contacts["assessment"].accepted()

    shown = contacts.listing()
    assert shown["visit-1"]["background_changed"] is True
    assert shown["assessment"]["background_changed"] is False


def test_the_marker_stays_through_a_hand_edit_and_a_discarded_outdated_proposal(client):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()
    visit = contacts["visit-1"]
    visit.accepted()
    visit.generate()
    contacts["assessment"].accepted()

    visit.edit(2, "Meine Befunde.")
    visit.discard()

    shown = visit.draft()
    assert shown["background_changed"] is True
    assert shown["sections"][1]["text"] == "Meine Befunde."


def test_only_a_proposal_from_the_current_background_clears_the_marker(client):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()
    visit = contacts["visit-1"]
    visit.accepted()
    contacts["assessment"].accepted()
    assert visit.draft()["background_changed"] is True

    visit.generate()
    shown = visit.accept().json()

    assert shown["background_changed"] is False
    assert shown["draft_background"] == 2


def test_a_visit_dated_earlier_that_is_accepted_later_changes_the_background_of_a_later_one(client):
    contacts = build(client, "FIK-2026-002")
    contacts["assessment"].accepted()
    later = contacts["visit-1"]
    later.accepted()
    assert later.draft()["background_changed"] is False

    contacts["visit-2"].accepted()

    assert later.draft()["background_changed"] is True
    assert contacts["visit-2"].draft()["background_changed"] is False


def test_a_later_visit_accepted_again_does_not_mark_an_earlier_one(client):
    contacts = build(client, "FIK-2026-002")
    contacts["assessment"].accepted()
    backdated = contacts["visit-2"]
    backdated.accepted()

    contacts["visit-1"].accepted()
    contacts["visit-1"].accepted()

    assert backdated.draft()["background_changed"] is False


def test_notes_changing_after_a_visit_draft_still_marks_the_draft_as_possibly_outdated(client):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()
    visit = contacts["visit-1"]
    visit.accepted()

    visit.save_notes(visit.encounter()["notes"] + " Nachtrag.")

    shown = visit.draft()
    assert shown["possibly_outdated"] is True and shown["background_changed"] is False


# ---- contradictions between the background and today's notes ----


def test_a_contradiction_with_the_background_is_a_clarification_item_naming_both_statements(
    client,
):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()

    proposal = contacts["visit-1"].generate().json()["proposal"]

    [item] = [c for c in proposal["clarifications"] if "widersprechen" in c["text"]]
    assert item["section"] == VERLAUF
    assert "Aufnahmeassessment vom 05.10.2026" in item["text"]
    assert "strahlt der Schmerz nicht ins Bein aus" in item["text"]
    assert "Ausstrahlung ins linke Bein" in item["text"]


def test_neither_side_of_the_contradiction_is_worded_in_the_draft(client):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()

    proposal = contacts["visit-1"].generate().json()["proposal"]

    everything = " ".join(texts(proposal["sections"]))
    assert "Bein" not in everything and "strahl" not in everything.lower()


def test_accepting_adopts_the_contradiction_item_and_a_manual_edit_does_not_resolve_it(client):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()
    visit = contacts["visit-1"]
    accepted = visit.accepted()
    assert any("widersprechen" in c["text"] for c in accepted["clarifications"])

    edited = visit.edit(1, "Der Schmerz strahlt nicht ins Bein aus.").json()

    assert edited["clarifications"] == accepted["clarifications"]


class SettlesADoseContradiction:
    """A model that sees two doses and words only today's, though it flagged the conflict."""

    def generate(self, request):
        item = {
            "section": VERLAUF,
            "text": "Aufnahmeassessment: Ibuprofen 400 mg. Notizen dieser Visite: Ibuprofen "
            "600 mg. Die Angaben widersprechen sich: 400 mg oder 600 mg.",
        }
        quote = "Ibuprofen 600 mg bei Bedarf"
        paragraph = {
            "text": "Ibuprofen 600 mg bei Bedarf.",
            "heading": "",
            "references": [{"source": "notes", "quote": quote}],
        }
        return {
            "sections": [
                {"title": t, "paragraphs": [paragraph] if t == VERLAUF else []}
                for t in VISIT_SECTIONS
            ],
            "clarifications": [item],
        }


def test_a_paragraph_that_settles_a_dose_contradiction_is_dropped_and_both_doses_are_named(
    tmp_path,
):
    client = client_with(tmp_path, SettlesADoseContradiction())
    contacts = build(client, "FIK-2026-001")
    visit = contacts["visit-1"]
    visit.save_notes("Ibuprofen 600 mg bei Bedarf.")

    proposal = visit.generate().json()["proposal"]

    assert proposal["sections"][0]["paragraphs"] == []
    asked = [c["text"] for c in proposal["clarifications"] if c["section"] == VERLAUF]
    assert any("400 mg" in t and "600 mg" in t and "widersprechen" in t for t in asked)
    assert any("400mg" in t and "600mg" in t for t in asked)


# ---- acceptance, manual edits, handover and copy as for the assessment ----


def test_accepting_a_visit_proposal_keeps_a_section_the_physician_edited(client):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()
    visit = contacts["visit-1"]
    visit.generate()
    visit.edit(2, "Meine Befunde von Hand.")
    shown = visit.draft()
    assert shown["proposal"]["retains"] == [BEFUNDE]
    assert shown["proposal"]["replaces"] == [VERLAUF, EINSCHAETZUNG, VORGEHEN]

    accepted = visit.accept().json()

    assert accepted["sections"][1]["text"] == "Meine Befunde von Hand."
    assert accepted["sections"][1]["manual"] and accepted["sections"][1]["not_updated"]
    assert not accepted["sections"][0]["manual"]
    assert accepted["sections"][2]["text"] == "Die Bewegungstherapie wird fortgeführt."


def test_a_hand_edit_marks_only_that_section_and_the_acceptance_counter_counts_acceptances(
    client,
):
    visit = build(client, "FIK-2026-001")["visit-1"]

    edited = visit.edit(3, "Meine Einschätzung.").json()

    assert [s["manual"] for s in edited["sections"]] == [False, False, True, False]
    assert edited["acceptances"] == 0
    assert visit.accepted()["acceptances"] == 1


def test_the_handover_of_a_visit_copies_the_current_draft_and_never_the_proposal(client):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()
    visit = contacts["visit-1"]
    visit.accepted()
    visit.edit(3, "Meine Einschätzung.")
    visit.generate()

    handover = visit.handover()

    assert handover["has_draft"] is True
    assert titles(handover["sections"]) == list(VISIT_SECTIONS)
    assert handover["sections"][2]["text"] == "Meine Einschätzung."
    assert "Bewegungstherapie wird fortgeführt" not in " ".join(texts(handover["sections"]))


def test_copying_a_visit_section_is_recorded_and_accepting_clears_it(client):
    contacts = build(client, "FIK-2026-001")
    visit = contacts["visit-1"]
    visit.accepted()

    copied = visit.copied(2).json()
    assert [s["copied"] for s in copied["sections"]] == [False, True, False, False]

    visit.generate()
    assert not any(s["copied"] for s in visit.accept().json()["sections"])


def test_a_visit_without_an_accepted_draft_has_nothing_to_copy(client):
    visit = build(client, "FIK-2026-001")["visit-1"]

    assert visit.handover() == {"has_draft": False, "sections": []}
    refused = visit.copied(1)
    assert refused.status_code == 409
    assert refused.json() == {"detail": "Es gibt noch nichts zu kopieren"}


def test_an_empty_section_of_a_visit_has_nothing_to_copy(client):
    visit = build(client, "FIK-2026-003")["visit-1"]
    visit.accepted()

    assert visit.copied(2).status_code == 409
    assert visit.copied(1).status_code == 200


def test_generating_a_visit_without_notes_is_refused(client):
    contacts = build(client, "FIK-2026-001")
    contacts["visit-1"].save_notes("   ")

    response = contacts["visit-1"].generate()

    assert response.status_code == 409
    assert response.json() == {"detail": "Zuerst Notizen eintragen"}


def test_a_visit_outside_the_cast_is_a_failed_generation_that_changes_nothing(client):
    contacts = build(client, "FIK-2026-001")
    contacts["assessment"].accepted()
    created = client.post(
        f"/api/cases/{contacts.case_id}/visits",
        json={"visit_date": "2026-10-12", "visit_time": "09:00"},
    ).json()
    stranger = Contact(client, f"/api/cases/{contacts.case_id}/encounters/{created['id']}", "x")
    stranger.save_notes("Etwas.")

    response = stranger.generate()

    assert response.status_code == 502
    assert stranger.draft()["proposal"] is None


def test_the_section_number_of_a_visit_runs_from_one_to_four(client):
    visit = build(client, "FIK-2026-001")["visit-1"]

    assert visit.edit(4, "Text").status_code == 200
    assert visit.edit(5, "Text").status_code == 404
    assert visit.copied(5).status_code == 404
