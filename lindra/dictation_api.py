"""The JSON routes for dictation. The token guard in `lindra/auth.py` covers `/api/`.

The recording arrives as the raw request body, whatever type the browser recorded (webm on
Chrome, mp4 on Safari). It lives in memory for the length of the request and is never written.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from lindra import case_api, cases, dictation
from lindra.speech import SpeechRecognizer, TranscriptionFailed
from lindra.store import Store

RawBody = Annotated[dict[str, Any] | None, Body()]
TOO_LARGE = "Die Aufnahme ist zu lang"


def build_router(
    store: Store, speech: SpeechRecognizer, clock: Callable[[], datetime]
) -> APIRouter:
    router = APIRouter(prefix="/api/cases/{case_id}/encounters/{encounter_id}/dictation")

    @router.post("/transcript")
    async def transcript(request: Request, case_id: int, encounter_id: int) -> Response:
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > dictation.MAX_AUDIO_BYTES:
            return JSONResponse({"detail": TOO_LARGE}, status_code=413)
        audio = await request.body()
        try:
            result = await run_in_threadpool(
                dictation.transcribe, store, speech, case_id, encounter_id, audio
            )
        except cases.NotFound as error:
            return case_api.not_found(error)
        except dictation.NoRecording as error:
            return JSONResponse({"detail": str(error)}, status_code=422)
        except dictation.RecordingTooLarge:
            return JSONResponse({"detail": TOO_LARGE}, status_code=413)
        except TranscriptionFailed as error:
            return JSONResponse({"detail": error.reason}, status_code=502)
        return JSONResponse(
            {"transcript": result.text, "outdates_proposal": result.outdates_proposal}
        )

    @router.post("/accept")
    def accept(case_id: int, encounter_id: int, raw: RawBody) -> Response:
        try:
            saved = dictation.accept(store, case_id, encounter_id, raw or {}, clock())
            return JSONResponse(case_api.opened_json(saved))
        except cases.NotFound as error:
            return case_api.not_found(error)
        except cases.Invalid as error:
            return case_api.invalid(error)

    return router
