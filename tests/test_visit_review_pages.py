"""What the physician sees in a visit's review: four steps, historical references, the refused
proposal and the changed-background marker (ADR 0008, ADR 0010).

The pages are server-rendered; the browser-side parts are measured in a real browser by
`scripts/screenshots.py`. Cases are created through the API with `build`, so no draft exists
until a test accepts one.
"""

import re

import pytest

from lindra.cast import VISIT_SECTIONS
from tests.test_review_pages import (
    body_of,
    main_of,
    proposal_pane,
    sidebar_of,
    steps_in_sidebar,
)
from tests.test_visit_review_api import (
    BACKGROUND_CHANGED,
    OUTDATED_BY_BACKGROUND,
    build,
)

VERLAUF, BEFUNDE, EINSCHAETZUNG, VORGEHEN = VISIT_SECTIONS


class Pages:
    """A built cast case with its pages."""

    def __init__(self, browser, api_client, number="FIK-2026-001"):
        self.browser = browser
        self.built = build(api_client, number)

    def base(self, key):
        return f"/faelle/{self.built.case_id}/kontakte/{self.built[key].id}"

    def get(self, key, suffix):
        return self.browser.get(self.base(key) + suffix)

    def step(self, key, number):
        return self.get(key, f"/abschnitte/{number}")

    def final(self, key):
        return self.get(key, "/abschluss")

    def sidebar_badge(self, key, page):
        """The label of the state badge the sidebar shows beside an encounter."""
        link = re.escape(f'href="{self.base(key)}/notizen"')
        found = re.search(
            link + r'[^>]*>.*?</a>\s*<button class="badge-button"[^>]*aria-label="([^"]*)"',
            sidebar_of(page),
            re.S,
        )
        return found.group(1)


@pytest.fixture
def pages(browser, api_client):
    return Pages(browser, api_client)


def accepted_with_background(pages):
    """The assessment and the visit accepted, then the assessment accepted again."""
    pages.built["assessment"].accepted()
    pages.built["visit-1"].accepted()
    pages.built["assessment"].accepted()


# ---- the steps of a visit ----


def test_a_visit_has_a_notes_step_four_section_steps_and_a_final_step(pages):
    steps = steps_in_sidebar(pages.get("visit-1", "/notizen").text)

    assert [(n, label) for n, label, _ in steps] == [
        (1, "Notizen"),
        *[(i + 2, title) for i, title in enumerate(VISIT_SECTIONS)],
        (6, "Übergabe"),
    ]


def test_the_final_step_of_a_visit_is_uebernehmen_while_a_proposal_is_pending(pages):
    pages.built["visit-1"].generate()

    steps = steps_in_sidebar(pages.get("visit-1", "/notizen").text)

    assert steps[-1][:2] == (6, "Übernehmen")


def test_a_visit_has_no_fifth_section_step(pages):
    assert pages.step("visit-1", 4).status_code == 200
    assert pages.step("visit-1", 5).status_code == 404


def test_a_visit_step_has_the_generate_button_and_the_same_action_bar(pages):
    page = pages.step("visit-1", 1).text

    assert "data-generate" in page
    assert "Entwurf erzeugen" in page
    assert 'aria-label="Vorschlag verwerfen"' not in page


# ---- historical references ----


def test_the_proposal_shows_aus_frueherem_kontakt_beside_aus_notizen(pages):
    pages.built["assessment"].accepted()
    pages.built["visit-1"].generate()

    pane = proposal_pane(pages.step("visit-1", 1).text)

    assert "aus Notizen" in pane
    assert "aus früherem Kontakt" in pane
    assert pane.count("origin-earlier") == 1


def test_tapping_the_historical_reference_reveals_the_quote_and_names_encounter_and_date(pages):
    pages.built["assessment"].accepted()
    pages.built["visit-1"].generate()

    pane = proposal_pane(pages.step("visit-1", 1).text)
    earlier = pane.split('<details class="origin origin-earlier">', 1)[1].split("</details>", 1)[0]

    assert "Aufnahmeassessment, 05.10.2026 09:00" in earlier
    assert "Ibuprofen 400 mg bei Bedarf, bis zu zwei Tabletten täglich, Wirkung gering." in earlier
    assert earlier.count("<blockquote") == 1


def test_today_s_observations_keep_aus_notizen_and_never_say_aus_frueherem_kontakt(pages):
    pages.built["assessment"].accepted()
    pages.built["visit-1"].generate()

    for number in (2, 3, 4):
        pane = proposal_pane(pages.step("visit-1", number).text)
        assert "aus Notizen" in pane
        assert "aus früherem Kontakt" not in pane


def test_the_two_kinds_of_reference_are_marked_apart(pages):
    pages.built["assessment"].accepted()
    pages.built["visit-1"].generate()

    pane = proposal_pane(pages.step("visit-1", 1).text)

    today = pane.split('<details class="origin">', 1)[1].split("</details>", 1)[0]
    assert "file-text" not in today and "origin-earlier" not in today
    earlier = pane.split('<details class="origin origin-earlier">', 1)[1].split("</details>", 1)[0]
    assert "origin-caption" in earlier and "origin-caption" not in today


def test_the_draft_pane_lists_the_historical_reference_of_an_accepted_paragraph(pages):
    pages.built["assessment"].accepted()
    pages.built["visit-1"].accepted()

    origins = pages.step("visit-1", 1).text.split('id="section-origins"', 1)[1]

    assert origins.count("aus früherem Kontakt") == 1
    assert origins.count("aus Notizen") == 1
    assert "Aufnahmeassessment, 05.10.2026 09:00" in origins


def test_a_rewritten_historical_paragraph_loses_its_reference_in_the_origins_fragment(pages):
    pages.built["assessment"].accepted()
    visit = pages.built["visit-1"]
    text = visit.accepted()["sections"][0]["text"]
    visit.edit(1, text.replace("Zuvor: Ibuprofen 400 mg", "Zuvor: Ibuprofen 500 mg"))

    fragment = pages.get("visit-1", "/abschnitte/1/herkunft").text

    assert "aus früherem Kontakt" not in fragment
    assert "von Hand, keine Herkunft" in fragment


def test_a_visit_without_background_shows_no_historical_reference(pages):
    pages.built["visit-1"].generate()

    pane = proposal_pane(pages.step("visit-1", 1).text)

    assert "aus Notizen" in pane
    assert "aus früherem Kontakt" not in pane


# ---- the proposal refused by its background ----


def refused_proposal(pages):
    pages.built["assessment"].accepted()
    pages.built["visit-1"].generate()
    pages.built["assessment"].accepted()


def test_the_outdated_proposal_disables_acceptance_and_spells_out_the_reason(pages):
    refused_proposal(pages)

    page = pages.final("visit-1").text

    assert OUTDATED_BY_BACKGROUND in page
    assert "data-outdated-reason" in page
    accept = re.search(r'<button class="btn btn-primary action-button" type="submit"([^>]*)>', page)
    assert "disabled" in accept.group(1)
    assert 'aria-describedby="outdated-reason"' in accept.group(1)


def test_the_outdated_proposal_stays_visible_on_the_section_steps_with_veraltet(pages):
    refused_proposal(pages)

    for number in (1, 2, 3, 4):
        page = pages.step("visit-1", number).text
        assert "Veraltet" in body_of(page)
        assert OUTDATED_BY_BACKGROUND in page
        assert "Hintergrund seit diesem Vorschlag geändert" in body_of(page)
    assert "Zuvor: Ibuprofen 400 mg" in proposal_pane(pages.step("visit-1", 1).text)


def test_accepting_the_outdated_proposal_by_the_form_is_refused_with_the_reason(pages):
    refused_proposal(pages)

    response = pages.browser.post(pages.base("visit-1") + "/abschluss/uebernehmen")

    assert response.status_code == 409
    assert OUTDATED_BY_BACKGROUND in response.text
    assert pages.built["visit-1"].draft()["has_draft"] is False


def test_the_sidebar_names_the_proposal_as_outdated_by_the_background(pages):
    refused_proposal(pages)

    label = pages.sidebar_badge("visit-1", pages.step("visit-1", 1).text)

    assert label == "Zustand: Vorschlag veraltet, Hintergrund geändert"


def test_discarding_and_generating_again_makes_the_proposal_acceptable(pages):
    refused_proposal(pages)
    pages.browser.post(pages.base("visit-1") + "/abschluss/verwerfen")
    pages.built["visit-1"].generate()

    page = pages.final("visit-1").text

    assert OUTDATED_BY_BACKGROUND not in page
    accept = re.search(r'<button class="btn btn-primary action-button" type="submit"([^>]*)>', page)
    assert "disabled" not in accept.group(1)


# ---- the draft marked "Hintergrund seit Erstellung geändert" ----


def test_every_step_of_the_visit_shows_the_marker_and_the_text_is_kept(pages):
    accepted_with_background(pages)
    kept = pages.built["visit-1"].draft()["sections"][0]["text"]

    for page in (
        pages.get("visit-1", "/notizen").text,
        pages.step("visit-1", 1).text,
        pages.step("visit-1", 4).text,
        pages.final("visit-1").text,
    ):
        assert BACKGROUND_CHANGED in body_of(page)
    assert kept in pages.step("visit-1", 1).text.replace("&#39;", "'")


def test_the_marker_explains_itself_on_tap_and_names_no_section(pages):
    accepted_with_background(pages)

    page = pages.step("visit-1", 1).text
    marker = page.split("data-background-changed", 1)[1].split("</div>", 1)[0]

    assert 'aria-expanded="false"' in marker and 'aria-controls="background-explanation"' in marker
    assert 'id="background-explanation" hidden' in marker
    assert "nichts von selbst neu" in marker
    assert not any(title in marker for title in VISIT_SECTIONS)


def test_the_sidebar_and_the_overview_show_the_background_badge_on_the_visit(pages):
    accepted_with_background(pages)

    overview = pages.browser.get(f"/faelle/{pages.built.case_id}").text
    step = pages.step("visit-1", 1).text

    assert pages.sidebar_badge("visit-1", step) == f"Zustand: {BACKGROUND_CHANGED}"
    assert pages.sidebar_badge("assessment", step) == "Zustand: Entwurf vorhanden"
    assert f"Zustand: {BACKGROUND_CHANGED}" in main_of(overview)


def test_the_assessment_never_shows_the_background_marker(pages):
    accepted_with_background(pages)

    page = pages.step("assessment", 1).text

    assert BACKGROUND_CHANGED not in body_of(page)


def test_a_visit_whose_background_did_not_change_shows_no_marker(pages):
    pages.built["assessment"].accepted()
    pages.built["visit-1"].accepted()

    page = pages.step("visit-1", 1).text

    assert BACKGROUND_CHANGED not in body_of(page)
    assert pages.sidebar_badge("visit-1", page) == "Zustand: Entwurf vorhanden"


def test_regenerating_and_accepting_clears_the_marker_on_the_page(pages):
    accepted_with_background(pages)
    pages.built["visit-1"].generate()
    pages.built["visit-1"].accept()

    page = pages.step("visit-1", 1).text

    assert BACKGROUND_CHANGED not in body_of(page)


def test_saving_notes_answers_with_the_badge_the_visit_has_now(pages, api_client):
    accepted_with_background(pages)
    visit = pages.built["visit-1"]

    answer = visit.save_notes(visit.encounter()["notes"]).json()

    assert answer["badge"]["state"] == "background_changed"
    assert answer["badge"]["label"] == BACKGROUND_CHANGED
    assert answer["background_changed"] is True


def test_the_notes_step_carries_an_icon_for_the_background_badge(pages):
    page = pages.get("visit-1", "/notizen").text

    assert page.count('<span data-icon="layers">') == 1


# ---- clarification items, nothing to copy ----


def test_the_contradiction_with_the_background_is_on_the_section_step_naming_both(pages):
    pages.built["assessment"].accepted()
    pages.built["visit-1"].accepted()

    page = pages.step("visit-1", 1).text

    asked = page.split('id="clarifications-title"', 1)[1]
    assert "Aufnahmeassessment vom 05.10.2026" in asked
    assert "strahlt der Schmerz nicht ins Bein aus" in asked
    assert "Ausstrahlung ins linke Bein" in asked


def test_a_visit_without_a_decision_says_so_in_the_section_and_on_the_list(browser, api_client):
    pages = Pages(browser, api_client, "FIK-2026-003")
    pages.built["assessment"].accepted()
    pages.built["visit-1"].accepted()

    page = pages.step("visit-1", 4).text

    assert "Für diese Visite ist kein Vorgehen und kein Ziel notiert." in page
    assert pages.step("visit-1", 4).text.count("data-section") >= 1
    draft_text = re.search(r"<textarea[^>]*data-section[^>]*>(.*?)</textarea>", page, re.S)
    assert draft_text.group(1).strip() == ""


def test_a_visit_without_an_accepted_draft_says_there_is_nothing_to_copy(pages):
    page = pages.final("visit-1").text

    assert "data-nothing-to-copy" in page
    assert "data-copy" not in body_of(page)


def test_the_handover_of_a_visit_has_one_copy_control_per_section(pages):
    pages.built["assessment"].accepted()
    pages.built["visit-1"].accepted()

    page = pages.final("visit-1").text

    assert page.count("data-copy-text=") == 4
    for title in VISIT_SECTIONS:
        assert f'aria-label="{title} kopieren"' in page
