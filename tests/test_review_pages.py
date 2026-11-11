"""What the physician sees in the review: one step per section, Übernehmen and Übergabe.

The pages are server-rendered; accepting and discarding are form posts. The browser-side parts
(autosave of a section, the generate button, the clipboard) are measured in a real browser by
`scripts/screenshots.py`. The clock stands at 10.11.2026 14:30 (`tests/conftest.py`).
"""

import html
import re

import pytest
from fastapi.testclient import TestClient

from lindra.app import create_app
from lindra.cast import ASSESSMENT_SECTIONS
from lindra.config import Settings
from tests.conftest import NOW, TOKEN
from tests.test_case_pages import Buttons
from tests.test_cases_api import seeded_case
from tests.test_review_api import AnswersInProse, Unreachable

OUTDATED = "Veraltet: Notizen seit diesem Vorschlag geändert"


class Review:
    """The seeded first fictional assessment, reached as pages and as API."""

    def __init__(self, browser, api_client, number="FIK-2026-001", kind="assessment"):
        case = seeded_case(api_client, number)
        found = next(e for e in case["encounters"] if e["kind"] == kind)
        self.browser, self.api = browser, api_client
        self.page_base = f"/faelle/{case['id']}/kontakte/{found['id']}"
        self.api_base = f"/api/cases/{case['id']}/encounters/{found['id']}"

    def get(self, suffix, **kwargs):
        return self.browser.get(self.page_base + suffix, **kwargs)

    def step(self, number):
        return self.get(f"/abschnitte/{number}")

    def final(self):
        return self.get("/abschluss")

    def generate(self):
        return self.api.post(f"{self.api_base}/generate")

    def accept(self):
        return self.api.post(f"{self.api_base}/proposal/accept")

    def edit(self, number, text):
        return self.api.put(f"{self.api_base}/draft/sections/{number}", json={"text": text})

    def save_notes(self, text):
        return self.api.put(f"{self.api_base}/notes", json={"notes": text})

    def notes(self):
        return self.api.get(self.api_base).json()["notes"]


@pytest.fixture
def review(browser, api_client):
    return Review(browser, api_client)


def sidebar_of(page):
    return page.split("<nav", 1)[1].split("</nav>", 1)[0]


def main_of(page):
    return page.split("<main", 1)[1].split("</main>", 1)[0]


def body_of(page):
    """The scrolling part of a step, without the action bar."""
    return main_of(page).split('<footer class="action-bar">', 1)[0]


def action_bar(page):
    return page.split('<footer class="action-bar">', 1)[1].split("</footer>", 1)[0]


def bar_controls(page):
    """The controls of the action bar in order: their classes (size and place) and labels."""
    bar = action_bar(page)
    return re.findall(r'<(?:a|button)[^>]* class="(btn [^"]*)"', bar), re.findall(
        r"<span>([^<]*)</span>", bar
    )


def steps_in_sidebar(page):
    pattern = (
        r'<a class="step-link[^"]*" href="([^"]+)"[^>]*>\s*'
        r'<span class="step-number">(\d+)</span>\s*'
        r'<span class="step-label">([^<]*)</span>'
    )
    return [(int(n), label.strip(), href) for href, n, label in re.findall(pattern, page)]


def textarea_text(page, marker):
    """What the browser puts in the text area: an HTML parser drops one leading line break."""
    area = re.search(rf"<textarea[^>]*{marker}[^>]*>(.*?)</textarea>", page, re.S)
    text = html.unescape(area.group(1))
    return text[1:] if text.startswith("\n") else text


def proposal_pane(page):
    return page.split('id="pane-proposal"', 1)[1].split("</section>", 1)[0]


# ---- the steps of an encounter ----


def test_an_assessment_has_a_notes_step_seven_section_steps_and_a_final_step(review):
    steps = steps_in_sidebar(review.get("/notizen").text)

    assert [(n, label) for n, label, _ in steps] == [
        (1, "Notizen"),
        *[(i + 2, title) for i, title in enumerate(ASSESSMENT_SECTIONS)],
        (9, "Übergabe"),
    ]
    assert steps[1][2] == review.page_base + "/abschnitte/1"
    assert steps[-1][2] == review.page_base + "/abschluss"


def test_the_final_step_is_called_uebernehmen_while_a_proposal_is_pending(review):
    review.generate()

    steps = steps_in_sidebar(review.get("/notizen").text)

    assert steps[-1][:2] == (9, "Übernehmen")


def test_every_step_is_reachable_directly_in_any_order(review):
    for number in (7, 1, 4, 2):
        assert review.step(number).status_code == 200
    assert review.final().status_code == 200
    assert review.get("/notizen").status_code == 200


def test_the_current_step_is_marked_in_the_sidebar(review):
    page = review.step(3).text

    current = re.findall(r'<a class="step-link current"[^>]*>.*?step-label">([^<]*)<', page, re.S)

    assert current == [ASSESSMENT_SECTIONS[2]]


def test_a_section_number_that_does_not_exist_is_not_found(review):
    response = review.step(8)

    assert response.status_code == 404
    assert "Abschnitt nicht gefunden" in response.text


def test_a_case_or_encounter_that_does_not_exist_is_not_found_with_its_reason(review):
    assert "Fall nicht gefunden" in review.browser.get("/faelle/999/kontakte/1/abschluss").text
    other = review.page_base.rsplit("/", 1)[0] + "/9999/abschluss"
    response = review.browser.get(other)
    assert response.status_code == 404
    assert "Kontakt nicht gefunden" in response.text


def test_opening_every_step_generates_nothing(review):
    review.get("/notizen")
    for number in range(1, 8):
        review.step(number)
    review.final()

    shown = review.api.get(f"{review.api_base}/draft").json()
    assert shown["proposal"] is None and not shown["has_draft"]


def test_the_action_bar_has_the_same_controls_in_the_same_places_on_every_step(review):
    notes = bar_controls(review.get("/notizen").text)

    for number in (1, 4, 7):
        assert bar_controls(review.step(number).text) == notes
    assert bar_controls(review.final().text) == notes
    classes, labels = notes
    assert labels == ["Zurück", "Weiter", "Verwerfen", "Kopieren", "Diktat"]
    assert all("action-button" in c for c in classes)
    review.generate()
    assert bar_controls(review.step(2).text) == notes
    assert bar_controls(review.final().text)[1] == [
        "Zurück",
        "Übernehmen",
        "Verwerfen",
        "Kopieren",
        "Diktat",
    ]


def test_back_and_next_walk_the_steps_and_are_disabled_at_the_ends(review):
    first = Buttons(review.get("/notizen").text)
    assert first.find("Zurück")[0]["disabled"]
    assert 'href="' + review.page_base + '/abschnitte/1"' in action_bar(review.get("/notizen").text)

    middle = action_bar(review.step(3).text)
    assert f'href="{review.page_base}/abschnitte/2"' in middle
    assert f'href="{review.page_base}/abschnitte/4"' in middle

    last = action_bar(review.step(7).text)
    assert f'href="{review.page_base}/abschluss"' in last
    final = Buttons(review.final().text)
    assert final.find("Weiter")[0]["disabled"]
    assert f'href="{review.page_base}/abschnitte/7"' in action_bar(review.final().text)


# ---- the section step ----


def test_a_section_step_shows_the_current_draft_and_the_proposal_side_by_side(review):
    review.generate()
    review.accept()
    review.edit(2, "Meine Fassung.")
    review.generate()
    page = review.step(2).text

    assert "Aktueller Entwurf" in page
    assert textarea_text(page, "data-section") == "Meine Fassung."
    assert "Bandscheibenvorfall L4/5 vor drei Jahren" in proposal_pane(page)
    assert page.count('<section class="pane') == 2


def test_the_draft_pane_is_empty_and_says_so_before_any_draft(review):
    page = review.step(1).text

    assert textarea_text(page, "data-section") == ""
    assert "Noch kein Entwurf" in page
    assert "Noch kein Vorschlag" in proposal_pane(page)


def test_the_proposal_pane_shows_subsection_headings_once_each(review):
    review.generate()

    pane = proposal_pane(review.step(3).text)

    assert pane.count("Aktuelle Medikation") == 1
    assert pane.count("Frühere nichtmedikamentöse Behandlungen") == 1
    assert pane.index("Aktuelle Medikation") < pane.index("Ibuprofen")


def test_a_section_the_proposal_leaves_empty_says_so(browser, api_client):
    gaps = Review(browser, api_client, "FIK-2026-003")
    gaps.generate()

    assert "Der Vorschlag lässt diesen Abschnitt leer" in proposal_pane(gaps.step(1).text)


def test_the_section_step_shows_the_clarification_items_of_that_section_only(browser, api_client):
    second = Review(browser, api_client, "FIK-2026-002")
    second.generate()
    second.accept()

    pain = second.step(4).text
    social = second.step(1).text

    assert "Welcher der drei Schmerzen steht im Vordergrund" in body_of(pain)
    assert "Welcher der drei Schmerzen" not in body_of(social)
    assert "Zu klären" in pain and "Zu klären" not in social


def test_the_section_step_has_a_one_line_state_with_more_and_no_long_sentence(review):
    page = review.step(1).text

    state = re.search(r'<div class="state-line">(.*?)</div>', page, re.S).group(1)
    assert "Noch kein Entwurf" in state
    assert ">Mehr<" in state
    assert 'aria-controls="state-explanation-1"' in state
    assert re.search(r'id="state-explanation-1" hidden>[^<]+</p>', page)


def badge_labels(page):
    head = page.split('id="section-head"', 1)[1].split('class="state-line"', 1)[0]
    return re.findall(r'class="section-badge" type="button" aria-label="([^"]+)"', head)


def test_a_section_the_proposal_would_change_carries_the_proposed_change_badge(review):
    review.generate()

    page = review.step(2).text

    assert badge_labels(page) == ["Vorschlag ändert diesen Abschnitt"]
    line = re.search(r'<span class="state-text">([^<]*)</span>', page).group(1)
    assert line == "Vorschlag ändert diesen Abschnitt"


def test_a_section_whose_proposal_text_equals_the_draft_carries_no_proposed_change_badge(review):
    review.generate()
    review.accept()
    review.generate()

    page = review.step(2).text

    assert badge_labels(page) == []
    assert "Vorschlag gleicht dem Entwurf" in page


def test_a_hand_edited_section_carries_only_the_manual_badge_while_a_proposal_is_pending(review):
    review.generate()
    review.accept()
    review.edit(1, "Meine Fassung.")
    review.generate()

    page = review.step(1).text

    assert badge_labels(page) == ["Manuell bearbeitet"]
    assert "Manuell bearbeitet, der Vorschlag ersetzt den Abschnitt nicht" in page


def test_the_open_question_and_copied_badges_appear_on_their_sections(browser, api_client):
    second = Review(browser, api_client, "FIK-2026-002")
    second.generate()
    second.accept()
    api_client.post(f"{second.api_base}/draft/sections/4/copied")

    assert badge_labels(second.step(4).text) == ["Offene Frage", "Kopiert"]
    assert badge_labels(second.step(1).text) == []


def test_a_retained_section_carries_nicht_aktualisiert_spelled_out_on_its_step(review):
    review.generate()
    review.edit(2, "Meine Fassung.")
    review.accept()

    page = review.step(2).text

    head = page.split('id="section-head"', 1)[1].split('class="state-line"', 1)[0]
    assert 'aria-label="Nicht aktualisiert"' in head
    assert '<span class="badge-word">Nicht aktualisiert</span>' in head
    assert '<span class="badge-word">Manuell' not in head
    other = review.step(3).text
    assert "Nicht aktualisiert" not in other.split('id="section-head"', 1)[1].split("state-line")[0]


def test_the_sidebar_step_of_a_retained_section_shows_its_badges(review):
    review.generate()
    review.edit(2, "Meine Fassung.")
    review.accept()

    sidebar = sidebar_of(review.step(1).text)

    second = sidebar.split('class="step-number">3<', 1)[1].split("</li>", 1)[0]
    assert "Nicht aktualisiert" in second and "Manuell bearbeitet" in second
    third = sidebar.split('class="step-number">4<', 1)[1].split("</li>", 1)[0]
    assert "Nicht aktualisiert" not in third


def test_the_section_head_fragment_follows_the_saved_text(review):
    before = review.get("/abschnitte/1/kopf").text
    assert "Manuell bearbeitet" not in before

    review.edit(1, "Meine Fassung.")
    after = review.get("/abschnitte/1/kopf")

    assert after.status_code == 200
    assert "Manuell bearbeitet" in after.text
    assert after.text.lstrip().startswith('<div class="section-head" id="section-head">')
    assert review.get("/abschnitte/9/kopf").status_code == 404


def test_the_section_step_has_no_accept_control_and_no_per_section_discard(review):
    review.generate()

    for number in (1, 4):
        page = review.step(number).text
        assert "uebernehmen" not in main_of(page)
        assert "verwerfen" in action_bar(page)
        assert Buttons(page).find("Übernehmen") == []
        assert main_of(page).count("<form") == 1


def test_a_text_that_starts_with_a_line_break_is_kept_in_the_draft_pane(review):
    review.edit(1, "\nZweite Zeile\n")

    assert textarea_text(review.step(1).text, "data-section") == "\nZweite Zeile\n"


def test_the_copy_control_of_a_section_step_copies_the_current_draft_not_the_proposal(review):
    review.generate()
    review.accept()
    review.edit(1, "Meine Fassung.")
    review.generate()

    bar = action_bar(review.step(1).text)

    assert 'data-copy-from="#section-text"' in bar
    assert "Etagenwohnung" not in bar
    assert "disabled" not in re.search(r"<button[^>]*data-copy[^>]*>", bar).group(0)


def test_the_copy_control_is_disabled_while_the_section_has_no_text(review):
    bar = action_bar(review.step(1).text)

    assert "disabled" in re.search(r"<button[^>]*data-copy[^>]*>", bar).group(0)


# ---- generating ----


def test_the_generate_button_is_on_every_step_and_says_neu_erzeugen_with_a_proposal(review):
    for page in (review.get("/notizen").text, review.step(3).text, review.final().text):
        assert "data-generate" in page
        assert "Entwurf erzeugen" in main_of(page)
    review.generate()
    page = review.step(3).text
    assert "Neu erzeugen" in main_of(page)
    assert f'data-generate-url="{review.api_base}/generate"' in page


def test_the_retry_button_for_a_failed_generation_is_in_the_layout_but_hidden_until_needed(review):
    strip = review.step(1).text.split('class="strip"', 1)[1].split("</div>\n  </div>", 1)[0]

    assert "data-retry-generation hidden" in strip.replace("\n", " ").replace("  ", " ") or (
        "data-retry-generation" in strip and " hidden" in strip
    )


def test_a_failed_generation_is_reported_in_the_status_area_with_a_retry_button(tmp_path):
    app = create_app(Settings(token=TOKEN, data_dir=tmp_path), lambda: NOW, Unreachable())
    api = TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"})
    browser = TestClient(app)
    browser.post("/anmelden", data={"token": TOKEN})
    failing = Review(browser, api)
    failing.generate()

    page = failing.step(1).text

    status = page.split('class="status-area"', 1)[1].split("</div>", 1)[0]
    assert "Entwurf nicht erzeugt" in status
    assert "Das Textmodell ist nicht erreichbar." in main_of(page)
    retry = re.search(r"<button[^>]*data-retry-generation[^>]*>", page).group(0)
    assert "hidden" not in retry
    assert "<button" not in status
    assert "Entwurf nicht erzeugt" in failing.get("/notizen").text


def test_prose_from_the_model_is_reported_as_a_failed_generation_on_the_page(tmp_path):
    app = create_app(Settings(token=TOKEN, data_dir=tmp_path), lambda: NOW, AnswersInProse())
    api = TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"})
    browser = TestClient(app)
    browser.post("/anmelden", data={"token": TOKEN})
    failing = Review(browser, api)

    failing.generate()

    assert "nicht die erwartete Struktur" in failing.get("/notizen").text
    assert "Aktueller Entwurf" in failing.step(1).text


def test_an_idle_page_shows_the_saved_state_and_no_failure(review):
    page = review.step(1).text

    status = page.split('class="status-area"', 1)[1].split("</div>", 1)[0]
    assert "Gespeichert" in status
    assert "Entwurf nicht erzeugt" not in status.split("<template", 1)[0]
    assert 'data-generation="idle"' in page


# ---- Übernehmen ----


def test_the_final_step_with_a_proposal_names_what_is_replaced_and_what_stays(review):
    review.generate()
    review.edit(2, "Meine Anamnese.")
    review.edit(6, "Mein Befund.")

    page = body_of(review.final().text)

    replaced = page.split('id="replaced-title"', 1)[1].split("</section>", 1)[0]
    retained = page.split('id="retained-title"', 1)[1].split("</section>", 1)[0]
    for title in (ASSESSMENT_SECTIONS[i] for i in (0, 2, 3, 4, 6)):
        assert f"<li>{title}</li>" in replaced
    assert f"<li>{ASSESSMENT_SECTIONS[1]}</li>" in retained
    assert f"<li>{ASSESSMENT_SECTIONS[5]}</li>" in retained
    assert f"<li>{ASSESSMENT_SECTIONS[1]}</li>" not in replaced
    assert "Nicht aktualisiert" in retained


def test_with_nothing_retained_the_final_step_says_no_section_stays(review):
    review.generate()

    page = body_of(review.final().text)

    retained = page.split('id="retained-title"', 1)[1].split("</section>", 1)[0]
    assert "Kein Abschnitt." in retained
    assert "<li>" not in retained


def test_the_final_step_shows_the_clarification_list_of_the_proposal(browser, api_client):
    second = Review(browser, api_client, "FIK-2026-002")
    second.generate()

    page = body_of(second.final().text)

    assert "Zu klären, laut Vorschlag" in page
    assert "Welcher der drei Schmerzen steht im Vordergrund" in page


def test_acceptance_is_one_action_for_the_whole_proposal(review):
    review.generate()
    page = review.final().text

    forms = re.findall(r'<form[^>]*action="([^"]+)"', main_of(page))
    assert forms == [
        f"{review.page_base}/abschluss/uebernehmen",
        f"{review.page_base}/abschluss/verwerfen",
    ]
    assert Buttons(page).find("Übernehmen")[0]["disabled"] is False


def test_accepting_by_the_form_replaces_the_draft_and_lands_on_the_handover(review):
    review.generate()

    response = review.browser.post(
        f"{review.page_base}/abschluss/uebernehmen", follow_redirects=False
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"{review.page_base}/abschluss"
    page = review.final().text
    assert '<h1 class="step-title">Übergabe</h1>' in page
    assert Buttons(review.step(1).text).find("Kopieren")[0]["disabled"] is False
    assert "Lebt mit dem Ehemann" in textarea_text(review.step(1).text, "data-section")


def test_discarding_by_the_form_returns_to_the_step_it_came_from(review):
    review.generate()

    response = review.browser.post(
        f"{review.page_base}/abschluss/verwerfen",
        data={"back": f"{review.page_base}/abschnitte/3"},
        follow_redirects=False,
    )

    assert response.headers["location"] == f"{review.page_base}/abschnitte/3"
    assert "Noch kein Vorschlag" in proposal_pane(review.step(3).text)
    assert steps_in_sidebar(review.step(3).text)[-1][1] == "Übergabe"


@pytest.mark.parametrize("back", ["https://example.org/", "//example.org/", "/faelle/1/andere", ""])
def test_discarding_never_redirects_outside_the_encounter(review, back):
    review.generate()

    response = review.browser.post(
        f"{review.page_base}/abschluss/verwerfen", data={"back": back}, follow_redirects=False
    )

    assert response.headers["location"] == f"{review.page_base}/notizen"


def test_a_proposal_that_replaces_nothing_changes_is_still_accepted_whole(review):
    review.generate()
    for number in range(1, 8):
        review.edit(number, f"Mein Text {number}.")

    page = body_of(review.final().text)
    review.browser.post(f"{review.page_base}/abschluss/uebernehmen")

    replaced = page.split('id="replaced-title"', 1)[1].split("</section>", 1)[0]
    assert "Kein Abschnitt." in replaced
    assert all(
        "Nicht aktualisiert"
        in review.step(n).text.split('id="section-head"')[1].split("state-line")[0]
        for n in range(1, 8)
    )


# ---- an outdated proposal ----


def outdated(review):
    review.generate()
    review.save_notes(review.notes() + " Neue Beobachtung.")


def test_an_outdated_proposal_disables_acceptance_and_spells_the_reason_out_next_to_it(review):
    outdated(review)
    page = review.final().text

    accept = Buttons(page).find("Übernehmen")[0]
    note = re.search(r'<p class="step-note" id="outdated-reason"[^>]*>(.*?)</p>', page, re.S)
    assert accept["disabled"]
    assert OUTDATED in html.unescape(note.group(1))
    assert 'aria-describedby="outdated-reason"' in page
    # The reason sits directly above the action bar, inside the page and not in a tooltip.
    assert page.index('id="outdated-reason"') < page.index('<footer class="action-bar">')
    assert "title=" not in note.group(0)


def test_an_outdated_proposal_stays_visible_and_offers_only_discard_and_regeneration(review):
    outdated(review)

    final = review.final().text
    section = review.step(1).text

    assert "Noch kein Vorschlag" not in proposal_pane(section)
    assert "Neu erzeugen" in main_of(final)
    assert Buttons(final).find("Übernehmen")[0]["disabled"]
    assert Buttons(final).find("Verwerfen")[0]["disabled"] is False


def test_an_outdated_proposal_shows_veraltet_next_to_the_icon_on_every_section_step(review):
    outdated(review)

    for number in (1, 5):
        head = review.step(number).text.split('id="section-head"', 1)[1].split("state-line", 1)[0]
        assert '<span class="badge-word">Veraltet</span>' in head
    line = re.search(r'<span class="state-text">([^<]*)</span>', review.step(1).text).group(1)
    assert line == "Vorschlag veraltet"


def test_accepting_an_outdated_proposal_by_the_form_is_refused_with_the_reason(review):
    outdated(review)

    response = review.browser.post(f"{review.page_base}/abschluss/uebernehmen")

    assert response.status_code == 409
    alert = re.search(
        r'<div class="alert alert-error" role="alert">(.*?)</div>', response.text, re.S
    )
    assert OUTDATED in html.unescape(alert.group(1))
    assert not review.api.get(f"{review.api_base}/draft").json()["has_draft"]


def test_the_outdated_proposal_does_not_change_the_sidebar_badge_into_a_fresh_one(review):
    outdated(review)

    sidebar = sidebar_of(review.get("/notizen").text)

    assert 'aria-label="Zustand: Vorschlag veraltet"' in sidebar


# ---- the encounter-wide marker ----


def possibly_outdated(review):
    review.generate()
    review.accept()
    review.save_notes(review.notes() + " Neu.")


def test_one_marker_says_the_draft_is_possibly_outdated_on_every_step(review):
    possibly_outdated(review)

    for page in (
        review.get("/notizen").text,
        review.step(1).text,
        review.step(6).text,
        review.final().text,
    ):
        assert page.count("Entwurf möglicherweise veraltet") >= 1
        assert main_of(page).count('class="marker"') == 1
    assert 'aria-label="Zustand: Entwurf möglicherweise veraltet"' in sidebar_of(
        review.step(1).text
    )


def test_there_is_no_marker_before_the_notes_move_past_the_draft(review):
    review.generate()
    review.accept()

    for page in (review.step(1).text, review.final().text):
        assert 'class="marker"' not in page


def test_the_marker_guesses_no_sections(review):
    possibly_outdated(review)

    marker = review.step(2).text.split('class="marker"', 1)[1].split("</div>", 1)[0]

    assert "Abschnitt" in marker  # "Lindra vermutet nicht, welche Abschnitte betroffen sind"
    assert not any(title in marker for title in ASSESSMENT_SECTIONS)


def test_the_marker_clears_when_a_proposal_from_the_current_notes_is_accepted(review):
    possibly_outdated(review)
    review.generate()
    assert 'class="marker"' in review.step(1).text

    review.accept()

    assert 'class="marker"' not in review.step(1).text


# ---- Übergabe ----


def test_an_encounter_without_a_draft_says_there_is_nothing_to_copy(review):
    page = review.final().text

    assert "Es gibt noch nichts zu kopieren" in body_of(page)
    assert "data-copy" not in body_of(page)
    assert '<h1 class="step-title">Übergabe</h1>' in page


def test_the_handover_has_one_copy_control_per_section_with_the_plain_text(review):
    review.generate()
    review.accept()

    page = body_of(review.final().text)

    rows = page.split('<li class="handover-row"')[1:]
    assert len(rows) == 7
    controls = re.findall(r'<button[^>]*data-copy[^>]*data-copy-text="([^"]*)"', page)
    assert len(controls) == 7
    therapy = html.unescape(controls[2])
    assert therapy.startswith("Aktuelle Medikation\nIbuprofen 400 mg")
    assert "\n\nFrühere nichtmedikamentöse Behandlungen\nPhysiotherapie 2024" in therapy
    assert html.unescape(controls[0]).startswith("Lebt mit dem Ehemann")
    assert 'aria-label="Sozialanamnese kopieren"' in page


def test_the_handover_copies_the_current_draft_and_never_the_pending_proposal(review):
    review.generate()
    review.accept()
    review.edit(1, "Meine Fassung.")
    review.generate()
    # While a proposal is pending the last step is Übernehmen, which copies nothing.
    assert "data-copy-text" not in review.final().text

    review.browser.post(f"{review.page_base}/abschluss/verwerfen")
    texts = [html.unescape(t) for t in re.findall(r'data-copy-text="([^"]*)"', review.final().text)]

    assert texts[0] == "Meine Fassung."
    assert not any("Etagenwohnung" in t for t in texts)


def test_an_empty_section_in_the_handover_has_a_disabled_copy_control(browser, api_client):
    gaps = Review(browser, api_client, "FIK-2026-003")
    gaps.generate()
    gaps.accept()

    page = body_of(gaps.final().text)

    first = page.split('<li class="handover-row"')[1]
    assert "Leer, nichts zu kopieren" in first
    assert "disabled" in re.search(r"<button[^>]*data-copy[^>]*>", first).group(0)
    assert "<pre" not in first


def test_a_draft_written_only_by_hand_can_be_copied_from_the_handover(review):
    review.edit(2, "Früher Bandscheibenvorfall.")

    page = body_of(review.final().text)

    assert "Es gibt noch nichts zu kopieren" not in page
    assert "Früher Bandscheibenvorfall." in page
    assert "Leer, nichts zu kopieren" in page


def test_the_copy_text_is_escaped_in_the_page_and_arrives_unchanged(review):
    review.edit(1, 'Patient sagt: "Es <tut> weh" & mehr')

    page = review.final().text

    (text,) = [html.unescape(t) for t in re.findall(r'data-copy-text="([^"]*)"', page)[:1]]
    assert text == 'Patient sagt: "Es <tut> weh" & mehr'
    assert "<tut>" not in page.replace("&lt;tut&gt;", "")


# ---- the notes step keeps working beside the new frame ----


def test_the_notes_step_still_shows_its_text_and_save_url(review):
    page = review.get("/notizen").text

    assert f'data-save-url="{review.api_base}/notes"' in page
    assert "Seit 14 Monaten tiefer Rückenschmerz" in textarea_text(page, "data-notes")
    assert 'id="badge-icons"' in page


def test_the_notes_step_shows_the_stale_marker_too(review):
    possibly_outdated(review)

    assert 'class="marker"' in review.get("/notizen").text


# ---- input references, pain problems and the clarification list (ticket 08) ----


def origins_of(page):
    return page.split('id="section-origins"', 1)[1]


def test_every_paragraph_of_the_proposal_has_a_tappable_reference_with_its_quoted_passage(review):
    review.generate()

    pane = proposal_pane(review.step(1).text)

    assert pane.count('<details class="origin">') == 1
    assert "aus Notizen" in pane
    assert (
        '<blockquote class="origin-quote" lang="de">Patientin lebt mit Ehemann in einer '
        "Etagenwohnung, zwei erwachsene Kinder, arbeitet halbtags im Büro, aktuell "
        "krankgeschrieben.</blockquote>"
    ) in pane


def test_a_paragraph_with_several_passages_shows_each(browser, api_client):
    second = Review(browser, api_client, "FIK-2026-002")
    second.generate()

    pane = proposal_pane(second.step(2).text)

    for quote in ("Migräne seit der Jugend", "Diabetes mellitus Typ 2", "Topiramat 2022"):
        assert quote in pane
    assert pane.count("<blockquote") == 3


def test_the_reference_says_where_the_text_came_from_and_nothing_about_correctness(review):
    review.generate()
    review.accept()

    origins = origins_of(review.step(1).text).split("</main>", 1)[0].lower()

    for claim in ("korrekt", "geprüft", "verifiziert", "bestätigt", "sicher", "konfidenz", "%"):
        assert claim not in origins


def test_the_draft_pane_lists_where_each_paragraph_came_from(review):
    review.generate()
    review.accept()

    origins = origins_of(review.step(3).text)

    assert origins.count("aus Notizen") == 2
    assert "von Hand, keine Herkunft" not in origins
    assert "Aktuelle Medikation · Ibuprofen 400 mg bei Bedarf" in origins
    assert "Frühere nichtmedikamentöse Behandlungen · Physio" in origins


def test_a_hand_rewritten_paragraph_shows_von_hand_keine_herkunft(review):
    review.generate()
    review.accept()
    review.edit(1, "Lebt allein.")

    origins = origins_of(review.step(1).text)

    assert "von Hand, keine Herkunft" in origins
    assert "aus Notizen" not in origins


def test_only_the_rewritten_paragraph_of_a_section_loses_its_reference(browser, api_client):
    second = Review(browser, api_client, "FIK-2026-002")
    second.generate()
    second.accept()
    text = textarea_text(second.step(3).text, "data-section")
    second.edit(3, text.replace("Physiotherapie 2025.", "Physiotherapie 2025, wöchentlich."))

    origins = origins_of(second.step(3).text)

    assert origins.count("aus Notizen") == 2
    assert origins.count("von Hand, keine Herkunft") == 1


def test_the_origins_fragment_follows_the_saved_text(review):
    review.generate()
    review.accept()
    assert "aus Notizen" in review.get("/abschnitte/1/herkunft").text

    review.edit(1, "Meine Fassung.")
    after = review.get("/abschnitte/1/herkunft")

    assert after.status_code == 200
    assert "von Hand, keine Herkunft" in after.text
    assert "aus Notizen" not in after.text
    assert after.text.lstrip().startswith('<div class="origins" id="section-origins">')
    assert review.get("/abschnitte/9/herkunft").status_code == 404


def test_a_section_without_a_draft_lists_no_origins(review):
    assert "Herkunft der Absätze" not in review.step(1).text


def test_the_pain_step_shows_each_pain_problem_as_its_own_block_with_its_own_heading(
    browser, api_client
):
    second = Review(browser, api_client, "FIK-2026-002")
    second.generate()

    pane = proposal_pane(second.step(4).text)

    headings = re.findall(r'<h3 class="para-heading">([^<]*)</h3>', pane)
    assert headings == ["Migräne", "Linkes Knie", "Beide Füße", "Ohne Zuordnung zu einem Schmerz"]
    assert "Hauptschmerz" not in pane


def test_the_proposal_pane_shows_the_questions_the_proposal_has_for_the_section(
    browser, api_client
):
    gaps = Review(browser, api_client, "FIK-2026-003")
    gaps.generate()

    pane = proposal_pane(gaps.step(1).text)

    assert "Zu klären, laut Vorschlag" in pane
    assert "Die Notizen enthalten keine Sozialanamnese." in pane
    assert "Zu klären, laut Vorschlag" not in proposal_pane(gaps.step(2).text)


def test_the_final_step_shows_the_whole_clarification_list_after_acceptance(browser, api_client):
    gaps = Review(browser, api_client, "FIK-2026-003")
    gaps.generate()
    gaps.accept()

    page = body_of(gaps.final().text)

    assert "Zu klären" in page and "laut Vorschlag" not in page
    for section in ("Sozialanamnese", "Therapeutische Anamnese", "Schmerzanamnese"):
        assert f"<strong>{section}.</strong>" in page
    assert "Die Angaben zu Tramadol widersprechen sich: 50 mg oder 100 mg zweimal täglich." in page
    assert "Die Begründung für den stationären Aufenthalt fehlt" in page


def test_a_manual_edit_leaves_the_list_on_the_final_step_as_it_was(browser, api_client):
    gaps = Review(browser, api_client, "FIK-2026-003")
    gaps.generate()
    gaps.accept()
    before = body_of(gaps.final().text)

    for number in range(1, 8):
        gaps.edit(number, f"Von Hand ergänzt {number}.")

    after = body_of(gaps.final().text)
    assert after.count("<strong>") == before.count("<strong>")
    assert "Die Notizen enthalten keine Sozialanamnese." in after


def test_the_final_step_without_a_list_shows_no_list(review):
    review.generate()
    review.accept()

    assert "Zu klären" not in body_of(review.final().text)
