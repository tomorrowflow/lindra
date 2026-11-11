"""Draft generation, proposal acceptance and handover through the JSON API (ADR 0008).

Every test uses the fixture text model, keyed to the fictional cast, so the cases come from the
seed hook. A model that fails or answers in prose is a small class below; no test reaches a
real model. These tests prove the workflow Lindra enforces itself (structure check, merge,
outdated and stale, copy text), not the medical fidelity of any model.
"""

import pytest
from fastapi.testclient import TestClient

from lindra import cast
from lindra.app import create_app
from lindra.cast import ASSESSMENT_SECTIONS
from lindra.config import Settings
from lindra.standins import FixtureTextModel
from lindra.textmodel import GenerationFailed
from tests.conftest import NOW, TOKEN
from tests.test_cases_api import seeded_case

CASE = "FIK-2026-001"
SOZIAL, FRUEHER, THERAPIE, SCHMERZ, INTERNIST, BEFUND, PLAN = ASSESSMENT_SECTIONS


def client_with(tmp_path, model=None):
    app = create_app(Settings(token=TOKEN, data_dir=tmp_path), clock=lambda: NOW, text_model=model)
    return TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"})


@pytest.fixture
def client(tmp_path):
    return client_with(tmp_path)


class Encounter:
    """One seeded encounter with the paths the physician's browser would call."""

    def __init__(self, client, number=CASE, kind="assessment", base=None):
        self.client = client
        if base is None:
            case = seeded_case(client, number)
            found = next(e for e in case["encounters"] if e["kind"] == kind)
            base = f"/api/cases/{case['id']}/encounters/{found['id']}"
        self.base = base

    def through(self, client):
        """The same encounter, reached through another client."""
        return Encounter(client, base=self.base)

    def get(self, suffix=""):
        return self.client.get(self.base + suffix)

    def draft(self):
        return self.get("/draft").json()

    def notes(self):
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


@pytest.fixture
def assessment(client):
    return Encounter(client)


def section(shown, number):
    return shown["sections"][number - 1]


def proposal_text(shown, number):
    return shown["proposal"]["sections"][number - 1]["text"]


class NotesEditedWhileGenerating:
    """The fixture model, but the physician saves her notes while it is still working."""

    def __init__(self, notes):
        self.notes = notes
        self.encounter = None
        self.inner = FixtureTextModel(cast.load_cast())

    def generate(self, request):
        self.encounter.save_notes(self.notes)
        return self.inner.generate(request)


class AnswersInProse:
    def generate(self, request):
        return "Die Patientin hat seit 14 Monaten Rückenschmerzen und nimmt Ibuprofen."


class Down:
    def generate(self, request):
        raise ConnectionError("the inference server is not running")


class Unreachable:
    def generate(self, request):
        raise GenerationFailed("Das Textmodell ist nicht erreichbar.")


# ---- the token guards every route ----


@pytest.mark.parametrize(
    ("method", "suffix"),
    [
        ("GET", "/draft"),
        ("GET", "/generation"),
        ("GET", "/handover"),
        ("POST", "/generate"),
        ("POST", "/proposal/accept"),
        ("DELETE", "/proposal"),
        ("PUT", "/draft/sections/1"),
        ("POST", "/draft/sections/1/copied"),
    ],
)
def test_review_routes_refuse_requests_without_the_token(anonymous, method, suffix):
    response = anonymous.request(method, f"/api/cases/1/encounters/1{suffix}")

    assert response.status_code == 401
    assert response.json() == {"detail": "Anmeldung erforderlich"}


# ---- generation happens only on request ----


def test_a_new_encounter_has_no_draft_and_no_proposal(assessment):
    shown = assessment.draft()

    assert not shown["has_draft"]
    assert shown["proposal"] is None
    assert [s["title"] for s in shown["sections"]] == list(ASSESSMENT_SECTIONS)
    assert all(s["empty"] for s in shown["sections"])


def test_nothing_is_generated_on_open_or_on_saving_notes(assessment):
    assessment.get()
    assessment.get("/draft")
    assessment.save_notes("Geänderte Notizen zum Rückenschmerz.")
    assessment.save_notes("Noch einmal geändert.")

    shown = assessment.draft()
    assert shown["proposal"] is None
    assert not shown["has_draft"]
    assert shown["generation"] == {"state": "idle", "reason": ""}


def test_generating_gives_one_proposal_for_the_whole_draft_and_leaves_the_draft_alone(assessment):
    response = assessment.generate()

    assert response.status_code == 200
    shown = response.json()
    assert not shown["has_draft"]
    assert all(s["empty"] for s in shown["sections"])
    proposal = shown["proposal"]
    assert [s["title"] for s in proposal["sections"]] == list(ASSESSMENT_SECTIONS)
    assert proposal["outdated"] is False
    assert proposal["notes_revision"] == assessment.notes()["notes_revision"]
    assert assessment.notes()["proposal"] == "pending"


def test_the_proposal_has_structured_paragraphs_with_input_references_and_subheadings(assessment):
    proposal = assessment.generate().json()["proposal"]

    therapy = proposal["sections"][2]
    assert [p["heading"] for p in therapy["paragraphs"]] == [
        "Aktuelle Medikation",
        "Frühere nichtmedikamentöse Behandlungen",
    ]
    assert therapy["text"].startswith("Aktuelle Medikation\nIbuprofen 400 mg bei Bedarf")
    first = proposal["sections"][0]["paragraphs"][0]
    assert first["references"] == [
        {
            "source": "notes",
            "quote": "Patientin lebt mit Ehemann in einer Etagenwohnung, zwei erwachsene "
            "Kinder, arbeitet halbtags im Büro, aktuell krankgeschrieben.",
        }
    ]
    assert proposal["sections"][5]["paragraphs"][0]["heading"] == (
        "Körperliche und internistische Untersuchung"
    )


def test_the_proposal_carries_the_clarification_list_of_its_generation(client):
    gaps = Encounter(client, "FIK-2026-003")

    proposal = gaps.generate().json()["proposal"]

    assert {c["section"] for c in proposal["clarifications"]} >= {SOZIAL, PLAN}
    assert section_text_of(proposal, SOZIAL) == ""
    assert "Tramadol" in section_text_of(proposal, THERAPIE)


def section_text_of(proposal, title):
    return next(s["text"] for s in proposal["sections"] if s["title"] == title)


def test_generating_needs_notes(client):
    case = client.post(
        "/api/cases",
        json={
            "case_number": "FIK-2026-777",
            "patient_name": "Leer Beispiel",
            "assessment_date": "2026-11-09",
            "assessment_time": "10:30",
            "period_start": "2026-11-09",
            "period_end": "2026-11-20",
        },
    ).json()
    base = f"/api/cases/{case['id']}/encounters/{case['encounters'][0]['id']}"

    response = client.post(f"{base}/generate")

    assert response.status_code == 409
    assert response.json() == {"detail": "Zuerst Notizen eintragen"}


def test_a_visit_has_no_draft_in_this_release_step(client):
    visit = Encounter(client, kind="visit")

    assert visit.get("/draft").status_code == 404
    assert visit.generate().status_code == 404
    assert visit.edit(1, "Text").status_code == 404


def test_a_case_or_encounter_that_does_not_exist_is_not_found(client, assessment):
    assert client.post("/api/cases/999/encounters/1/generate").json() == {
        "detail": "Fall nicht gefunden"
    }
    base = assessment.base.rsplit("/", 1)[0] + "/999"
    assert client.get(f"{base}/draft").json() == {"detail": "Kontakt nicht gefunden"}


# ---- a failed generation costs nothing ----


def test_a_case_outside_the_fixture_cast_is_a_failed_generation_with_notes_untouched(client):
    case = client.post(
        "/api/cases",
        json={
            "case_number": "FIK-2026-778",
            "patient_name": "Fremd Beispiel",
            "assessment_date": "2026-11-09",
            "assessment_time": "10:30",
            "period_start": "2026-11-09",
            "period_end": "2026-11-20",
        },
    ).json()
    base = f"/api/cases/{case['id']}/encounters/{case['encounters'][0]['id']}"
    client.put(f"{base}/notes", json={"notes": "Rückenschmerz seit Jahren."})

    response = client.post(f"{base}/generate")

    assert response.status_code == 502
    assert "erfundenen Fällen" in response.json()["detail"]
    shown = client.get(f"{base}/draft").json()
    assert shown["proposal"] is None and not shown["has_draft"]
    assert client.get(base).json()["notes"] == "Rückenschmerz seit Jahren."


def test_prose_from_the_model_is_a_failed_generation(tmp_path):
    client = client_with(tmp_path, AnswersInProse())
    encounter = Encounter(client)

    response = encounter.generate()

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Das Ergebnis des Textmodells hat nicht die erwartete Struktur."
    }
    assert encounter.draft()["proposal"] is None


def test_a_model_that_is_down_is_a_failed_generation_not_a_server_error(tmp_path):
    client = client_with(tmp_path, Down())
    encounter = Encounter(client)

    response = encounter.generate()

    assert response.status_code == 502
    assert response.json() == {"detail": "Das Textmodell hat nicht geantwortet."}


def test_a_failure_leaves_notes_draft_and_the_earlier_proposal_untouched(tmp_path):
    flaky = FixtureTextModel(cast.load_cast())
    client = client_with(tmp_path, flaky)
    encounter = Encounter(client)
    encounter.generate()
    encounter.accept()
    encounter.edit(1, "Meine Fassung.")
    encounter.save_notes(encounter.notes()["notes"] + " Neu.")
    encounter.generate()
    before = (encounter.draft(), encounter.notes())
    # The same storage, served by an application whose model now fails.
    failing = encounter.through(client_with(tmp_path, Unreachable()))

    response = failing.generate()

    assert response.status_code == 502
    assert response.json() == {"detail": "Das Textmodell ist nicht erreichbar."}
    after = (failing.draft(), failing.notes())
    for key in ("sections", "proposal", "clarifications", "acceptances", "has_draft"):
        assert after[0][key] == before[0][key]
    assert after[1]["notes"] == before[1]["notes"]
    assert after[1]["notes_revision"] == before[1]["notes_revision"]


def test_a_failure_is_reported_until_the_next_try_and_a_retry_can_succeed(tmp_path):
    client = client_with(tmp_path, Unreachable())
    encounter = Encounter(client)

    encounter.generate()

    assert encounter.draft()["generation"] == {
        "state": "failed",
        "reason": "Das Textmodell ist nicht erreichbar.",
    }
    assert encounter.get("/generation").json()["state"] == "failed"

    retry = encounter.through(client_with(tmp_path))
    assert retry.generate().status_code == 200
    assert retry.draft()["generation"]["state"] == "idle"


def test_a_second_generation_while_one_runs_is_refused(tmp_path):
    class Impatient:
        def __init__(self):
            self.encounter = None
            self.inner = FixtureTextModel(cast.load_cast())
            self.second = None

        def generate(self, request):
            self.second = self.encounter.generate()
            return self.inner.generate(request)

    model = Impatient()
    client = client_with(tmp_path, model)
    model.encounter = Encounter(client)

    first = model.encounter.generate()

    assert first.status_code == 200
    assert model.second.status_code == 409
    assert model.second.json() == {"detail": "Für diesen Kontakt wird gerade ein Entwurf erzeugt"}


def test_while_a_generation_runs_the_state_says_so_and_the_notes_can_still_be_saved(tmp_path):
    seen = {}

    class Observing:
        def __init__(self):
            self.encounter = None
            self.inner = FixtureTextModel(cast.load_cast())

        def generate(self, request):
            seen["state"] = self.encounter.get("/generation").json()["state"]
            seen["save"] = self.encounter.save_notes("Während der Erzeugung geschrieben.")
            seen["draft"] = self.encounter.draft()
            return self.inner.generate(request)

    model = Observing()
    client = client_with(tmp_path, model)
    model.encounter = Encounter(client)

    model.encounter.generate()

    assert seen["state"] == "running"
    assert seen["save"].status_code == 200
    assert seen["draft"]["generation"]["state"] == "running"
    assert model.encounter.draft()["generation"]["state"] == "idle"


# ---- accepting the proposal as a whole ----


def test_accepting_makes_the_proposal_the_draft_and_clears_it(assessment):
    proposal = assessment.generate().json()["proposal"]

    shown = assessment.accept().json()

    assert shown["has_draft"]
    assert shown["proposal"] is None
    assert [s["text"] for s in shown["sections"]] == [s["text"] for s in proposal["sections"]]
    assert not any(s["manual"] or s["not_updated"] or s["copied"] for s in shown["sections"])
    assert assessment.notes()["proposal"] == "none"


def test_accepting_increments_the_acceptance_counter_each_time(assessment):
    assert assessment.draft()["acceptances"] == 0

    assessment.generate()
    assert assessment.accept().json()["acceptances"] == 1
    assessment.generate()
    assert assessment.accept().json()["acceptances"] == 2


def test_accepting_adopts_the_clarification_list_of_the_proposal(client):
    encounter = Encounter(client, "FIK-2026-002")
    proposal = encounter.generate().json()["proposal"]
    assert encounter.draft()["clarifications"] == []

    shown = encounter.accept().json()

    assert shown["clarifications"] == proposal["clarifications"]
    assert shown["clarifications"][0]["section"] == SCHMERZ


def test_a_manual_edit_never_resolves_a_clarification_item(client):
    encounter = Encounter(client, "FIK-2026-002")
    encounter.generate()
    encounter.accept()
    items = encounter.draft()["clarifications"]

    encounter.edit(4, "Die Frage ist beantwortet: Knieschmerz im Vordergrund.")

    assert encounter.draft()["clarifications"] == items


def test_accepting_replaces_only_sections_without_the_manual_flag(assessment):
    assessment.generate()
    assessment.accept()
    assessment.edit(4, "Meine Fassung der Schmerzanamnese.")
    assessment.generate()
    before = assessment.draft()

    shown = assessment.accept().json()

    assert section(shown, 4)["text"] == "Meine Fassung der Schmerzanamnese."
    assert section(shown, 4)["manual"] and section(shown, 4)["not_updated"]
    assert [s["not_updated"] for s in shown["sections"]] == [False] * 3 + [True] + [False] * 3
    for number in (1, 2, 3, 5, 6, 7):
        assert section(shown, number)["text"] == proposal_text(before, number)
        assert not section(shown, number)["manual"]


def test_a_section_edited_while_the_proposal_was_pending_is_retained(assessment):
    proposal_shown = assessment.generate().json()
    assessment.edit(1, "Während des Wartens geschrieben.")

    shown = assessment.accept().json()

    assert section(shown, 1)["text"] == "Während des Wartens geschrieben."
    assert section(shown, 1)["not_updated"]
    assert section(shown, 2)["text"] == proposal_text(proposal_shown, 2)
    assert not section(shown, 2)["manual"]


def test_the_proposal_names_what_it_replaces_and_what_stays_before_acceptance(assessment):
    assessment.generate()
    assessment.edit(2, "Eigene Anamnese.")
    assessment.edit(6, "Eigene Untersuchung.")

    proposal = assessment.draft()["proposal"]

    assert proposal["retains"] == [FRUEHER, BEFUND]
    assert proposal["replaces"] == [SOZIAL, THERAPIE, SCHMERZ, INTERNIST, PLAN]


def test_the_retained_sections_proposal_text_stays_visible_until_the_decision(assessment):
    assessment.generate()
    assessment.edit(1, "Meine Fassung.")
    shown = assessment.draft()

    assert section(shown, 1)["text"] == "Meine Fassung."
    assert "Etagenwohnung" in proposal_text(shown, 1)
    assessment.accept()
    assert assessment.draft()["proposal"] is None


def test_accepting_without_a_proposal_is_refused(assessment):
    response = assessment.accept()

    assert response.status_code == 409
    assert response.json() == {"detail": "Es liegt kein Vorschlag vor"}


def test_discarding_drops_the_whole_proposal_and_keeps_the_draft(assessment):
    assessment.generate()
    assessment.accept()
    assessment.edit(1, "Meine Fassung.")
    assessment.generate()

    shown = assessment.discard().json()

    assert shown["proposal"] is None
    assert section(shown, 1)["text"] == "Meine Fassung."
    assert shown["acceptances"] == 1
    assert assessment.discard().status_code == 200


def test_there_is_no_route_that_accepts_or_discards_a_single_section(assessment):
    assessment.generate()

    for method, suffix in (
        ("POST", "/proposal/sections/1/accept"),
        ("DELETE", "/proposal/sections/1"),
        ("POST", "/proposal/accept/1"),
    ):
        assert assessment.client.request(method, assessment.base + suffix).status_code in (404, 405)
    assert assessment.draft()["proposal"] is not None


# ---- hand edits ----


def test_a_hand_edit_marks_the_section_and_removes_its_input_references(assessment):
    assessment.generate()
    assessment.accept()
    assert section(assessment.draft(), 1)["paragraphs"][0]["references"]

    shown = assessment.edit(1, "Lebt allein, nicht mit dem Ehemann.").json()

    edited = section(shown, 1)
    assert edited["manual"]
    assert edited["text"] == "Lebt allein, nicht mit dem Ehemann."
    assert all(p["references"] == [] for p in edited["paragraphs"])
    assert section(shown, 2)["paragraphs"][0]["references"]
    assert not section(shown, 2)["manual"]


def test_saving_the_text_a_section_has_marks_nothing_and_a_retry_is_harmless(assessment):
    assessment.generate()
    assessment.accept()
    text = section(assessment.draft(), 1)["text"]

    assessment.edit(1, text)
    assert not section(assessment.draft(), 1)["manual"]

    assessment.edit(2, "Neu.")
    again = assessment.edit(2, "Neu.").json()
    assert section(again, 2)["text"] == "Neu."


def test_writing_a_section_without_any_draft_starts_a_draft_without_staleness(assessment):
    shown = assessment.edit(2, "Früher Bandscheibenvorfall.").json()

    assert shown["has_draft"]
    assert shown["draft_revision"] is None
    assert section(shown, 2)["manual"]
    assert [s["empty"] for s in shown["sections"]] == [True, False, True, True, True, True, True]
    assessment.save_notes("Geändert.")
    assert not assessment.draft()["possibly_outdated"]


def test_a_hand_edit_keeps_every_character_the_physician_typed(assessment):
    text = "\nErste Zeile\n\n\nZweite Zeile  \n"

    shown = assessment.edit(1, text).json()

    assert section(shown, 1)["text"] == text
    assert assessment.draft()["sections"][0]["text"] == text


@pytest.mark.parametrize(
    ("body", "errors"),
    [
        ({}, {"text": "Den Text des Abschnitts als Text übermitteln"}),
        ({"text": 3}, {"text": "Den Text des Abschnitts als Text übermitteln"}),
        ({"text": "x" * 50_001}, {"text": "Höchstens 50000 Zeichen"}),
    ],
)
def test_a_section_text_that_is_not_text_or_too_long_is_refused(assessment, body, errors):
    response = assessment.client.put(f"{assessment.base}/draft/sections/1", json=body)

    assert response.status_code == 422
    assert response.json()["errors"] == errors
    assert not assessment.draft()["has_draft"]


@pytest.mark.parametrize("number", [0, 8, 99])
def test_a_section_number_outside_the_seven_is_not_found(assessment, number):
    assert assessment.edit(number, "Text").json() == {"detail": "Abschnitt nicht gefunden"}
    assert assessment.copied(number).status_code == 404


# ---- outdated proposals and the stale draft ----


def test_changing_the_notes_outdates_a_pending_proposal_and_acceptance_is_refused(assessment):
    assessment.generate()
    assessment.save_notes(assessment.notes()["notes"] + " Neue Beobachtung.")

    shown = assessment.draft()
    refused = assessment.accept()

    assert shown["proposal"]["outdated"]
    assert (
        shown["proposal"]["outdated_reason"] == "Veraltet: Notizen seit diesem Vorschlag geändert"
    )
    assert assessment.notes()["proposal"] == "outdated"
    assert refused.status_code == 409
    assert refused.json() == {"detail": "Veraltet: Notizen seit diesem Vorschlag geändert"}
    assert not assessment.draft()["has_draft"]
    assert assessment.draft()["acceptances"] == 0


def test_an_outdated_proposal_stays_visible_until_it_is_discarded(assessment):
    first = assessment.generate().json()["proposal"]
    assessment.save_notes("Völlig neue Notizen.")

    still = assessment.draft()["proposal"]

    assert [s["text"] for s in still["sections"]] == [s["text"] for s in first["sections"]]
    assessment.discard()
    assert assessment.draft()["proposal"] is None


def test_an_explicit_regeneration_replaces_an_outdated_proposal_with_a_current_one(assessment):
    assessment.generate()
    assessment.save_notes(assessment.notes()["notes"] + " Ergänzt.")
    assert assessment.draft()["proposal"]["outdated"]

    shown = assessment.generate().json()

    assert not shown["proposal"]["outdated"]
    assert shown["proposal"]["notes_revision"] == assessment.notes()["notes_revision"]
    assert assessment.accept().status_code == 200


def test_notes_saved_while_the_model_works_outdate_the_proposal_on_arrival(tmp_path):
    model = NotesEditedWhileGenerating("Beim Erzeugen weitergeschrieben.")
    client = client_with(tmp_path, model)
    model.encounter = Encounter(client)

    shown = model.encounter.generate().json()

    assert shown["proposal"]["outdated"]
    assert shown["proposal"]["notes_revision"] == model.encounter.notes()["notes_revision"] - 1
    assert model.encounter.accept().status_code == 409


def test_saving_the_same_notes_again_does_not_outdate_the_proposal(assessment):
    assessment.generate()

    assessment.save_notes(assessment.notes()["notes"])

    assert not assessment.draft()["proposal"]["outdated"]
    assert assessment.accept().status_code == 200


def test_the_draft_is_possibly_outdated_when_the_notes_moved_past_it(assessment):
    assessment.generate()
    assessment.accept()
    assert not assessment.draft()["possibly_outdated"]

    assessment.save_notes(assessment.notes()["notes"] + " Neu.")

    shown = assessment.draft()
    assert shown["possibly_outdated"]
    assert assessment.notes()["possibly_outdated"]
    assert all(not s["manual"] for s in shown["sections"])


def test_the_marker_is_one_flag_for_the_whole_draft_not_a_guess_per_section(assessment):
    assessment.generate()
    assessment.accept()
    assessment.save_notes("Etwas ganz anderes.")

    shown = assessment.draft()

    assert shown["possibly_outdated"] is True
    assert not any("possibly_outdated" in s for s in shown["sections"])


def test_the_marker_clears_only_when_a_proposal_from_the_current_notes_is_accepted(assessment):
    assessment.generate()
    assessment.accept()
    assessment.save_notes(assessment.notes()["notes"] + " Neu.")
    assessment.generate()
    assert assessment.draft()["possibly_outdated"]

    assessment.save_notes(assessment.notes()["notes"] + " Noch mehr.")
    assert assessment.accept().status_code == 409
    assert assessment.draft()["possibly_outdated"]

    assessment.generate()
    assert assessment.draft()["possibly_outdated"]
    assert not assessment.accept().json()["possibly_outdated"]


def test_discarding_a_proposal_does_not_clear_the_marker(assessment):
    assessment.generate()
    assessment.accept()
    assessment.save_notes("Geändert.")
    assessment.generate()

    assessment.discard()

    assert assessment.draft()["possibly_outdated"]


# ---- handover and copy text ----


def test_an_encounter_without_a_draft_has_nothing_to_copy(assessment):
    shown = assessment.handover()

    assert shown == {"has_draft": False, "sections": []}


def test_handover_gives_the_plain_text_of_each_section_of_the_current_draft(assessment):
    assessment.generate()
    assessment.accept()

    shown = assessment.handover()

    assert shown["has_draft"]
    assert [s["title"] for s in shown["sections"]] == list(ASSESSMENT_SECTIONS)
    therapy = shown["sections"][2]["text"]
    assert therapy == (
        "Aktuelle Medikation\n"
        "Ibuprofen 400 mg bei Bedarf, bis zu zwei Tabletten täglich, Wirkung gering.\n\n"
        "Frühere nichtmedikamentöse Behandlungen\n"
        "Physiotherapie 2024 mit kurzer Besserung, Wärmeanwendungen."
    )
    assert shown["sections"][0]["text"].startswith("Lebt mit dem Ehemann")
    assert "Sozialanamnese" not in shown["sections"][0]["text"]


def test_handover_never_contains_the_pending_proposal(assessment):
    assessment.generate()
    assessment.accept()
    assessment.edit(1, "Meine Fassung.")
    assessment.generate()

    shown = assessment.handover()

    assert shown["sections"][0]["text"] == "Meine Fassung."
    assert "Etagenwohnung" not in shown["sections"][0]["text"]
    assert "Etagenwohnung" in proposal_text(assessment.draft(), 1)


def test_handover_before_the_first_acceptance_shows_nothing_of_a_pending_proposal(assessment):
    assessment.generate()

    assert assessment.handover() == {"has_draft": False, "sections": []}


def test_an_empty_section_is_marked_empty_and_cannot_be_marked_copied(client):
    gaps = Encounter(client, "FIK-2026-003")
    gaps.generate()
    gaps.accept()

    shown = gaps.handover()

    assert shown["sections"][0]["empty"] and shown["sections"][0]["text"] == ""
    assert not shown["sections"][2]["empty"]
    assert gaps.copied(1).status_code == 409
    assert gaps.copied(1).json() == {"detail": "Es gibt noch nichts zu kopieren"}


def test_copying_without_a_draft_is_refused(assessment):
    assert assessment.copied(1).status_code == 409


def test_a_copied_section_is_marked_until_its_text_changes(assessment):
    assessment.generate()
    assessment.accept()

    marked = assessment.copied(1).json()
    assert section(marked, 1)["copied"]
    assert assessment.copied(1).status_code == 200
    assert assessment.handover()["sections"][0]["copied"]
    assert not section(marked, 2)["copied"]

    edited = assessment.edit(1, "Neu geschrieben.").json()
    assert not section(edited, 1)["copied"]


def test_the_copy_text_of_a_hand_edited_section_is_exactly_what_was_typed(assessment):
    assessment.edit(2, "Zeile 1\n\nZeile 2")

    shown = assessment.handover()

    assert shown["has_draft"]
    assert shown["sections"][1]["text"] == "Zeile 1\n\nZeile 2"
    assert shown["sections"][0]["empty"]


# ---- what the case listing shows ----


def test_the_encounter_listing_reports_the_review_state(assessment):
    case_path = assessment.base.rsplit("/encounters", 1)[0]

    def listed():
        encounters = assessment.client.get(case_path).json()["encounters"]
        return next(e for e in encounters if e["kind"] == "assessment")

    assert (listed()["has_draft"], listed()["proposal"], listed()["acceptances"]) == (
        False,
        "none",
        0,
    )

    assessment.generate()
    assert listed()["proposal"] == "pending"
    assessment.accept()
    assert (listed()["has_draft"], listed()["proposal"], listed()["acceptances"]) == (
        True,
        "none",
        1,
    )
    assessment.save_notes("Geändert.")
    assert listed()["possibly_outdated"]


def test_saving_notes_answers_with_the_badge_the_sidebar_shows_now(assessment):
    assessment.generate()
    assessment.accept()

    answer = assessment.save_notes("Geändert.").json()

    assert answer["badge"]["state"] == "possibly_outdated"
    assert answer["badge"]["label"] == "Entwurf möglicherweise veraltet"
    assessment.generate()
    assert assessment.save_notes("Wieder geändert.").json()["badge"]["state"] == "outdated"
