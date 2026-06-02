import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.models.patient import Patient
from app.schemas.patient import PatientCreate, PatientOut, PatientUpdate

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.post("/", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
async def create_patient(
    payload: PatientCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Patient:
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User must belong to an organization")

    patient = Patient(
        **payload.model_dump(),
        organization_id=current_user.organization_id,
    )
    db.add(patient)
    await db.flush()
    await db.refresh(patient)
    return patient


@router.get("/", response_model=dict)
async def list_patients(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
) -> dict:
    if not current_user.organization_id:
        return {"items": [], "total": 0, "page": page, "size": size, "pages": 0}

    base_query = select(Patient).where(
        Patient.organization_id == current_user.organization_id,
        Patient.is_active == True,
    )

    if search:
        base_query = base_query.where(
            (Patient.first_name.ilike(f"%{search}%"))
            | (Patient.last_name.ilike(f"%{search}%"))
            | (Patient.email.ilike(f"%{search}%"))
        )

    count_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = count_result.scalar_one()

    result = await db.execute(
        base_query.offset((page - 1) * size).limit(size).order_by(Patient.created_at.desc())
    )
    patients = result.scalars().all()

    return {
        "items": [PatientOut.model_validate(p).model_dump(mode="json") for p in patients],
        "total": int(total),
        "page": page,
        "size": size,
        "pages": math.ceil(total / size) if total > 0 else 0,
    }


@router.get("/{patient_id}", response_model=PatientOut)
async def get_patient(
    patient_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Patient:
    result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.organization_id == current_user.organization_id,
        )
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.patch("/{patient_id}", response_model=PatientOut)
async def update_patient(
    patient_id: uuid.UUID,
    payload: PatientUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Patient:
    result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.organization_id == current_user.organization_id,
        )
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(patient, field, value)

    await db.flush()
    await db.refresh(patient)
    return patient
