"""
Voice transcription endpoint (Phase 0 — Voice-to-Text).

Accepts a short audio recording captured in the browser (MediaRecorder) and
returns a plain-text transcript via OpenAI Whisper. The transcript is inserted
into the Chat with Maya input so the patient can edit it before sending — the
message itself still flows through the normal triage chat pipeline.

Stateless utility: no PHI is persisted here. Available to the anonymous triage
flow (no auth) so patients can use voice without an account.
"""
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import settings
from app.core.logging import logger

router = APIRouter(prefix="/voice", tags=["Voice"])

# OpenAI's audio API rejects files larger than 25 MB. Keep recordings short.
MAX_AUDIO_BYTES = 25 * 1024 * 1024
TRANSCRIBE_MODEL = "whisper-1"

# Lazily-built client so importing this module never requires a key at startup.
_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import AsyncOpenAI

        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)) -> dict:
    """Transcribe an uploaded audio clip to text.

    Returns ``{"text": "..."}``. Raises a calm, user-safe error otherwise — the
    frontend surfaces these and offers a retry.
    """
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="Voice transcription isn't available right now. Please type your message.",
        )

    audio = await file.read()
    if not audio:
        raise HTTPException(
            status_code=400,
            detail="We didn't receive any audio. Please try recording again.",
        )
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail="That recording is too long. Please keep it under a few minutes.",
        )

    filename = file.filename or "recording.webm"
    content_type = file.content_type or "audio/webm"

    try:
        result = await _get_client().audio.transcriptions.create(
            model=TRANSCRIBE_MODEL,
            file=(filename, audio, content_type),
        )
        text = (getattr(result, "text", "") or "").strip()
    except Exception:  # noqa: BLE001 — convert any provider/network error to a safe message
        logger.exception("voice_transcription_failed", filename=filename)
        raise HTTPException(
            status_code=502,
            detail="We couldn't transcribe that audio. Please try again.",
        )

    return {"text": text}
