"""
Patient history & timeline API (V4 Phase 4).

Exposes the assembled memory for a patient: a unified timeline (assessments,
documents, observations, follow-ups…) and the active clinical facts / open care
actions. Backend + API only — frontend visualization can come later.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.models.assessment import Assessment
from app.models.document import Document
from app.models.memory import CareAction, CareActionStatus, ClinicalFact, FactStatus, TimelineEvent
from app.models.patient import Patient
from app.schemas.document import (
    CareActionOut,
    ClinicalFactOut,
    PatientMemoryOut,
    TimelineEventOut,
)
from app.services.context_service import get_patient_history_block

router = APIRouter(prefix="/patients", tags=["Patient History"])


@router.get("/me/summary", response_model=dict)
async def get_my_patient_summary(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Everything the patient's own dashboard needs, in one call: profile,
    remembered clinical facts, open follow-ups, recent assessments, uploaded
    documents, and the recent timeline. Resolves the patient by the login's
    ``user_id`` link; returns empty collections for a brand-new account."""
    patient = (
        await db.execute(select(Patient).where(Patient.user_id == current_user.id))
    ).scalar_one_or_none()

    empty = {
        "patient": None,
        "facts": [],
        "open_actions": [],
        "assessments": [],
        "documents": [],
        "timeline": [],
    }
    if patient is None:
        empty["patient"] = {
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
        }
        return empty

    facts = (
        await db.execute(
            select(ClinicalFact)
            .where(ClinicalFact.patient_id == patient.id, ClinicalFact.status == FactStatus.ACTIVE.value)
            .order_by(ClinicalFact.category, ClinicalFact.updated_at.desc())
        )
    ).scalars().all()

    actions = (
        await db.execute(
            select(CareAction)
            .where(
                CareAction.patient_id == patient.id,
                CareAction.status.in_([CareActionStatus.OPEN.value, CareActionStatus.IN_PROGRESS.value]),
            )
            .order_by(CareAction.due_at.asc().nullslast())
        )
    ).scalars().all()

    assessments = (
        await db.execute(
            select(Assessment)
            .where(Assessment.patient_id == patient.id)
            .order_by(Assessment.created_at.desc())
            .limit(20)
        )
    ).scalars().all()

    documents = (
        await db.execute(
            select(Document)
            .where(Document.patient_id == patient.id)
            .order_by(Document.created_at.desc())
            .limit(20)
        )
    ).scalars().all()

    timeline = (
        await db.execute(
            select(TimelineEvent)
            .where(TimelineEvent.patient_id == patient.id)
            .order_by(TimelineEvent.occurred_at.desc())
            .limit(30)
        )
    ).scalars().all()

    return {
        "patient": {
            "id": str(patient.id),
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "age": patient.age,
            "biological_sex": patient.biological_sex.value if patient.biological_sex else None,
        },
        "facts": [ClinicalFactOut.model_validate(f).model_dump(mode="json") for f in facts],
        "open_actions": [CareActionOut.model_validate(a).model_dump(mode="json") for a in actions],
        "assessments": [
            {
                "id": str(a.id),
                "session_token": a.session_token,
                "chief_complaint": a.chief_complaint,
                "triage_level": a.triage_level.value if a.triage_level else None,
                "status": a.status.value if a.status else None,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
            }
            for a in assessments
        ],
        "documents": [
            {
                "id": str(d.id),
                "doc_type": d.doc_type,
                "original_filename": d.original_filename,
                "status": d.status,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in documents
        ],
        "timeline": [TimelineEventOut.model_validate(e).model_dump(mode="json") for e in timeline],
    }


async def _require_patient(db: AsyncSession, patient_id: uuid.UUID, current_user) -> Patient:
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
    return patient


@router.get("/{patient_id}/timeline", response_model=list[TimelineEventOut])
async def get_patient_timeline(
    patient_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=100, ge=1, le=500),
) -> list[TimelineEvent]:
    """Unified chronological timeline for a patient (most recent first)."""
    await _require_patient(db, patient_id, current_user)
    rows = (
        await db.execute(
            select(TimelineEvent)
            .where(TimelineEvent.patient_id == patient_id)
            .order_by(TimelineEvent.occurred_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return rows


@router.get("/{patient_id}/memory", response_model=PatientMemoryOut)
async def get_patient_memory(
    patient_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PatientMemoryOut:
    """Active clinical facts + open care actions + the rendered history block
    (exactly what Maya sees)."""
    await _require_patient(db, patient_id, current_user)

    facts = (
        await db.execute(
            select(ClinicalFact)
            .where(ClinicalFact.patient_id == patient_id, ClinicalFact.status == FactStatus.ACTIVE.value)
            .order_by(ClinicalFact.category, ClinicalFact.updated_at.desc())
        )
    ).scalars().all()

    actions = (
        await db.execute(
            select(CareAction)
            .where(
                CareAction.patient_id == patient_id,
                CareAction.status.in_([CareActionStatus.OPEN.value, CareActionStatus.IN_PROGRESS.value]),
            )
            .order_by(CareAction.due_at.asc().nullslast())
        )
    ).scalars().all()

    history_block = await get_patient_history_block(db, patient_id)

    return PatientMemoryOut(
        facts=[ClinicalFactOut.model_validate(f) for f in facts],
        open_actions=[CareActionOut.model_validate(a) for a in actions],
        history_block=history_block,
    )
