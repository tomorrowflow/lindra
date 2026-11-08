"""The health endpoint and the minimal authentication (ADR 0005).

This file is the pattern every later ticket follows: one test per observable
behaviour, named after what the physician or the environment check sees.
"""

from tests.conftest import TOKEN


def test_health_answers_without_a_token(anonymous):
    response = anonymous.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_request_without_token_is_refused(anonymous):
    response = anonymous.get("/api/session")

    assert response.status_code == 401
    assert response.json() == {"detail": "Anmeldung erforderlich"}


def test_api_request_with_token_is_accepted(api_client):
    response = api_client.get("/api/session")

    assert response.status_code == 200
    assert response.json() == {"authenticated": True}


def test_api_request_with_wrong_token_is_refused(anonymous):
    response = anonymous.get("/api/session", headers={"Authorization": "Bearer wrong"})

    assert response.status_code == 401


def test_page_without_login_redirects_to_the_login_page(anonymous):
    response = anonymous.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/anmelden"


def test_login_page_is_german_and_open(anonymous):
    response = anonymous.get("/anmelden")

    assert response.status_code == 200
    assert 'lang="de"' in response.text
    assert "Zugangsschlüssel" in response.text


def test_wrong_token_on_login_page_is_refused_in_german(anonymous):
    response = anonymous.post("/anmelden", data={"token": "falsch"})

    assert response.status_code == 400
    assert "Der Zugangsschlüssel ist nicht gültig" in response.text


def test_login_with_token_sets_the_session_and_opens_the_shell(anonymous):
    login = anonymous.post("/anmelden", data={"token": TOKEN}, follow_redirects=False)
    assert login.status_code == 303
    assert login.headers["location"] == "/"

    shell = anonymous.get("/")

    assert shell.status_code == 200
    assert 'lang="de"' in shell.text
    assert "Fall auswählen" in shell.text


def test_logout_closes_the_session(anonymous):
    anonymous.post("/anmelden", data={"token": TOKEN})

    anonymous.post("/abmelden")
    response = anonymous.get("/", follow_redirects=False)

    assert response.status_code == 303


def test_shell_serves_only_self_hosted_assets(api_client):
    shell = api_client.get("/")

    assert "http://" not in shell.text.replace("http://www.w3.org/2000/svg", "")
    assert "https://" not in shell.text
    assert "/static/" in shell.text
