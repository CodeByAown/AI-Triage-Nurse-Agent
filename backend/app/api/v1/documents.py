"""
Document upload & retrieval (V4 Phase 2).

Patients/providers upload medical files (labs, imaging, prescriptions, discharge
summaries, records) from the dashboard or from inside an active triage session.
Files are stored, text-extracted, structured, and folded into patient memory so
Maya remembers their contents.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, OptionalUser
from app.core.config import settings
from app.db.session import get_db
from app.models.assessment import Assessment
from app.models.document import Document, DocumentExtraction
from app.models.patient import Patient
from app.schemas.document import DocumentDetailOut, DocumentOut
from app.services import document_service
from app.services.storage import get_storage

router = APIRouter(prefix="/documents", tags=["Documents"])


async def _detail(db: AsyncSession, doc: Document) -> DocumentDetailOut:
    ext = (
        await db.execute(select(DocumentExtraction).where(DocumentExtraction.document_id == doc.id))
    ).scalar_one_or_none()
    out = DocumentDetailOut.model_validate(doc)
    if ext is not None:
        from app.schemas.document import DocumentExtractionOut

        out.extraction = DocumentExtractionOut.model_validate(ext)
    return out


async def _read_within_limit(file: UploadFile) -> bytes:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds the {settings.max_upload_mb} MB limit.")
    return data


@router.post("/upload", response_model=DocumentDetailOut, status_code=201)
async def upload_document(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
    patient_id: uuid.UUID = Form(...),
    doc_type: str | None = Form(default=None),
    assessment_id: uuid.UUID | None = Form(default=None),
) -> DocumentDetailOut:
    """Authenticated upload (provider/patient dashboard). Org-scoped to the patient."""
    patient = (
        await db.execute(
            select(Patient).where(
                Patient.id == patient_id,
                Patient.organization_id == current_user.organization_id,
            )
        )
    ).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    data = await _read_within_limit(file)
    doc = await document_service.save_upload(
        db,
        patient_id=patient.id,
        organization_id=patient.organization_id,
        data=data,
        filename=file.filename or "document",
        content_type=file.content_type,
        doc_type=doc_type,
        uploaded_by_user_id=current_user.id,
        assessment_id=assessment_id,
    )
    await document_service.process_document(db, doc)
    return await _detail(db, doc)


@router.post("/anonymous/upload", response_model=DocumentDetailOut, status_code=201)
async def upload_document_anonymous(
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
    session_token: str = Form(...),
    doc_type: str | None = Form(default=None),
) -> DocumentDetailOut:
    """Upload from inside an active (anonymous) triage session. The session token
    is the capability that ties the file to the right patient/assessment."""
    assessment = (
        await db.execute(select(Assessment).where(Assessment.session_token == session_token))
    ).scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Session not found")

    data = await _read_within_limit(file)
    doc = await document_service.save_upload(
        db,
        patient_id=assessment.patient_id,
        organization_id=assessment.organization_id,
        data=data,
        filename=file.filename or "document",
        content_type=file.content_type,
        doc_type=doc_type,
        assessment_id=assessment.id,
    )
    await document_service.process_document(db, doc)
    return await _detail(db, doc)


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    patient_id: uuid.UUID = Query(...),
) -> list[Document]:
    """List a patient's documents (org-scoped)."""
    patient = (
        await db.execute(
            select(Patient).where(
                Patient.id == patient_id,
                Patient.organization_id == current_user.organization_id,
            )
        )
    ).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    rows = (
        await db.execute(
            select(Document).where(Document.patient_id == patient_id).order_by(Document.created_at.desc())
        )
    ).scalars().all()
    return rows


@router.get("/{document_id}", response_model=DocumentDetailOut)
async def get_document(
    document_id: uuid.UUID,
    current_user: OptionalUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    session_token: str | None = Query(default=None),
) -> DocumentDetailOut:
    doc = (await db.execute(select(Document).where(Document.id == document_id))).scalar_one_or_none()
    await _authorize_document(db, doc, current_user, session_token)
    return await _detail(db, doc)


@router.get("/{document_id}/download")
async def download_document(
    document_id: uuid.UUID,
    current_user: OptionalUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    session_token: str | None = Query(default=None),
) -> Response:
    doc = (await db.execute(select(Document).where(Document.id == document_id))).scalar_one_or_none()
    await _authorize_document(db, doc, current_user, session_token)
    try:
        data = get_storage().read(doc.storage_path)
    except Exception:
        raise HTTPException(status_code=404, detail="File is no longer available.")
    return Response(
        content=data,
        media_type=doc.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{doc.original_filename}"'},
    )


async def _authorize_document(db, doc, current_user, session_token) -> None:
    """Access via the document's session_token (anonymous capability) OR an
    authenticated same-org user. 404 (not 403) to avoid leaking existence."""
    if doc is None:
        raise HTTPException(status_code=404, detail="Not found")
    if session_token:
        a = (
            await db.execute(select(Assessment).where(Assessment.id == doc.assessment_id))
        ).scalar_one_or_none() if doc.assessment_id else None
        if a is not None and a.session_token == session_token:
            return
    if (
        current_user is not None
        and current_user.organization_id is not None
        and doc.organization_id == current_user.organization_id
    ):
        return
    raise HTTPException(status_code=404, detail="Not found")
