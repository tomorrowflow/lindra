"""What the physician sees of dictation on the pages: the persistent control and the overlay.

Recording, the overlay's states and the microphone itself run in the browser and are measured
in a real one by `scripts/screenshots.py`. These tests state what the server renders: the
control on every step of an encounter, disabled where no encounter is selected, and the
overlay's controls and texts, outside the action bar so the bar keeps its layout (ADR 0008).
"""

import re

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


@pytest.fixture
def review(browser, api_client):
    return Review(browser, api_client)


def mic(page):
    return [b for b in Buttons(action_bar(page)).buttons if b["text"].strip() == "Diktat"]


def overlay(page):
    return page.split('<dialog class="dictation ', 1)[1].split("</dialog>", 1)[0]


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
    overview = review.browser.get(review.page_base.rsplit("/kontakte/", 1)[0])

    for page in (browser.get("/"), overview):
        assert [b["disabled"] for b in mic(page.text)] == [True]
        assert '<dialog class="dictation ' not in page.text


def test_the_control_opens_the_overlay_and_is_the_only_way_in(review):
    page = review.get("/notizen").text

    assert "data-dictate" in action_bar(page)
    assert 'aria-haspopup="dialog"' in action_bar(page)
    # Nothing on the page starts a recording by itself: no autostart, no hidden capture input.
    assert "autostart" not in page and "capture=" not in page


def test_the_overlay_is_a_dialog_outside_the_action_bar_with_its_addresses(review):
    page = review.get("/notizen").text

    assert "<dialog" not in main_of(page)
    shown = overlay(page)
    base = review.api_base
    assert f'data-transcript-url="{base}/dictation/transcript"' in shown
    assert f'data-accept-url="{base}/dictation/accept"' in shown
    assert f'data-notes-url="{review.page_base}/notizen"' in shown


def test_the_overlay_has_the_controls_of_all_its_states(review):
    shown = overlay(review.step(3).text)

    labels = [b["text"].strip() for b in Buttons(shown).buttons]
    for label in OVERLAY_LABELS:
        assert label in labels
    assert "Text wird erstellt" in shown


def test_the_overlay_names_each_state_in_words_and_marks_the_active_one_for_the_script(review):
    shown = overlay(review.get("/notizen").text)

    for state in ("starting", "recording", "transcribing", "reviewing", "failed"):
        assert f'data-state="{state}"' in shown
    for words in (
        "Mikrofon wird freigegeben",
        "Aufnahme läuft",
        "Text wird erstellt",
        "Text prüfen",
    ):
        assert words in shown


def test_the_overlay_announces_the_outdated_proposal_in_the_review_state(review):
    shown = overlay(review.get("/notizen").text)

    assert "Der Vorschlag zu diesem Kontakt wird dadurch veraltet" in shown
    assert "data-outdates hidden" in shown


def test_the_overlay_asks_for_the_transcript_to_be_edited_in_a_text_area(review):
    shown = overlay(review.get("/notizen").text)

    assert re.search(r"<textarea[^>]*data-transcript", shown)
    assert 'lang="de"' in shown


def test_the_overlay_script_uses_only_the_service_for_speech_recognition(browser):
    script = browser.get("/static/js/dictation.js").text

    assert "SpeechRecognition" not in script
    assert "webkitSpeech" not in script
    assert "getUserMedia" in script
