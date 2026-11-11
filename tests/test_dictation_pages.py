"""What the physician sees of dictation on the pages: the persistent control and the overlay.

Recording, the overlay's states, what blocks behind it and the microphone itself run in the
browser and are measured in a real one by `scripts/screenshots.py`. These tests state what the
server shows: the control on every step of an encounter, disabled where no encounter is
selected, and the overlay's buttons and words, kept out of the action bar so the bar keeps its
layout (ADR 0008).
"""

import pytest

from tests.test_case_pages import Buttons
from tests.test_review_pages import Review, action_bar, main_of

OVERLAY_LABELS = [
    "Aufnahme beenden",
    "In Notizen übernehmen",
    "Verwerfen",
    "Erneut versuchen",
    "Schließen",
]
OVERLAY_WORDS = [
    "Mikrofon wird freigegeben",
    "Aufnahme läuft",
    "Text wird erstellt",
    "Text prüfen",
    "Der Vorschlag zu diesem Kontakt wird dadurch veraltet",
    "Ihre Notizen sind unverändert",
]
OVERLAY_START = '<dialog class="dictation '


@pytest.fixture
def review(browser, api_client):
    return Review(browser, api_client)


def mic(page):
    return [b for b in Buttons(action_bar(page)).buttons if b["text"].strip() == "Diktat"]


def overlay(page):
    return page.split(OVERLAY_START, 1)[1].split("</dialog>", 1)[0]


def test_the_control_is_enabled_on_every_step_of_an_assessment(review):
    pages = [review.get("/notizen"), review.step(1), review.step(4), review.step(7)]
    pages += [review.final()]

    for response in pages:
        assert [b["disabled"] for b in mic(response.text)] == [False]


def test_the_control_is_enabled_on_the_notes_step_of_a_visit(browser, api_client):
    visit = Review(browser, api_client, kind="visit")

    assert [b["disabled"] for b in mic(visit.get("/notizen").text)] == [False]


def test_the_control_stays_enabled_while_a_proposal_is_pending_and_on_the_handover(review):
    review.generate()
    assert [b["disabled"] for b in mic(review.final().text)] == [False]
    review.accept()

    assert [b["disabled"] for b in mic(review.final().text)] == [False]


def test_the_control_is_disabled_where_no_encounter_is_selected(browser, api_client):
    review = Review(browser, api_client)
    overview = browser.get(review.page_base.rsplit("/kontakte/", 1)[0])

    for page in (browser.get("/"), overview):
        assert [b["disabled"] for b in mic(page.text)] == [True]
        assert OVERLAY_START not in page.text


def test_the_overlay_is_not_part_of_the_step_or_its_action_bar(review):
    page = review.get("/notizen").text

    assert "<dialog" not in main_of(page)


def test_the_overlay_has_the_buttons_and_words_of_all_its_states(review):
    shown = overlay(review.step(3).text)

    labels = [b["text"].strip() for b in Buttons(shown).buttons]
    for label in OVERLAY_LABELS:
        assert label in labels
    for words in OVERLAY_WORDS:
        assert words in shown


def test_the_overlay_names_the_encounter_it_dictates_into(review):
    shown = overlay(review.get("/notizen").text)

    assert "FIK-2026-001, Aufnahmeassessment 05.10.2026 09:00" in shown
