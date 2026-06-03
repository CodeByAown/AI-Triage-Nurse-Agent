"""
Medical document processing (V4 Phase 2).

Pipeline:  upload → store original → extract text → structure findings (LLM) →
write into patient memory (clinical_facts + timeline_event + observation).

Text extraction:
  • PDFs  → PyMuPDF (fitz) text layer.
  • Images → gpt-4o vision (base64).
Structuring: a single LLM pass turns the raw text into {label, value, unit}
findings + a one-line summary + a doc_type guess. Lab values become clinical
facts so Maya remembers them (e.g. HbA1c 8.2%).

Everything is defensive: a failed extraction marks the document
``extraction_failed`` but never raises to the caller — the upload still succeeds.
"""
from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.document import (
    Document,
    DocumentExtraction,
    DocumentStatus,
    DocumentType,
    ObservationModality,
)
from app.models.memory import FactCategory, FactSource, TimelineEventType
from app.services import memory_service
from app.services.storage import get_storage

_client = None


def _client_or_none():
    global _client
    if not settings.openai_api_key:
        return None
    if _client is None:
        from openai import AsyncOpenAI

        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


def _guess_doc_type(filename: str, content_type: str | None) -> str:
    name = (filename or "").lower()
    if any(k in name for k in ("lab", "blood", "cbc", "panel", "result")):
        return DocumentType.LAB_REPORT.value
    if any(k in name for k in ("rx", "prescription", "script")):
        return DocumentType.PRESCRIPTION.value
    if any(k in name for k in ("discharge", "summary")):
        return DocumentType.DISCHARGE_SUMMARY.value
    if any(k in name for k in ("xray", "x-ray", "mri", "ct", "ultrasound", "imaging", "radiology")):
        return DocumentType.IMAGING_REPORT.value
    if (content_type or "").startswith("image/"):
        return DocumentType.IMAGING_REPORT.value
    if any(k in name for k in ("record", "history", "report")):
        return DocumentType.MEDICAL_RECORD.value
    return DocumentType.OTHER.value


def _extract_pdf_text(data: bytes) -> str:
    import fitz  # PyMuPDF

    text_parts: list[str] = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            text_parts.append(page.get_text())
    return "\n".join(text_parts).strip()


async def _extract_image_text(data: bytes, content_type: str) -> str:
    client = _client_or_none()
    if client is None:
        return ""
    b64 = base64.b64encode(data).decode("ascii")
    resp = await client.chat.completions.create(
        model=settings.openai_model,
        max_tokens=1500,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Transcribe ALL text and numeric values visible in this medical document image. Output the raw text only."},
                    {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{b64}"}},
                ],
            }
        ],
    )
    return (resp.choices[0].message.content or "").strip()


_STRUCTURE_PROMPT = (
    "You are a clinical data extractor. Given the raw text of a medical document, "
    "return STRICT JSON with keys: "
    '"doc_type" (one of lab_report, imaging_report, prescription, discharge_summary, medical_record, other), '
    '"summary" (one concise sentence), '
    '"findings" (array of objects with keys: "category" one of [lab, vital, medication, condition, procedure, other], '
    '"label" (e.g. "HbA1c"), "value" (string, e.g. "8.2"), "unit" (e.g. "%", or null), '
    '"abnormal" (true/false/null)). '
    "Only include findings actually present. Do not invent values. Return JSON only, no prose."
)


async def _structure_text(text: str) -> dict:
    client = _client_or_none()
    if client is None or not text.strip():
        return {}
    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            max_tokens=1200,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _STRUCTURE_PROMPT},
                {"role": "user", "content": text[:12000]},
            ],
        )
        raw = resp.choices[0].message.content or "{}"
        return json.loads(raw)
    except Exception as e:  # noqa: BLE001
        logger.error("document_structuring_failed", error=str(e))
        return {}


async def save_upload(
    db: AsyncSession,
    *,
    patient_id: uuid.UUID,
    organization_id: uuid.UUID | None,
    data: bytes,
    filename: str,
    content_type: str | None,
    doc_type: str | None = None,
    uploaded_by_user_id: uuid.UUID | None = None,
    assessment_id: uuid.UUID | None = None,
) -> Document:
    """Store the original file and create the Document row (status=uploaded)."""
    storage = get_storage()
    storage_path = storage.save(patient_id=patient_id, filename=filename, data=data)
    doc = Document(
        patient_id=patient_id,
        organization_id=organization_id,
        uploaded_by_user_id=uploaded_by_user_id,
        assessment_id=assessment_id,
        doc_type=doc_type or _guess_doc_type(filename, content_type),
        original_filename=filename[:500],
        content_type=content_type,
        file_size=len(data),
        storage_backend=storage.backend,
        storage_path=storage_path,
        status=DocumentStatus.UPLOADED.value,
    )
    db.add(doc)
    await db.flush()
    return doc


async def process_document(db: AsyncSession, document: Document) -> DocumentExtraction | None:
    """Extract text, structure findings, and write them into patient memory.

    Returns the DocumentExtraction (or None on failure). Sets the document status.
    """
    document.status = DocumentStatus.PROCESSING.value
    await db.flush()

    try:
        data = get_storage().read(document.storage_path)
        ctype = (document.content_type or "").lower()

        if ctype == "application/pdf" or document.original_filename.lower().endswith(".pdf"):
            text = _extract_pdf_text(data)
            modality = ObservationModality.PDF.value
        elif ctype.startswith("image/"):
            text = await _extract_image_text(data, document.content_type or "image/png")
            modality = ObservationModality.IMAGE.value
        else:
            # Best-effort: try decoding as UTF-8 text.
            try:
                text = data.decode("utf-8", errors="ignore").strip()
            except Exception:  # noqa: BLE001
                text = ""
            modality = ObservationModality.NOTE.value

        structured = await _structure_text(text)
        findings = structured.get("findings") or []
        summary = structured.get("summary") or None
        # Refine doc_type from the model if the upload didn't specify one well.
        model_doc_type = structured.get("doc_type")
        if model_doc_type and document.doc_type == DocumentType.OTHER.value:
            document.doc_type = model_doc_type

        extraction = DocumentExtraction(
            document_id=document.id,
            patient_id=document.patient_id,
            extracted_text=text or None,
            structured=findings,
            summary=summary,
            model_used=settings.openai_model if settings.openai_api_key else None,
        )
        db.add(extraction)
        await db.flush()

        now = datetime.now(timezone.utc)

        # Timeline event for the upload.
        await memory_service.add_timeline_event(
            db,
            patient_id=document.patient_id,
            organization_id=document.organization_id,
            event_type=TimelineEventType.DOCUMENT.value,
            title=f"{document.doc_type.replace('_', ' ').title()}: {document.original_filename}",
            description=summary,
            occurred_at=document.created_at or now,
            source_type="document",
            source_id=document.id,
        )

        # One observation capturing the whole document (multi-modal substrate).
        await memory_service.record_observation(
            db,
            patient_id=document.patient_id,
            organization_id=document.organization_id,
            source_modality=modality,
            observation_type="document_extraction",
            content=(summary or (text[:500] if text else document.original_filename)),
            structured={"findings": findings},
            source_type="document",
            source_id=document.id,
            observed_at=document.created_at or now,
        )

        # Turn lab/vital/medication/condition findings into durable clinical facts.
        cat_map = {
            "lab": FactCategory.LAB.value,
            "vital": FactCategory.VITAL.value,
            "medication": FactCategory.MEDICATION.value,
            "condition": FactCategory.CONDITION.value,
            "procedure": FactCategory.PROCEDURE.value,
        }
        for f in findings:
            if not isinstance(f, dict):
                continue
            label = f.get("label")
            if not label:
                continue
            category = cat_map.get(str(f.get("category", "")).lower(), FactCategory.OTHER.value)
            value = f.get("value")
            value_str = str(value) if value is not None else None
            value_num = None
            try:
                if value is not None:
                    value_num = float(str(value).split()[0].replace("%", "").replace(",", ""))
            except (ValueError, IndexError):
                value_num = None
            await memory_service.upsert_clinical_fact(
                db,
                patient_id=document.patient_id,
                organization_id=document.organization_id,
                category=category,
                label=str(label),
                value=value_str,
                value_num=value_num,
                unit=f.get("unit"),
                source=FactSource.DOCUMENT_EXTRACTED.value,
                source_confidence=0.8,
                source_document_id=document.id,
                observed_at=document.created_at or now,
            )

        document.status = DocumentStatus.EXTRACTED.value
        await db.flush()
        logger.info(
            "document_processed",
            document_id=str(document.id),
            findings=len(findings),
            chars=len(text or ""),
        )
        return extraction

    except Exception as e:  # noqa: BLE001
        logger.error("document_processing_failed", error=str(e), document_id=str(document.id))
        document.status = DocumentStatus.EXTRACTION_FAILED.value
        document.error_detail = str(e)[:1000]
        await db.flush()
        return None
