import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.session_manager import create_session, process_message
from app.api.deps import CurrentUser
from app.db.session import get_db
from app.models.assessment import Assessment, AssessmentStatus, Conversation, TriageReport
from app.models.patient import Patient
from app.schemas.assessment import (
    AssessmentCreate,
    AssessmentOut,
    ConversationMessageOut,
    TriageMessageRequest,
    TriageMessageResponse,
    TriageReportOut,
)
from app.services.audit import write_audit

router = APIRouter(prefix="/triage", tags=["Triage"])


@router.get("/assessments", response_model=dict)
async def list_assessments(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
) -> dict:
    """List all assessments for the current organization."""
    base = select(Assessment).where(
        Assessment.organization_id == current_user.organization_id
    )
    if status_filter:
        try:
            base = base.where(Assessment.status == AssessmentStatus(status_filter))
        except ValueError:
            pass

    count_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = count_result.scalar_one()

    result = await db.execute(
        base.order_by(Assessment.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    assessments = result.scalars().all()

    return {
        "items": [AssessmentOut.model_validate(a).model_dump(mode="json") for a in assessments],
        "total": int(total),
        "page": page,
        "size": size,
        "pages": math.ceil(total / size) if total > 0 else 0,
    }


@router.post("/sessions", response_model=AssessmentOut, status_code=status.HTTP_201_CREATED)
async def start_triage_session(
    payload: AssessmentCreate,
    request: Request,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Assessment:
    patient_result = await db.execute(
        select(Patient).where(
            Patient.id == payload.patient_id,
            Patient.organization_id == current_user.organization_id,
        )
    )
    patient = patient_result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    assessment = await create_session(
        db=db,
        patient_id=payload.patient_id,
        organization_id=current_user.organization_id,
    )
    if payload.chief_complaint:
        assessment.chief_complaint = payload.chief_complaint

    await write_audit(
        db,
        action="triage_started",
        resource_type="assessment",
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        resource_id=str(assessment.id),
        ip_address=request.client.host if request.client else None,
        metadata={"patient_id": str(payload.patient_id), "session_token": assessment.session_token},
    )

    return assessment


@router.post("/message", response_model=TriageMessageResponse)
async def send_triage_message(
    payload: TriageMessageRequest,
    request: Request,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TriageMessageResponse:
    session_result = await db.execute(
        select(Assessment).where(
            Assessment.session_token == payload.session_token,
            Assessment.organization_id == current_user.organization_id,
        )
    )
    assessment = session_result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await process_message(
        db=db,
        session_token=payload.session_token,
        user_message=payload.message,
    )

    if result["is_complete"]:
        await write_audit(
            db,
            action="triage_completed",
            resource_type="assessment",
            user_id=current_user.id,
            organization_id=current_user.organization_id,
            resource_id=str(assessment.id),
            metadata={
                "triage_level": result.get("triage_level"),
                "requires_escalation": result.get("requires_escalation", False),
            },
        )

    return TriageMessageResponse(
        message=result["message"],
        node=result["node"],
        is_complete=result["is_complete"],
        requires_escalation=result["requires_escalation"],
        triage_level=result.get("triage_level"),
    )


@router.post("/anonymous/start")
async def start_anonymous_session(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    from app.models.organization import Organization

    org_result = await db.execute(
        select(Organization).where(Organization.is_active == True).limit(1)
    )
    org = org_result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=503, detail="No active organization found")

    patient = Patient(
        first_name="Anonymous",
        last_name="Patient",
        organization_id=org.id,
    )
    db.add(patient)
    await db.flush()

    assessment = await create_session(
        db=db,
        patient_id=patient.id,
        organization_id=org.id,
    )

    await write_audit(
        db,
        action="triage_started",
        resource_type="assessment",
        organization_id=org.id,
        resource_id=str(assessment.id),
        metadata={"anonymous": True, "session_token": assessment.session_token},
    )

    return {
        "session_token": assessment.session_token,
        "assessment_id": str(assessment.id),
    }


@router.post("/anonymous/message")
async def send_anonymous_message(
    payload: TriageMessageRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TriageMessageResponse:
    session_result = await db.execute(
        select(Assessment).where(Assessment.session_token == payload.session_token)
    )
    assessment = session_result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await process_message(
        db=db,
        session_token=payload.session_token,
        user_message=payload.message,
    )

    if result["is_complete"]:
        await write_audit(
            db,
            action="triage_completed",
            resource_type="assessment",
            organization_id=assessment.organization_id,
            resource_id=str(assessment.id),
            metadata={
                "triage_level": result.get("triage_level"),
                "requires_escalation": result.get("requires_escalation", False),
                "anonymous": True,
            },
        )

    return TriageMessageResponse(
        message=result["message"],
        node=result["node"],
        is_complete=result["is_complete"],
        requires_escalation=result["requires_escalation"],
        triage_level=result.get("triage_level"),
    )


@router.get("/sessions/{session_token}/conversation", response_model=list[ConversationMessageOut])
async def get_conversation(
    session_token: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Conversation]:
    result = await db.execute(
        select(Assessment).where(Assessment.session_token == session_token)
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Session not found")

    conv_result = await db.execute(
        select(Conversation)
        .where(Conversation.assessment_id == assessment.id)
        .order_by(Conversation.created_at)
    )
    return conv_result.scalars().all()


@router.get("/reports/{assessment_id}", response_model=TriageReportOut)
async def get_triage_report(
    assessment_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TriageReport:
    result = await db.execute(
        select(TriageReport).where(TriageReport.assessment_id == assessment_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found or not yet generated")
    return report


@router.get("/sessions/{assessment_id}", response_model=AssessmentOut)
async def get_assessment(
    assessment_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Assessment:
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return assessment
