"""The real adapters against a local stub server that speaks the documented routes.

No real model and no real recogniser runs here (they run only in the operator's evaluation,
`docs/evaluation/real-backends.md`). The stub answers like an OpenAI-style chat completions
server and like whisper.cpp's `/inference`, so these tests prove what Lindra sends, what it
does with the answer and that a server that fails never produces a draft or a transcript.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

from lindra import cast, standins
from lindra.app import create_app
from lindra.backends import ChatCompletionsModel, SelfHostedSpeech, render_request
from lindra.config import Settings
from lindra.speech import TranscriptionFailed
from lindra.textmodel import BackgroundEncounter, GenerationFailed, GenerationRequest
from tests.conftest import NOW, TOKEN
from tests.test_cases_api import seeded_case

FIRST = cast.load_cast().cases[0]
ASSESSMENT = FIRST.encounters[0]


class Stub:
    """A server that records each request and answers with what the test set."""

    def __init__(self):
        self.requests = []
        self.status = 200
        self.body = b"{}"
        self.location = ""
        self.claimed_length = 0
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                stub.requests.append((self.path, dict(self.headers), self.rfile.read(length)))
                self.send_response(stub.status)
                self.send_header("Content-Type", "application/json")
                if stub.location:
                    self.send_header("Location", stub.location)
                if stub.claimed_length:
                    self.send_header("Content-Length", str(stub.claimed_length))
                self.end_headers()
                self.wfile.write(stub.body)

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_port}"

    def answer_chat(self, content):
        self.body = json.dumps({"choices": [{"message": {"content": content}}]}).encode()

    def answer_text(self, text):
        self.body = json.dumps({"text": text}).encode()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def stub():
    server = Stub()
    yield server
    server.close()


def request_for(encounter=ASSESSMENT, background=()):
    from datetime import datetime, time

    return GenerationRequest(
        FIRST.case_number,
        encounter.kind,
        datetime.combine(encounter.date, time(9, 0)),
        encounter.notes,
        background=background,
    )


# ---- the text model ----


def test_the_model_gets_the_instructions_the_sections_and_the_notes(stub):
    stub.answer_chat("{}")

    ChatCompletionsModel(stub.url, "some-model:1b").generate(request_for())

    path, _, body = stub.requests[0]
    sent = json.loads(body)
    assert path == "/v1/chat/completions"
    assert sent["model"] == "some-model:1b"
    assert sent["temperature"] == 0
    system, user = sent["messages"]
    assert system["role"] == "system"
    assert "Du fügst nichts hinzu" in system["content"]
    for title in cast.ASSESSMENT_SECTIONS:
        assert title in user["content"]
    assert ASSESSMENT.notes in user["content"]


def test_a_visit_sends_its_background_with_the_key_of_each_encounter():
    visit = next(e for e in FIRST.encounters if e.kind == "visit")
    from datetime import datetime, time

    earlier = BackgroundEncounter(
        "encounter:7",
        "assessment",
        datetime.combine(ASSESSMENT.date, time(9, 0)),
        (("Sozialanamnese", "Lebt allein."),),
    )

    text = render_request(request_for(visit, background=(earlier,)))

    assert "encounter:7" in text
    assert "Lebt allein." in text
    assert visit.notes in text
    for title in cast.VISIT_SECTIONS:
        assert title in text


def test_the_model_answer_is_the_json_object_in_its_message(stub):
    stub.answer_chat('{"sections": [], "clarifications": []}')

    result = ChatCompletionsModel(stub.url, "m").generate(request_for())

    assert result == {"sections": [], "clarifications": []}


def test_a_model_that_wraps_its_answer_in_a_code_fence_still_answers(stub):
    stub.answer_chat('```json\n{"sections": [], "clarifications": []}\n```')

    result = ChatCompletionsModel(stub.url, "m").generate(request_for())

    assert result == {"sections": [], "clarifications": []}


@pytest.mark.parametrize("content", ["Hier ist Ihr Entwurf.", "", None, 7])
def test_prose_instead_of_json_is_a_failed_generation(stub, content):
    stub.answer_chat(content)

    with pytest.raises(GenerationFailed):
        ChatCompletionsModel(stub.url, "m").generate(request_for())


def test_an_answer_without_choices_is_a_failed_generation(stub):
    stub.body = b'{"error": "x"}'

    with pytest.raises(GenerationFailed):
        ChatCompletionsModel(stub.url, "m").generate(request_for())


def test_a_server_error_is_a_failed_generation(stub):
    stub.status = 500

    with pytest.raises(GenerationFailed, match="nicht geantwortet"):
        ChatCompletionsModel(stub.url, "m").generate(request_for())


def test_a_redirect_is_not_followed_so_the_key_stays_with_its_host(stub):
    elsewhere = Stub()
    try:
        stub.status = 302
        stub.location = elsewhere.url + "/v1/chat/completions"

        with pytest.raises(GenerationFailed):
            ChatCompletionsModel(stub.url, "m", "key-for-the-test-only").generate(request_for())

        assert elsewhere.requests == []
    finally:
        elsewhere.close()


def test_an_answer_that_breaks_off_is_a_failed_generation(stub):
    stub.body = b'{"choices": '
    stub.claimed_length = 500

    with pytest.raises(GenerationFailed):
        ChatCompletionsModel(stub.url, "m", timeout=5).generate(request_for())


def test_a_server_that_is_not_there_is_a_failed_generation():
    with pytest.raises(GenerationFailed, match="nicht geantwortet"):
        ChatCompletionsModel("http://127.0.0.1:9", "m", timeout=2).generate(request_for())


def test_the_key_is_sent_as_a_bearer_token_only_when_there_is_one(stub):
    stub.answer_chat("{}")

    ChatCompletionsModel(stub.url, "m").generate(request_for())
    ChatCompletionsModel(stub.url, "m", "key-for-the-test-only").generate(request_for())

    without, with_key = (headers for _, headers, _ in stub.requests)
    assert "Authorization" not in without
    assert with_key["Authorization"] == "Bearer key-for-the-test-only"


# ---- speech ----


def test_the_recording_goes_to_the_recogniser_as_german_audio(stub):
    stub.answer_text(" Rückenschmerz seit zwei Jahren. ")
    audio = cast.fixture_audio("any")

    text = SelfHostedSpeech(stub.url).transcribe(audio)

    path, headers, body = stub.requests[0]
    assert text == "Rückenschmerz seit zwei Jahren."
    assert path == "/inference"
    assert headers["Content-Type"].startswith("multipart/form-data; boundary=")
    assert audio in body
    assert b'name="language"\r\n\r\nde' in body
    assert b'name="response_format"\r\n\r\njson' in body


def test_the_recogniser_route_and_model_are_the_operators_to_choose(stub):
    stub.answer_text("x")

    SelfHostedSpeech(stub.url, "/v1/audio/transcriptions", "some-whisper").transcribe(b"audio")

    path, _, body = stub.requests[0]
    assert path == "/v1/audio/transcriptions"
    assert b'name="model"\r\n\r\nsome-whisper' in body


def test_a_recogniser_error_is_a_failed_transcription(stub):
    stub.status = 500

    with pytest.raises(TranscriptionFailed):
        SelfHostedSpeech(stub.url).transcribe(b"audio")


def test_a_recogniser_answer_without_text_is_a_failed_transcription(stub):
    stub.body = b'{"segments": []}'

    with pytest.raises(TranscriptionFailed):
        SelfHostedSpeech(stub.url).transcribe(b"audio")


def test_a_recogniser_that_is_not_there_is_a_failed_transcription():
    with pytest.raises(TranscriptionFailed):
        SelfHostedSpeech("http://127.0.0.1:9", timeout=2).transcribe(b"audio")


# ---- the evaluation configuration, through the HTTP API ----


def evaluation_client(tmp_path, **settings):
    app = create_app(
        Settings(token=TOKEN, data_dir=tmp_path, tier="evaluation", **settings),
        clock=lambda: NOW,
    )
    return TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"})


def test_the_self_hosted_model_writes_the_draft_of_a_cast_case(tmp_path, stub):
    stub.answer_chat(json.dumps(standins.expected_result(ASSESSMENT, {})))
    client = evaluation_client(
        tmp_path, text_backend="selfhosted", text_url=stub.url, text_model="some-model:1b"
    )
    case = seeded_case(client, FIRST.case_number)
    encounter = next(e for e in case["encounters"] if e["kind"] == "assessment")

    response = client.post(f"/api/cases/{case['id']}/encounters/{encounter['id']}/generate")

    assert response.status_code == 200
    assert response.json()["proposal"]["sections"][0]["text"]
    assert client.get("/api/environment").json()["text_backend"] == "selfhosted"
    assert len(stub.requests) == 1


def test_the_hosted_comparison_sends_the_operators_key_and_model(tmp_path, stub):
    stub.answer_chat(json.dumps(standins.expected_result(ASSESSMENT, {})))
    client = evaluation_client(
        tmp_path,
        text_backend="hosted",
        hosted_url=stub.url,
        hosted_model="hosted-model",
        hosted_key="key-for-the-test-only",
    )
    case = seeded_case(client, FIRST.case_number)
    encounter = next(e for e in case["encounters"] if e["kind"] == "assessment")

    response = client.post(f"/api/cases/{case['id']}/encounters/{encounter['id']}/generate")

    assert response.status_code == 200
    _, headers, body = stub.requests[0]
    assert headers["Authorization"] == "Bearer key-for-the-test-only"
    assert json.loads(body)["model"] == "hosted-model"
    assert "key-for-the-test-only" not in response.text


def test_a_failing_real_model_does_not_fall_back_to_the_fixture_model(tmp_path, stub):
    stub.status = 500
    client = evaluation_client(
        tmp_path, text_backend="selfhosted", text_url=stub.url, text_model="m"
    )
    case = seeded_case(client, FIRST.case_number)
    encounter = next(e for e in case["encounters"] if e["kind"] == "assessment")

    response = client.post(f"/api/cases/{case['id']}/encounters/{encounter['id']}/generate")

    assert response.status_code == 502
    assert "nicht geantwortet" in response.json()["detail"]
    draft = client.get(f"/api/cases/{case['id']}/encounters/{encounter['id']}/draft").json()
    assert draft["proposal"] is None


def test_the_self_hosted_recogniser_transcribes_a_dictation(tmp_path, stub):
    stub.answer_text("Seit zwei Jahren Rückenschmerz.")
    client = evaluation_client(tmp_path, speech_backend="selfhosted", speech_url=stub.url)
    case = seeded_case(client, FIRST.case_number)
    encounter = case["encounters"][0]

    response = client.post(
        f"/api/cases/{case['id']}/encounters/{encounter['id']}/dictation/transcript",
        content=cast.fixture_audio("x"),
    )

    assert response.status_code == 200
    assert response.json()["transcript"] == "Seit zwei Jahren Rückenschmerz."


def test_a_cast_case_number_under_another_name_never_reaches_a_real_backend(tmp_path, stub):
    """The start check compares number and name; so does every request after it."""
    stub.answer_chat(json.dumps(standins.expected_result(ASSESSMENT, {})))
    client = evaluation_client(
        tmp_path,
        text_backend="selfhosted",
        text_url=stub.url,
        text_model="m",
        speech_backend="selfhosted",
        speech_url=stub.url,
    )
    created = client.post(
        "/api/cases",
        json={
            "case_number": FIRST.case_number,
            "patient_name": "Erika Beispiel",
            "label": "",
            "period_start": FIRST.period_start.isoformat(),
            "period_end": FIRST.period_end.isoformat(),
            "assessment_date": FIRST.period_start.isoformat(),
            "assessment_time": "09:00",
        },
    ).json()
    base = f"/api/cases/{created['id']}/encounters/{created['encounters'][0]['id']}"
    client.put(f"{base}/notes", json={"notes": "Rückenschmerz."})

    generated = client.post(f"{base}/generate")
    dictated = client.post(f"{base}/dictation/transcript", content=cast.fixture_audio("x"))

    assert generated.status_code == 502
    assert "erfundenen Fälle" in generated.json()["detail"]
    assert dictated.status_code == 502
    assert "erfundenen Fälle" in dictated.json()["detail"]
    assert stub.requests == []


def test_a_recording_for_a_case_outside_the_cast_never_reaches_the_recogniser(tmp_path, stub):
    stub.answer_text("never")
    client = evaluation_client(tmp_path, speech_backend="selfhosted", speech_url=stub.url)
    created = client.post(
        "/api/cases",
        json={
            "case_number": "K-4711",
            "patient_name": "Erika Beispiel",
            "label": "",
            "period_start": FIRST.period_start.isoformat(),
            "period_end": FIRST.period_end.isoformat(),
            "assessment_date": FIRST.period_start.isoformat(),
            "assessment_time": "09:00",
        },
    ).json()

    response = client.post(
        f"/api/cases/{created['id']}/encounters/{created['encounters'][0]['id']}"
        "/dictation/transcript",
        content=cast.fixture_audio("x"),
    )

    assert response.status_code == 502
    assert "erfundenen Fälle" in response.json()["detail"]
    assert stub.requests == []
