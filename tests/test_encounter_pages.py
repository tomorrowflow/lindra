"""What the physician sees of encounters: the sidebar, the overview, "Neue Visite", the notes step.

The clock stands at 10.11.2026 14:30 (`tests/conftest.py`). The case created below runs from
9.11. to 20.11., so now lies inside its period; the fictional case FIK-2026-002 ran in
October, so now lies after it. The browser-side autosave (saving, not saved, retry) is
measured in a real browser by `scripts/screenshots.py`; the service side of it is covered in
`tests/test_encounters_api.py`.
"""

import re

import pytest

from tests.test_case_pages import Buttons, case_path, create_case, seed


def sidebar_of(page):
    return page.split("<nav", 1)[1].split("</nav>", 1)[0]


def main_of(page):
    return page.split("<main", 1)[1].split("</main>", 1)[0]


def visit_form(browser, location, **entries):
    return browser.post(f"{location}/visiten/neu", data=entries, follow_redirects=False)


def encounters_in_sidebar(page):
    """Every encounter in the sidebar, in the order shown: its address, label and date."""
    pattern = (
        r'<a class="encounter-link[^"]*" href="([^"]+)"[^>]*>\s*'
        r'<span class="encounter-label">([^<]*)</span>\s*'
        r'<span class="encounter-when">([^<]*)</span>'
    )
    return [
        {"href": href, "label": label.strip(), "when": when.strip()}
        for href, label, when in re.findall(pattern, sidebar_of(page))
    ]


def first_encounter(browser, location):
    return encounters_in_sidebar(browser.get(location).text)[0]["href"]


def api_path(notes_page_path):
    """The JSON address of the notes of the encounter whose notes page this is."""
    path = notes_page_path.replace("/faelle/", "/api/cases/").replace("/kontakte/", "/encounters/")
    return path.removesuffix("/notizen") + "/notes"


def textarea_of(page):
    return page.split("<textarea", 1)[1].split(">", 1)[1].split("</textarea>", 1)[0]


# ---- the login guards the new pages ----


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/faelle/1/visiten/neu"),
        ("POST", "/faelle/1/visiten/neu"),
        ("GET", "/faelle/1/kontakte/1/notizen"),
    ],
)
def test_encounter_pages_send_a_visitor_without_login_to_the_login_page(anonymous, method, path):
    response = anonymous.request(method, path, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/anmelden"


# ---- the overview and the sidebar show the encounters ----


def test_the_overview_lists_the_assessment_and_visits_by_date_and_offers_a_new_visit(browser):
    location = create_case(browser)
    visit_form(browser, location, visit_date="2026-11-18", visit_time="09:00")
    visit_form(browser, location, visit_date="2026-11-12", visit_time="08:15")

    page = main_of(browser.get(location).text)

    assert (
        page.index("09.11.2026 10:30")
        < page.index("12.11.2026 08:15")
        < page.index("18.11.2026 09:00")
    )
    assert page.count("Aufnahmeassessment") == 1
    assert Buttons(page).find("Neue Visite") != []


def test_an_encounter_row_of_the_overview_opens_its_notes(browser):
    location = create_case(browser)

    page = main_of(browser.get(location).text)

    assert re.search(rf'href="{location}/kontakte/\d+/notizen"', page)


def test_the_sidebar_shows_the_selected_cases_encounters_after_the_case_list(browser):
    seed(browser)

    page = browser.get(case_path(browser, "FIK-2026-002")).text

    sidebar = sidebar_of(page)
    assert sidebar.index("FIK-2026-003") < sidebar.index("Aufnahmeassessment")
    assert [(e["label"], e["when"]) for e in encounters_in_sidebar(page)] == [
        ("Aufnahmeassessment", "12.10.2026 09:00"),
        ("Visite", "14.10.2026 09:00"),
        ("Visite", "16.10.2026 09:00"),
    ]


def test_the_sidebar_shows_only_the_encounters_of_the_selected_case(browser):
    seed(browser)

    second = encounters_in_sidebar(browser.get(case_path(browser, "FIK-2026-002")).text)
    first = encounters_in_sidebar(browser.get(case_path(browser, "FIK-2026-001")).text)

    assert not {e["href"] for e in first} & {e["href"] for e in second}
    assert encounters_in_sidebar(browser.get("/").text) == []


def test_the_sidebar_offers_a_new_visit_beside_the_encounters(browser):
    location = create_case(browser)

    sidebar = sidebar_of(browser.get(location).text)

    assert f'href="{location}/visiten/neu"' in sidebar
    assert "Neue Visite" in sidebar


def test_each_encounter_carries_a_state_badge_with_its_explanation_on_tap(browser):
    seed(browser)
    location = create_case(browser)

    page = browser.get(case_path(browser, "FIK-2026-001")).text
    seeded = sidebar_of(page)
    empty = sidebar_of(browser.get(location).text)

    assert seeded.count('class="badge-button"') == len(encounters_in_sidebar(page)) >= 2
    assert 'aria-label="Zustand: Notizen gespeichert, noch kein Entwurf"' in seeded
    assert 'aria-label="Zustand: Keine Notizen"' in empty
    # The explanation is in the page, hidden until the badge is tapped.
    assert re.search(r'<p class="badge-explanation" id="[^"]+" hidden>', seeded)


def test_the_badge_follows_the_saved_notes_and_blank_notes_count_as_none(browser):
    location = create_case(browser)
    path = first_encounter(browser, location)

    browser.put(api_path(path), json={"notes": " \n\t "})
    blank = sidebar_of(browser.get(path).text)
    browser.put(api_path(path), json={"notes": "Rückenschmerz"})
    written = sidebar_of(browser.get(path).text)

    assert 'aria-label="Zustand: Keine Notizen"' in blank
    assert 'aria-label="Zustand: Notizen gespeichert, noch kein Entwurf"' in written


def test_a_badge_says_nothing_about_clinical_correctness(browser):
    seed(browser)

    sidebar = sidebar_of(browser.get(case_path(browser, "FIK-2026-001")).text)

    for word in ("geprüft", "verifiziert", "korrekt", "freigegeben", "vollständig"):
        assert word not in sidebar


def test_the_other_encounters_keep_their_badges_while_one_is_selected(browser):
    seed(browser)
    shown = encounters_in_sidebar(browser.get(case_path(browser, "FIK-2026-001")).text)

    page = browser.get(shown[1]["href"]).text

    assert len(shown) >= 2
    assert sidebar_of(page).count('class="badge-button"') == len(shown)


# ---- Neue Visite ----


def test_the_new_visit_form_limits_the_date_to_the_period(browser):
    location = create_case(browser)

    page = browser.get(f"{location}/visiten/neu").text

    assert 'min="2026-11-09"' in page and 'max="2026-11-20"' in page
    assert "09.11.2026 bis 20.11.2026" in page
    assert Buttons(page).find("Visite anlegen") != []
    assert Buttons(page).find("Abbrechen") != []


def test_the_new_visit_form_starts_with_now_when_now_lies_in_the_period(browser):
    location = create_case(browser)

    page = browser.get(f"{location}/visiten/neu").text

    assert re.search(r'name="visit_date"[^>]*value="2026-11-10"', page)
    assert re.search(r'name="visit_time"[^>]*value="14:30"', page)
    assert "Vorbelegt mit jetzt" in page
    assert "Uhrzeit lässt sich ändern" in page
    assert "kein Datum vorbelegt" not in page


def test_the_new_visit_form_starts_empty_when_now_lies_outside_the_period(browser):
    seed(browser)

    page = browser.get(f"{case_path(browser, 'FIK-2026-002')}/visiten/neu").text

    assert re.search(r'name="visit_date"[^>]*value=""', page)
    assert re.search(r'name="visit_time"[^>]*value=""', page)
    assert "Heute (10.11.2026) liegt außerhalb des Behandlungszeitraums" in page
    assert "kein Datum vorbelegt" in page
    assert "Vorbelegt mit jetzt" not in page


def test_now_on_the_last_day_of_the_period_still_fills_the_form(browser):
    location = create_case(browser, period_start="2026-11-01", period_end="2026-11-10")

    page = browser.get(f"{location}/visiten/neu").text

    assert re.search(r'name="visit_date"[^>]*value="2026-11-10"', page)


def test_the_new_visit_form_for_an_unknown_case_is_not_found(browser):
    response = browser.get("/faelle/999/visiten/neu")

    assert response.status_code == 404
    assert "Fall nicht gefunden" in response.text


def test_a_visit_inside_the_period_is_created_and_opens_on_its_notes(browser):
    location = create_case(browser)

    response = visit_form(browser, location, visit_date="2026-11-12", visit_time="08:15")

    assert response.status_code == 303
    notes = browser.get(response.headers["location"])
    assert notes.status_code == 200
    assert "12.11.2026 08:15" in notes.text
    assert "Visite" in main_of(notes.text)


def test_a_backdated_visit_is_accepted_and_sorts_by_its_date(browser):
    location = create_case(browser)
    visit_form(browser, location, visit_date="2026-11-18", visit_time="09:00")

    response = visit_form(browser, location, visit_date="2026-11-09", visit_time="15:00")

    assert response.status_code == 303
    shown = encounters_in_sidebar(browser.get(location).text)
    assert [e["when"] for e in shown] == [
        "09.11.2026 10:30",
        "09.11.2026 15:00",
        "18.11.2026 09:00",
    ]


def test_a_visit_outside_the_period_is_refused_inline_and_keeps_the_entries(browser):
    location = create_case(browser)

    response = visit_form(browser, location, visit_date="2026-11-25", visit_time="09:30")

    assert response.status_code == 422
    page = response.text
    assert "Die Visite muss im Behandlungszeitraum 09.11.2026 bis 20.11.2026 liegen" in page
    assert re.search(r'name="visit_date"[^>]*value="2026-11-25"', page)
    assert re.search(r'name="visit_time"[^>]*value="09:30"', page)
    assert len(encounters_in_sidebar(browser.get(location).text)) == 1


def test_a_visit_without_date_or_time_is_refused_inline(browser):
    location = create_case(browser)

    response = visit_form(browser, location)

    assert response.status_code == 422
    assert "Datum der Visite angeben" in response.text
    assert "Uhrzeit der Visite angeben" in response.text


def test_a_refused_visit_form_keeps_its_buttons_and_the_room_for_its_messages(browser):
    location = create_case(browser)
    clean = browser.get(f"{location}/visiten/neu").text
    refused = visit_form(browser, location, visit_date="2027-01-01", visit_time="09:30").text

    assert Buttons(clean).buttons == Buttons(refused).buttons
    assert clean.count('class="field-error"') == refused.count('class="field-error"') == 2


def test_a_visit_for_an_unknown_case_is_not_found_on_the_page(browser):
    response = browser.post("/faelle/999/visiten/neu", data={"visit_date": "2026-11-12"})

    assert response.status_code == 404
    assert "Fall nicht gefunden" in response.text


# ---- the notes step ----


def test_the_notes_step_shows_the_case_header_and_the_encounters_date(browser):
    location = create_case(browser)

    page = main_of(browser.get(first_encounter(browser, location)).text)

    assert "FIK-2026-100" in page
    assert "Marta Lindqvist" in page
    assert "Aufnahmeassessment" in page
    assert "09.11.2026 10:30" in page
    assert "Notizen" in page


def test_the_notes_step_has_a_free_text_area_with_the_saved_notes_and_no_save_button(browser):
    seed(browser)

    page = browser.get(first_encounter(browser, case_path(browser, "FIK-2026-001"))).text

    # The dictation overlay holds the only other text area, for a transcript.
    assert page.split('<dialog class="dictation ')[0].count("<textarea") == 1
    assert textarea_of(page).strip() != ""
    assert Buttons(page).find("Speichern") == []


def test_notes_are_shown_as_text_and_never_as_markup(browser):
    location = create_case(browser)
    path = first_encounter(browser, location)
    browser.put(api_path(path), json={"notes": "<script>alert(1)</script>"})

    page = browser.get(path).text

    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page


def test_a_note_that_starts_with_a_blank_line_keeps_it(browser):
    location = create_case(browser)
    path = first_encounter(browser, location)
    browser.put(api_path(path), json={"notes": "\nzweite Zeile"})

    page = browser.get(path).text

    # The first line break after the tag is the parser's own; the next one is the note's.
    assert textarea_of(page) == "\n\nzweite Zeile"


@pytest.mark.parametrize("notes", ["\r\nzweite Zeile", "\rzweite Zeile"])
def test_a_note_that_starts_with_a_windows_or_old_style_break_keeps_it_too(browser, notes):
    location = create_case(browser)
    path = first_encounter(browser, location)
    browser.put(api_path(path), json={"notes": notes})

    page = browser.get(path).text

    # The same extra line break as for "\n": the parser drops exactly one.
    assert textarea_of(page) == "\n" + notes


@pytest.mark.parametrize("notes", ["", "Rückenschmerz", "erste Zeile\nzweite Zeile\n"])
def test_a_note_is_in_the_text_area_without_a_line_break_added_in_front(browser, notes):
    location = create_case(browser)
    path = first_encounter(browser, location)
    browser.put(api_path(path), json={"notes": notes})

    page = browser.get(path).text

    assert textarea_of(page) == notes


def test_the_status_area_says_saved_and_holds_no_button(browser):
    location = create_case(browser)

    page = browser.get(first_encounter(browser, location)).text

    status = page.split('class="status-area"', 1)[1].split("</div>", 1)[0]
    assert "Gespeichert" in status
    assert "<button" not in status
    assert "<a " not in status


def test_the_status_area_can_show_every_save_state(browser):
    location = create_case(browser)

    page = browser.get(first_encounter(browser, location)).text

    for label in ("Gespeichert", "Speichert …", "Nicht gespeichert", "Speichern fehlgeschlagen"):
        assert label in page


def test_the_retry_button_is_a_separate_control_that_is_hidden_until_a_save_fails(browser):
    location = create_case(browser)

    page = browser.get(first_encounter(browser, location)).text

    retry = Buttons(page).find("Erneut speichern")
    assert len(retry) == 1
    assert retry[0]["hidden"] is True
    status = page.split('class="status-area"', 1)[1].split("</div>", 1)[0]
    assert "Erneut speichern" not in status


def test_the_notes_step_loads_its_script_and_tells_it_where_to_save(browser):
    location = create_case(browser)
    path = first_encounter(browser, location)

    page = browser.get(path).text

    assert f'data-save-url="{api_path(path)}"' in page
    assert '<script type="module" src="/static/js/notes.js"' in page


def test_the_selected_encounter_shows_its_steps_beneath_it_and_no_other_does(browser):
    seed(browser)
    shown = encounters_in_sidebar(browser.get(case_path(browser, "FIK-2026-002")).text)

    sidebar = sidebar_of(browser.get(shown[1]["href"]).text)

    assert sidebar.count('class="step-link') == 1
    assert sidebar.index(shown[1]["href"]) < sidebar.index('class="step-link')
    assert sidebar.index('class="step-link') < sidebar.index(shown[2]["href"])


def test_no_steps_are_shown_while_only_the_case_is_selected(browser):
    seed(browser)

    page = browser.get(case_path(browser, "FIK-2026-002")).text

    assert 'class="step-link' not in sidebar_of(page)


def test_the_notes_step_is_the_current_page_in_the_sidebar(browser):
    seed(browser)
    shown = encounters_in_sidebar(browser.get(case_path(browser, "FIK-2026-002")).text)

    sidebar = sidebar_of(browser.get(shown[1]["href"]).text)

    assert sidebar.count('aria-current="page"') == 1
    step = sidebar.split('class="step-link', 1)[1].split(">", 1)[0]
    assert 'aria-current="page"' in step


def test_the_notes_of_an_encounter_of_another_case_are_not_found(browser):
    seed(browser)
    other = first_encounter(browser, case_path(browser, "FIK-2026-001"))
    here = re.search(r"/faelle/(\d+)", case_path(browser, "FIK-2026-002")).group(1)
    wrong = re.sub(r"/faelle/\d+/", f"/faelle/{here}/", other)

    response = browser.get(wrong)

    assert response.status_code == 404
    assert "Kontakt nicht gefunden" in response.text
    assert "FIK-2026-001" in response.text


def test_the_notes_of_an_unknown_case_are_not_found(browser):
    response = browser.get("/faelle/999/kontakte/1/notizen")

    assert response.status_code == 404
    assert "Fall nicht gefunden" in response.text


def test_the_action_bar_is_the_same_on_the_overview_and_on_the_notes_step(browser):
    location = create_case(browser)

    overview = browser.get(location).text
    notes = browser.get(first_encounter(browser, location)).text

    def action_bar(page):
        """The controls of the bar in order: their classes (size and place) and their labels."""
        bar = page.split('<footer class="action-bar">', 1)[1].split("</footer>", 1)[0]
        controls = re.findall(r'<(?:a|button)[^>]* class="(btn [^"]*)"', bar)
        return controls, re.findall(r"<span>([^<]*)</span>", bar)

    assert action_bar(overview) == action_bar(notes)
