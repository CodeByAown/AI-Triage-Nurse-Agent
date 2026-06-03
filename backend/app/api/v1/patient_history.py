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
