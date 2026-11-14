"""The real adapters for the text model and speech recognition (ADR 0003).

They run only in the evaluation configuration (`lindra/config.py` refuses to build settings
for them anywhere else). Both speak plain HTTP with the standard library, so the service gains
no dependency:

- `ChatCompletionsModel` sends the instructions and the notes to a server that implements the
  OpenAI-style `/v1/chat/completions` route. llama.cpp's server, Ollama and vLLM do, on the
  same host or the same network. The hosted comparison is the same class pointed at the
  provider's address with the operator's key; whether a given provider serves that route is
  part of what the evaluation records.
- `SelfHostedSpeech` posts the recording to a recogniser server as a multipart upload:
  whisper.cpp's `whisper-server` (`/inference`) or an OpenAI-style transcription route such
  as the one faster-whisper wrappers offer (`/v1/audio/transcriptions`).

An adapter returns what its server produced; the structure and fidelity checks in
`lindra/drafts.py` and `lindra/fidelity.py` are the same as for the fixture model. A server
that does not answer, answers with an error or answers with something that is not JSON is a
failed generation or transcription with a sentence for the physician, never a draft. The audio
is sent from memory and kept nowhere by Lindra.
"""

from __future__ import annotations

import http.client
import json
import logging
import re
import secrets
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlsplit

from lindra.cast import SECTIONS, Cast
from lindra.config import HOSTED, SELF_HOSTED, STAND_IN, Settings
from lindra.evaluation import CastOnlyTextModel
from lindra.speech import SPEECH_ERROR, SpeechRecognizer, TranscriptionFailed
from lindra.standins import FixtureSpeech, FixtureTextModel
from lindra.textmodel import MODEL_NOT_ANSWERING, GenerationFailed, GenerationRequest, TextModel

log = logging.getLogger(__name__)

CHAT_PATH = "/v1/chat/completions"
# A local model on modest hardware needs minutes for an admission draft.
TEXT_TIMEOUT_SECONDS = 600
SPEECH_TIMEOUT_SECONDS = 300
NOT_JSON = "Das Textmodell hat keine auswertbare Antwort geliefert."
FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)
GERMAN = "de"


def render_request(request: GenerationRequest) -> str:
    """The user message: the sections to fill, the background of a visit and the notes."""
    titles = "\n".join(f"- {title}" for title in SECTIONS[request.kind])
    parts = [f"Abschnitte in dieser Reihenfolge:\n{titles}"]
    for earlier in request.background:
        parts.append(
            f"Hintergrund, Kennung {earlier.source} ({earlier.kind}, "
            f"{earlier.occurred_at:%d.%m.%Y}):\n{earlier.text}"
        )
    parts.append(f"Notizen:\n{request.notes}")
    return "\n\n".join(parts)


def decode_json(content: str) -> Any:
    """The JSON object in a model's answer, which may come wrapped in a code fence."""
    fenced = FENCE.match(content)
    try:
        return json.loads(fenced.group(1) if fenced else content)
    except ValueError as error:
        raise GenerationFailed(NOT_JSON) from error


class ChatCompletionsModel:
    """A text model behind an OpenAI-style chat completions route."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout: float = TEXT_TIMEOUT_SECONDS,
    ) -> None:
        self._url = base_url.rstrip("/") + CHAT_PATH
        self._model = model
        self._api_key = api_key
        self._timeout = timeout

    def generate(self, request: GenerationRequest) -> Any:
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": request.instructions},
                {"role": "user", "content": render_request(request)},
            ],
            "temperature": 0,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            answer = send(self._url, json.dumps(body).encode("utf-8"), headers, self._timeout)
        except ServerFailed as error:
            raise GenerationFailed(MODEL_NOT_ANSWERING) from error
        try:
            content = json.loads(answer)["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise GenerationFailed(NOT_JSON) from error
        if not isinstance(content, str):
            raise GenerationFailed(NOT_JSON)
        return decode_json(content)


class ServerFailed(Exception):
    """The server gave no answer: it was not reachable, timed out or answered with an error."""


class NoRedirects(urllib.request.HTTPRedirectHandler):
    """A redirect is an error, so the account key never follows one to another host."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


OPENER = urllib.request.build_opener(NoRedirects)


def send(url: str, body: bytes, headers: dict[str, str], timeout: float) -> bytes:
    """One POST. Any transport or status failure is `ServerFailed`, logged with the host only:
    the request holds the notes or the audio, the headers hold the key."""
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    host = urlsplit(url).hostname
    try:
        with OPENER.open(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        log.error("the server at %s answered %s", host, error.code)
        raise ServerFailed from error
    except (urllib.error.URLError, http.client.HTTPException, OSError) as error:
        log.error("the server at %s gave no answer: %s", host, type(error).__name__)
        raise ServerFailed from error


class SelfHostedSpeech:
    """A recogniser server that takes the recording as a multipart upload."""

    def __init__(
        self,
        base_url: str,
        path: str = "/inference",
        model: str = "",
        timeout: float = SPEECH_TIMEOUT_SECONDS,
    ) -> None:
        self._url = base_url.rstrip("/") + "/" + path.lstrip("/")
        self._model = model
        self._timeout = timeout

    def transcribe(self, audio: bytes) -> str:
        fields = {"language": GERMAN, "response_format": "json", "temperature": "0"}
        if self._model:
            fields["model"] = self._model
        body, content_type = multipart(fields, audio)
        try:
            answer = send(self._url, body, {"Content-Type": content_type}, self._timeout)
        except ServerFailed as error:
            raise TranscriptionFailed(SPEECH_ERROR) from error
        try:
            text = json.loads(answer)["text"]
        except (ValueError, KeyError, TypeError) as error:
            raise TranscriptionFailed(SPEECH_ERROR) from error
        if not isinstance(text, str):
            raise TranscriptionFailed(SPEECH_ERROR)
        return text.strip()


def multipart(fields: dict[str, str], audio: bytes) -> tuple[bytes, str]:
    """A multipart/form-data body: the form fields and the recording as the field `file`."""
    boundary = secrets.token_hex(16)
    lines: list[bytes] = []
    for name, value in fields.items():
        lines += [
            f"--{boundary}".encode(),
            f'Content-Disposition: form-data; name="{name}"'.encode(),
            b"",
            value.encode("utf-8"),
        ]
    lines += [
        f"--{boundary}".encode(),
        b'Content-Disposition: form-data; name="file"; filename="dictation"',
        b"Content-Type: application/octet-stream",
        b"",
        audio,
        f"--{boundary}--".encode(),
        b"",
    ]
    return b"\r\n".join(lines), f"multipart/form-data; boundary={boundary}"


def build_text_model(settings: Settings, cast: Cast) -> TextModel:
    """The configured text model. Outside the evaluation configuration `Settings` cannot hold
    anything but the stand-in, so a real or hosted model is only built where it may run. In the
    evaluation configuration a real model is wrapped so that it sees only the cast."""
    if settings.text_backend == STAND_IN:
        return FixtureTextModel(cast)
    if settings.text_backend == SELF_HOSTED:
        model: TextModel = ChatCompletionsModel(settings.text_url, settings.text_model)
    elif settings.text_backend == HOSTED:
        model = ChatCompletionsModel(
            settings.hosted_url, settings.hosted_model, settings.hosted_key
        )
    else:
        raise AssertionError(settings.text_backend)
    return CastOnlyTextModel(model, cast)


def build_speech(settings: Settings, cast: Cast) -> SpeechRecognizer:
    if settings.speech_backend == STAND_IN:
        return FixtureSpeech(cast)
    return SelfHostedSpeech(settings.speech_url, settings.speech_path, settings.speech_model)
