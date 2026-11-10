"""What the physician sees: the sidebar, "Fall auswählen", the case forms and the overview.

The pages sit behind the same token login as the API (ADR 0005). Forms post to the
page routes and the browser follows the redirects, as the test client does here.
"""

from html.parser import HTMLParser

import pytest

from tests.conftest import TOKEN

FORM = {
    "case_number": "FIK-2026-100",
    "patient_name": "Marta Lindqvist",
    "label": "Kopfschmerz",
    "assessment_date": "2026-11-09",
    "assessment_time": "10:30",
    "period_start": "2026-11-09",
    "period_end": "2026-11-20",
}


class Buttons(HTMLParser):
    """The controls a physician taps: buttons and links styled as buttons, with their state."""

    def __init__(self, html):
        super().__init__()
        self.buttons = []
        self._current = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "button" or (tag == "a" and "btn" in (attributes.get("class") or "").split()):
            self._current = {
                "text": "",
                "disabled": "disabled" in attributes,
                "hidden": "hidden" in attributes,
            }
            self.buttons.append(self._current)

    def handle_data(self, data):
        if self._current is not None:
            self._current["text"] += data

    def handle_endtag(self, tag):
        if tag in ("button", "a"):
            self._current = None

    def find(self, label):
        return [b for b in self.buttons if b["text"].strip() == label]


def create_case(browser, **changes):
    response = browser.post("/faelle/neu", data={**FORM, **changes}, follow_redirects=False)
    assert response.status_code == 303
    return response.headers["location"]


def seed(browser):
    assert (
        browser.post("/api/seed", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 200
    )


def case_path(browser, number):
    # The sidebar links to every case; the link carries the case's address.
    page = browser.get("/").text
    start = page.index(number)
    return page[:start].rsplit('href="', 1)[1].split('"', 1)[0]


# ---- the login guards the pages ----


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/faelle/neu"),
        ("POST", "/faelle/neu"),
        ("GET", "/faelle/1"),
        ("GET", "/faelle/1/zeitraum"),
        ("POST", "/faelle/1/zeitraum"),
        ("GET", "/faelle/1/zeitraum/pruefen"),
        ("GET", "/faelle/1/loeschen"),
        ("POST", "/faelle/1/loeschen"),
    ],
)
def test_case_pages_send_a_visitor_without_login_to_the_login_page(anonymous, method, path):
    response = anonymous.request(method, path, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/anmelden"


# ---- the start screen ----


def test_the_start_screen_asks_for_a_case_and_offers_a_new_one(browser):
    page = browser.get("/").text

    assert "Fall auswählen" in page
    assert "Neuer Fall" in page


def test_no_case_is_preselected_even_when_cases_exist(browser):
    seed(browser)

    page = browser.get("/").text

    assert "Fall auswählen" in page
    assert 'aria-current="page"' not in page
    assert "Behandlungszeitraum" not in page


def test_the_sidebar_lists_each_case_by_number_with_name_and_period(browser):
    seed(browser)

    page = browser.get("/").text

    first = page.index("FIK-2026-001")
    assert first < page.index("FIK-2026-002") < page.index("FIK-2026-003")
    assert "Hanna Erlenbach" in page
    assert "05.10.2026 bis 16.10.2026" in page


def test_an_installation_without_cases_says_so_in_the_sidebar(browser):
    assert "Noch keine Fälle angelegt" in browser.get("/").text


def test_the_sidebar_is_reachable_from_a_button_in_the_top_bar(browser):
    page = browser.get("/").text

    assert 'for="sidebar-toggle"' in page
    assert 'aria-label="Seitenleiste öffnen"' in page


# ---- creating a case ----


def test_the_new_case_form_asks_for_every_field(browser):
    page = browser.get("/faelle/neu").text

    for text in (
        "Neuer Fall",
        "Fallnummer",
        "Patientenname",
        "Kurzbezeichnung (optional)",
        "Datum des Assessments",
        "Uhrzeit",
        "Behandlungsbeginn",
        "Behandlungsende",
        "Fall anlegen",
        "Abbrechen",
    ):
        assert text in page


def test_a_created_case_opens_on_its_overview(browser):
    location = create_case(browser)

    page = browser.get(location).text

    assert "FIK-2026-100" in page
    assert "Marta Lindqvist" in page
    assert "Kopfschmerz" in page
    assert "09.11.2026 bis 20.11.2026" in page
    assert "Ändern" in page


def test_the_new_case_appears_in_the_sidebar_and_is_the_selected_one(browser):
    location = create_case(browser)

    page = browser.get(location).text

    assert page.count('aria-current="page"') == 1
    sidebar = page.split("<nav", 1)[1].split("</nav>", 1)[0]
    assert "FIK-2026-100" in sidebar
    assert "Marta Lindqvist" in sidebar


def test_a_missing_patient_name_is_shown_inline_and_keeps_the_other_entries(browser):
    response = browser.post("/faelle/neu", data={**FORM, "patient_name": ""})

    assert response.status_code == 422
    assert "Patientenname angeben" in response.text
    assert 'value="FIK-2026-100"' in response.text
    assert "Marta" not in response.text.split("<nav", 1)[1].split("</nav>", 1)[0]


def test_an_assessment_outside_the_period_is_shown_inline(browser):
    response = browser.post("/faelle/neu", data={**FORM, "assessment_date": "2026-12-01"})

    assert response.status_code == 422
    assert "Das Assessment muss im Behandlungszeitraum liegen" in response.text


def test_an_end_before_the_start_is_shown_inline(browser):
    response = browser.post(
        "/faelle/neu", data={**FORM, "period_start": "2026-11-20", "period_end": "2026-11-09"}
    )

    assert response.status_code == 422
    assert "Behandlungsende liegt vor Behandlungsbeginn" in response.text


def test_a_refused_form_keeps_its_buttons_and_reserves_room_for_messages(browser):
    clean = browser.get("/faelle/neu").text
    refused = browser.post("/faelle/neu", data={}).text

    assert Buttons(clean).buttons == Buttons(refused).buttons
    # Each field has its message slot whether or not it carries a message.
    assert clean.count('class="field-error"') == refused.count('class="field-error"') == 7


def test_a_refused_case_is_not_stored(browser):
    browser.post("/faelle/neu", data={**FORM, "patient_name": ""})

    assert "Noch keine Fälle angelegt" in browser.get("/").text


# ---- the overview ----


def test_the_overview_shows_the_assessment_and_the_visits_with_their_dates(browser):
    seed(browser)

    page = browser.get(case_path(browser, "FIK-2026-002")).text

    assert "FIK-2026-002" in page
    assert "Behandlungszeitraum" in page
    assert "Aufnahmeassessment" in page
    assert "12.10.2026 09:00" in page
    assert page.count("Visite") >= 2
    assert "14.10.2026" in page and "16.10.2026" in page


def test_an_unknown_case_says_so_and_keeps_the_sidebar(browser):
    seed(browser)

    response = browser.get("/faelle/999")

    assert response.status_code == 404
    assert "Fall nicht gefunden" in response.text
    assert "FIK-2026-001" in response.text


# ---- correcting the period ----


def test_the_period_form_shows_the_current_period(browser):
    location = create_case(browser)

    page = browser.get(f"{location}/zeitraum").text

    assert "Behandlungszeitraum ändern" in page
    assert 'value="2026-11-09"' in page and 'value="2026-11-20"' in page


def test_a_period_that_fits_is_saved_and_shown_in_the_sidebar(browser):
    location = create_case(browser)

    response = browser.post(
        f"{location}/zeitraum",
        data={"period_start": "2026-11-05", "period_end": "2026-11-30"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == location
    sidebar = browser.get(location).text.split("<nav", 1)[1].split("</nav>", 1)[0]
    assert "05.11.2026 bis 30.11.2026" in sidebar


def test_a_period_that_strands_encounters_names_them_and_disables_saving(browser):
    seed(browser)
    path = case_path(browser, "FIK-2026-002")

    response = browser.post(
        f"{path}/zeitraum", data={"period_start": "2026-10-12", "period_end": "2026-10-15"}
    )

    assert response.status_code == 409
    assert "Visite am 16.10.2026" in response.text
    assert "Visite am 14.10.2026" not in response.text
    assert Buttons(response.text).find("Speichern")[0]["disabled"] is True
    assert Buttons(response.text).find("Abbrechen") != []


def test_a_period_that_strands_the_assessment_names_the_assessment(browser):
    location = create_case(browser)

    response = browser.post(
        f"{location}/zeitraum", data={"period_start": "2026-11-10", "period_end": "2026-11-20"}
    )

    assert response.status_code == 409
    assert "Aufnahmeassessment am 09.11.2026" in response.text


def test_a_refused_period_changes_nothing(browser):
    location = create_case(browser)

    browser.post(
        f"{location}/zeitraum", data={"period_start": "2026-11-10", "period_end": "2026-11-20"}
    )

    assert "09.11.2026 bis 20.11.2026" in browser.get(location).text


def test_the_period_form_is_open_for_saving_before_any_refusal(browser):
    location = create_case(browser)

    page = browser.get(f"{location}/zeitraum").text

    assert Buttons(page).find("Speichern")[0]["disabled"] is False


def test_an_end_before_the_start_is_shown_inline_on_the_period_form(browser):
    location = create_case(browser)

    response = browser.post(
        f"{location}/zeitraum", data={"period_start": "2026-11-20", "period_end": "2026-11-09"}
    )

    assert response.status_code == 422
    assert "Behandlungsende liegt vor Behandlungsbeginn" in response.text


def test_editing_the_dates_checks_them_before_saving_and_changes_nothing(browser):
    location = create_case(browser)

    refused = browser.get(
        f"{location}/zeitraum/pruefen",
        params={"period_start": "2026-11-10", "period_end": "2026-11-20"},
    ).text
    fits = browser.get(
        f"{location}/zeitraum/pruefen",
        params={"period_start": "2026-11-01", "period_end": "2026-11-30"},
    ).text

    assert "Aufnahmeassessment am 09.11.2026" in refused
    assert 'data-ok="false"' in refused
    assert "Aufnahmeassessment" not in fits
    assert 'data-ok="true"' in fits
    assert "09.11.2026 bis 20.11.2026" in browser.get(location).text


def test_the_check_names_an_end_before_the_start_and_a_missing_date(browser):
    location = create_case(browser)

    reversed_dates = browser.get(
        f"{location}/zeitraum/pruefen",
        params={"period_start": "2026-11-20", "period_end": "2026-11-09"},
    ).text
    missing = browser.get(
        f"{location}/zeitraum/pruefen", params={"period_start": "2026-11-09"}
    ).text

    assert "Behandlungsende liegt vor Behandlungsbeginn" in reversed_dates
    assert "Behandlungsende angeben" in missing
    assert 'data-ok="false"' in missing


# ---- deleting a case ----


def test_deleting_asks_for_confirmation_first(browser):
    location = create_case(browser)

    page = browser.get(f"{location}/loeschen").text

    assert "Fall löschen" in page
    assert "FIK-2026-100" in page
    assert "Notizen" in page and "Entwürfe" in page
    assert Buttons(page).find("Abbrechen") != []
    # Asking is not deleting.
    assert "Marta Lindqvist" in browser.get("/").text


def test_a_confirmed_delete_removes_the_case_and_returns_to_the_start(browser):
    seed(browser)
    path = case_path(browser, "FIK-2026-002")

    response = browser.post(f"{path}/loeschen", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    start = browser.get("/").text
    assert "FIK-2026-002" not in start
    assert "FIK-2026-001" in start and "FIK-2026-003" in start
    assert browser.get(path).status_code == 404


def test_deleting_an_unknown_case_is_not_found(browser):
    assert browser.post("/faelle/999/loeschen").status_code == 404
