"""The result check, input references and the clarification list through the JSON API.

The text model is the fixture model. Where a test needs a result that breaks a rule, it wraps
the fixture model and adds or changes a paragraph in what it returns; no other model is
involved. These tests prove what Lindra enforces itself after the model has answered
(ADR 0001, ADR 0008), not what any real model would write.
"""

import copy

import pytest

from lindra import cast
from lindra.standins import FixtureTextModel
from tests.test_review_api import (
    BEFUND,
    FRUEHER,
    INTERNIST,
    PLAN,
    SCHMERZ,
    SOZIAL,
    THERAPIE,
    Encounter,
    client_with,
    section,
)

CASE_ONE, CASE_TWO, CASE_THREE = "FIK-2026-001", "FIK-2026-002", "FIK-2026-003"


@pytest.fixture
def client(tmp_path):
    return client_with(tmp_path)


class Altered:
    """The fixture model with its answer changed by `change` before the service sees it."""

    def __init__(self, change):
        self.change = change
        self.inner = FixtureTextModel(cast.load_cast())

    def generate(self, request):
        raw = copy.deepcopy(self.inner.generate(request))
        self.change(raw)
        return raw


def paragraph(text, *quotes, heading=""):
    return {
        "text": text,
        "heading": heading,
        "references": [{"source": "notes", "quote": quote} for quote in quotes],
    }


def adding(title, *paragraphs):
    def change(raw):
        target = next(s for s in raw["sections"] if s["title"] == title)
        target["paragraphs"].extend(paragraphs)

    return change


def proposal_of(tmp_path, change, number=CASE_ONE):
    client = client_with(tmp_path, Altered(change))
    encounter = Encounter(client, number)
    return encounter, encounter.generate().json()["proposal"]


def text_of(proposal, title):
    return next(s["text"] for s in proposal["sections"] if s["title"] == title)


def items_for(proposal, title):
    return [c["text"] for c in proposal["clarifications"] if c["section"] == title]


# ---- a paragraph that does not point into the notes is dropped ----


def test_a_paragraph_whose_reference_is_not_in_the_notes_is_dropped_and_the_gap_is_listed(tmp_path):
    invented = paragraph("Raucht seit 20 Jahren.", "Raucht seit 20 Jahren")

    encounter, proposal = proposal_of(tmp_path, adding(SOZIAL, invented))

    assert "Raucht" not in text_of(proposal, SOZIAL)
    assert text_of(proposal, SOZIAL).startswith("Lebt mit dem Ehemann")
    [item] = items_for(proposal, SOZIAL)
    assert "verweist auf keine Stelle der Notizen" in item
    assert "nicht im Entwurf" in item
    assert encounter.accept().json()["clarifications"] == proposal["clarifications"]


def test_a_paragraph_without_any_reference_is_dropped(tmp_path):
    unreferenced = paragraph("Hat zwei Geschwister.")

    _, proposal = proposal_of(tmp_path, adding(SOZIAL, unreferenced))

    assert "Geschwister" not in text_of(proposal, SOZIAL)
    assert len(items_for(proposal, SOZIAL)) == 1


def test_a_section_the_notes_do_not_support_stays_empty_with_a_clarification_item(tmp_path):
    def unsupported(raw):
        target = next(s for s in raw["sections"] if s["title"] == FRUEHER)
        target["paragraphs"] = [paragraph("Zustand nach Operation.", "Operation 2019")]

    encounter, proposal = proposal_of(tmp_path, unsupported)

    assert text_of(proposal, FRUEHER) == ""
    assert len(items_for(proposal, FRUEHER)) == 1
    shown = encounter.accept().json()
    assert section(shown, 2)["empty"]
    assert [c["section"] for c in shown["clarifications"]] == [FRUEHER]


def test_a_section_the_model_leaves_empty_without_an_item_gets_one(tmp_path):
    def silent(raw):
        raw["clarifications"] = []
        next(s for s in raw["sections"] if s["title"] == SOZIAL)["paragraphs"] = []

    _, proposal = proposal_of(tmp_path, silent)

    assert items_for(proposal, SOZIAL) == [
        "Die Notizen enthalten keine Angaben für diesen Abschnitt."
    ]


def test_every_paragraph_of_every_fixture_proposal_has_a_reference_into_its_notes(client):
    for number in (CASE_ONE, CASE_TWO, CASE_THREE):
        encounter = Encounter(client, number)
        notes = encounter.notes()["notes"]
        proposal = encounter.generate().json()["proposal"]
        paragraphs = [p for s in proposal["sections"] for p in s["paragraphs"]]

        assert paragraphs
        for p in paragraphs:
            assert p["origin"] == "notes"
            assert p["references"]
            assert all(r["source"] == "notes" and r["quote"] in notes for r in p["references"])


def test_a_result_that_fails_structurally_is_a_failed_generation(tmp_path):
    def broken(raw):
        del raw["sections"][3]

    client = client_with(tmp_path, Altered(broken))
    encounter = Encounter(client)

    response = encounter.generate()

    assert response.status_code == 502
    assert encounter.draft()["proposal"] is None
    assert not encounter.draft()["has_draft"]


# ---- ADR 0001: what the model may not add ----

# A text a careless model adds, with a real passage of the first case as its only reference.
TEMPTED = [
    ("a ranking", SCHMERZ, "Der Rückenschmerz ist der Hauptschmerz.", "Seit 14 Monaten tiefer"),
    ("a ranking", SCHMERZ, "Der Rückenschmerz steht im Vordergrund.", "Seit 14 Monaten tiefer"),
    ("a diagnosis", SCHMERZ, "Verdacht auf eine Radikulopathie.", "Seit 14 Monaten tiefer"),
    ("a cause", FRUEHER, "Der Bandscheibenvorfall ist die Ursache der Schmerzen.", "Vor 3 Jahren"),
    ("a conversion", THERAPIE, "Ibuprofen 0,4 g bei Bedarf.", "Ibuprofen 400 mg bei Bedarf"),
    ("a dose", THERAPIE, "Ibuprofen 600 mg bei Bedarf.", "Ibuprofen 400 mg bei Bedarf"),
    ("an interaction", THERAPIE, "Eine Wechselwirkung ist unwahrscheinlich.", "Ibuprofen 400 mg"),
    ("a normal finding", BEFUND, "Neurologisch unauffällig.", "Lasègue negativ"),
    ("a justification", PLAN, "Die stationäre Aufnahme ist indiziert.", "Stationäre Aufnahme"),
    ("a recommendation", PLAN, "Eine Psychotherapie wird empfohlen.", "Stationäre Aufnahme"),
    ("an approval", INTERNIST, "Die Angaben sind vollständig und geprüft.", "kein Nikotin"),
    ("a provenance", SOZIAL, "Nach Angabe der Patientin lebt sie gern dort.", "Patientin lebt mit"),
    ("a date", FRUEHER, "Vor drei Jahren, im Frühjahr 2023.", "Vor 3 Jahren"),
    ("a score", SCHMERZ, "NRS 6 im Mittel, zusammen 12 Punkte.", "NRS 6 im Mittel"),
]


@pytest.mark.parametrize(
    ("kind", "title", "text", "quote"), TEMPTED, ids=[f"{t[0]}: {t[2]}" for t in TEMPTED]
)
def test_the_draft_does_not_get_what_the_notes_do_not_say(tmp_path, kind, title, text, quote):
    encounter, proposal = proposal_of(tmp_path, adding(title, paragraph(text, quote)))

    everything = "\n".join(s["text"] for s in proposal["sections"])
    assert text not in everything
    assert len(items_for(proposal, title)) == 1
    assert "Notizen" in items_for(proposal, title)[0]
    accepted = encounter.accept().json()
    assert text not in "\n".join(s["text"] for s in accepted["sections"])
    assert text not in "\n".join(s["text"] for s in encounter.handover()["sections"])


def test_the_main_pain_appears_only_for_the_pain_the_physician_named(tmp_path):
    named = paragraph(
        "Gonarthrose, Hauptschmerz.",
        "Linkes Knie, Gonarthrose, seit 5 Jahren belastungsabhängig",
        "Knieschmerz ist der Hauptschmerz",
        heading="Linkes Knie",
    )
    other = paragraph(
        "Seit der Jugend, Hauptschmerz.",
        "Migräne seit der Jugend, 3 Attacken pro Monat",
        heading="Migräne",
    )

    def both_called_main(raw):
        pain = next(s for s in raw["sections"] if s["title"] == SCHMERZ)
        pain["paragraphs"] = [named, other]

    encounter = Encounter(client_with(tmp_path, Altered(both_called_main)), CASE_TWO)
    notes = encounter.notes()["notes"]
    encounter.save_notes(notes + " Einschätzung: Knieschmerz ist der Hauptschmerz.")

    proposal = encounter.generate().json()["proposal"]

    assert text_of(proposal, SCHMERZ) == "Linkes Knie\nGonarthrose, Hauptschmerz."
    assert any("Hauptschmerz" in item for item in items_for(proposal, SCHMERZ))


# ---- input references and their loss on rewrite ----


def test_a_hand_rewritten_paragraph_has_no_reference_and_the_others_keep_theirs(client):
    encounter = Encounter(client, CASE_TWO)
    encounter.generate()
    encounter.accept()
    before = section(encounter.draft(), 3)
    assert [p["origin"] for p in before["paragraphs"]] == ["notes", "notes", "notes"]

    text = before["text"].replace("Physiotherapie 2025.", "Physiotherapie 2025, zweimal pro Woche.")
    shown = encounter.edit(3, text).json()

    edited = section(shown, 3)
    assert edited["manual"]
    assert edited["text"] == text
    assert [p["origin"] for p in edited["paragraphs"]] == ["notes", "notes", "hand"]
    assert [bool(p["references"]) for p in edited["paragraphs"]] == [True, True, False]
    assert section(shown, 4)["paragraphs"][0]["origin"] == "notes"


def test_a_rewritten_section_has_only_hand_paragraphs_and_stays_so_after_reload(client):
    encounter = Encounter(client, CASE_ONE)
    encounter.generate()
    encounter.accept()

    encounter.edit(1, "Lebt allein.")

    [only] = section(encounter.draft(), 1)["paragraphs"]
    assert only["origin"] == "hand"
    assert only["references"] == []


def test_a_paragraph_the_physician_adds_has_no_reference(client):
    encounter = Encounter(client, CASE_ONE)
    encounter.generate()
    encounter.accept()
    text = section(encounter.draft(), 1)["text"] + "\n\nSeit dem Umzug im Mai allein."

    shown = encounter.edit(1, text).json()

    assert [p["origin"] for p in section(shown, 1)["paragraphs"]] == ["notes", "hand"]


def test_a_section_the_physician_kept_by_hand_keeps_no_reference_through_a_new_acceptance(client):
    encounter = Encounter(client, CASE_ONE)
    encounter.generate()
    encounter.accept()
    encounter.edit(1, "Lebt allein.")

    encounter.generate()
    shown = encounter.accept().json()

    assert section(shown, 1)["paragraphs"][0]["origin"] == "hand"
    assert section(shown, 2)["paragraphs"][0]["origin"] == "notes"


def test_the_notes_passage_a_reference_quotes_is_word_for_word_in_the_notes(client):
    encounter = Encounter(client, CASE_TWO)
    notes = encounter.notes()["notes"]
    proposal = encounter.generate().json()["proposal"]
    schmerz = next(s for s in proposal["sections"] if s["title"] == SCHMERZ)

    quotes = [r["quote"] for p in schmerz["paragraphs"] for r in p["references"]]

    assert "Migräne seit der Jugend, 3 Attacken pro Monat" in quotes
    assert all(q in notes for q in quotes)


# ---- the clarification list ----


def test_the_list_is_the_proposals_after_acceptance_and_stays_until_the_next_acceptance(client):
    encounter = Encounter(client, CASE_THREE)
    proposal = encounter.generate().json()["proposal"]
    assert encounter.draft()["clarifications"] == []

    accepted = encounter.accept().json()

    assert accepted["clarifications"] == proposal["clarifications"]
    assert len(accepted["clarifications"]) >= 5
    encounter.generate()
    assert encounter.draft()["clarifications"] == accepted["clarifications"]
    encounter.discard()
    assert encounter.draft()["clarifications"] == accepted["clarifications"]


def test_a_manual_edit_of_every_section_removes_no_item(client):
    encounter = Encounter(client, CASE_THREE)
    encounter.generate()
    items = encounter.accept().json()["clarifications"]

    for number in range(1, 8):
        encounter.edit(number, f"Ergänzt von Hand, Abschnitt {number}.")

    shown = encounter.draft()
    assert all(s["manual"] for s in shown["sections"])
    assert shown["clarifications"] == items


def test_the_list_survives_a_restart(tmp_path):
    first = Encounter(client_with(tmp_path), CASE_THREE)
    first.generate()
    items = first.accept().json()["clarifications"]
    first.edit(1, "Lebt allein.")

    again = first.through(client_with(tmp_path))

    assert again.draft()["clarifications"] == items
    assert section(again.draft(), 1)["manual"]


def test_the_next_acceptance_replaces_the_list_with_the_new_proposals(tmp_path):
    def cleared(raw):
        raw["clarifications"] = []

    client = client_with(tmp_path)
    encounter = Encounter(client, CASE_TWO)
    encounter.generate()
    assert encounter.accept().json()["clarifications"]
    second = Encounter(client_with(tmp_path, Altered(cleared)), CASE_TWO, base=encounter.base)
    proposal = second.generate().json()["proposal"]

    shown = second.accept().json()

    assert shown["clarifications"] == proposal["clarifications"]
    assert shown["clarifications"] == []


# ---- the third case leaves its gaps ----


def test_the_third_case_yields_its_gaps_and_the_clarification_items_for_them(client):
    gaps = Encounter(client, CASE_THREE)

    proposal = gaps.generate().json()["proposal"]

    assert text_of(proposal, SOZIAL) == ""
    assert text_of(proposal, INTERNIST) == ""
    assert text_of(proposal, PLAN) == ""
    therapy = text_of(proposal, THERAPIE)
    assert "Dosis unklar" in therapy
    assert "50 mg" not in therapy and "100 mg" not in therapy
    assert "Beginn unklar" in text_of(proposal, SCHMERZ)
    assert items_for(proposal, THERAPIE) == [
        "Die Angaben zu Tramadol widersprechen sich: 50 mg oder 100 mg zweimal täglich."
    ]
    assert items_for(proposal, SCHMERZ) == [
        "Der Beginn ist unklar: seit dem Sommer oder länger. Welcher Zeitpunkt gilt für den "
        "Sturz im Frühjahr?"
    ]
    assert items_for(proposal, PLAN) == [
        "Die Begründung für den stationären Aufenthalt fehlt, ebenso Ziele und Behandlungsplan."
    ]
    assert items_for(proposal, SOZIAL) == ["Die Notizen enthalten keine Sozialanamnese."]


def test_a_model_that_fills_the_third_cases_gaps_loses_what_it_filled_in(tmp_path):
    filled = [
        (SOZIAL, "Lebt allein.", "Lebt allein"),
        (THERAPIE, "Tramadol retard 100 mg zweimal täglich.", "steht 100 mg zweimal täglich"),
        (PLAN, "Die stationäre Aufnahme ist wegen der Chronifizierung notwendig.", "Sturz"),
        (
            PLAN,
            "Die Aufnahme erfolgt wegen des Sturzes im Frühjahr.",
            "Seit einem Sturz im Frühjahr schlechter.",
        ),
    ]

    def fill(raw):
        for title, text, quote in filled:
            adding(title, paragraph(text, quote))(raw)

    _, proposal = proposal_of(tmp_path, fill, CASE_THREE)

    for title, text, _ in filled:
        assert text not in text_of(proposal, title)
    assert text_of(proposal, SOZIAL) == ""
    assert text_of(proposal, PLAN) == ""
    assert "Dosis unklar" in text_of(proposal, THERAPIE)
