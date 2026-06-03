"""
Voice transcription endpoint (Phase 0 — Voice-to-Text; Phase 5 — Voice Memory).

Accepts a short audio recording captured in the browser (MediaRecorder) and
returns a plain-text transcript via OpenAI Whisper. The transcript is inserted
into the Chat with Maya input so the patient can edit it before sending — the
message itself still flows through the normal triage chat pipeline.

Phase 5: when the request carries a ``session_token``, the transcript is also
recorded as a voice ``patient_observation`` so spoken input enters patient memory
exactly like typed input (Voice → Transcript → Observation → … → History).
"""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.db.session import get_db
from app.models.assessment import Assessment
from app.models.document import ObservationModality
from app.services import memory_service

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
async def transcribe_audio(
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
    session_token: str | None = Form(default=None),
) -> dict:
    """Transcribe an uploaded audio clip to text.

    Returns ``{"text": "..."}``. Raises a calm, user-safe error otherwise — the
    frontend surfaces these and offers a retry. When ``session_token`` is present,
    the transcript is also captured as a voice observation in patient memory.
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

    # Phase 5: record the spoken input into patient memory (best-effort, never
    # blocks the transcript response). Tied to the patient via the session token.
    if text and session_token:
        try:
            assessment = (
                await db.execute(select(Assessment).where(Assessment.session_token == session_token))
            ).scalar_one_or_none()
            if assessment is not None:
                await memory_service.record_observation(
                    db,
                    patient_id=assessment.patient_id,
                    organization_id=assessment.organization_id,
                    source_modality=ObservationModality.VOICE.value,
                    observation_type="spoken_message",
                    content=text,
                    source_type="assessment",
                    source_id=assessment.id,
                    observed_at=datetime.now(timezone.utc),
                )
        except Exception as e:  # noqa: BLE001
            logger.error("voice_observation_failed", error=str(e))

    return {"text": text}
