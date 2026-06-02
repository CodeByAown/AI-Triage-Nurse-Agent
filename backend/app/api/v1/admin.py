import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_role
from app.core.security import hash_password
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.assessment import Assessment
from app.models.user import User, UserRole
from app.schemas.auth import AdminCreateUserRequest
from app.schemas.user import UserOut
from app.services.audit import write_audit

router = APIRouter(prefix="/admin", tags=["Admin"])

AdminRequired = Depends(require_role(UserRole.ADMIN, UserRole.SUPER_ADMIN))


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED, dependencies=[AdminRequired])
async def create_user(
    payload: AdminCreateUserRequest,
    request: Request,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Create a team member (e.g. a provider/nurse) inside the admin's organization."""
    try:
        role = UserRole(payload.role)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid role: {payload.role}")

    # Only a super_admin may mint another super_admin.
    if role == UserRole.SUPER_ADMIN and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Cannot create a super_admin")

    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        role=role,
        organization_id=current_user.organization_id,
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    await write_audit(
        db,
        action="user_created",
        resource_type="user",
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        resource_id=str(user.id),
        ip_address=request.client.host if request.client else None,
        metadata={"email": user.email, "role": role.value},
    )
    return user


@router.get("/users", response_model=dict, dependencies=[AdminRequired])
async def list_users(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
) -> dict:
    base = select(User).where(User.organization_id == current_user.organization_id)
    if search:
        base = base.where(
            (User.first_name.ilike(f"%{search}%"))
            | (User.last_name.ilike(f"%{search}%"))
            | (User.email.ilike(f"%{search}%"))
        )

    count_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = count_result.scalar_one()
    result = await db.execute(base.offset((page - 1) * size).limit(size))
    users = result.scalars().all()

    return {
        "items": [UserOut.model_validate(u).model_dump(mode="json") for u in users],
        "total": int(total),
        "page": page,
        "size": size,
        "pages": math.ceil(total / size) if total > 0 else 0,
    }


@router.patch("/users/{user_id}/role", dependencies=[AdminRequired])
async def update_user_role(
    user_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    role: UserRole = Query(...),
) -> dict:
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.organization_id == current_user.organization_id,
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if current_user.role != UserRole.SUPER_ADMIN and role == UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Cannot assign super_admin role")

    old_role = user.role.value
    user.role = role
    await db.flush()

    await write_audit(
        db,
        action="user_role_changed",
        resource_type="user",
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        resource_id=str(user_id),
        ip_address=request.client.host if request.client else None,
        metadata={"old_role": old_role, "new_role": role.value, "target_user_id": str(user_id)},
    )

    return {"message": f"Role updated to {role.value}"}


@router.patch("/users/{user_id}/deactivate", dependencies=[AdminRequired])
async def deactivate_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.organization_id == current_user.organization_id,
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    user.is_active = False
    await db.flush()

    await write_audit(
        db,
        action="user_deactivated",
        resource_type="user",
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        resource_id=str(user_id),
        ip_address=request.client.host if request.client else None,
        metadata={"target_email": user.email, "target_user_id": str(user_id)},
    )

    return {"message": "User deactivated"}


@router.get("/audit-logs", dependencies=[AdminRequired])
async def get_audit_logs(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, le=200),
    action: str | None = None,
) -> dict:
    base = select(AuditLog).where(AuditLog.organization_id == current_user.organization_id)
    if action:
        base = base.where(AuditLog.action == action)

    count_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = count_result.scalar_one()
    result = await db.execute(
        base.order_by(AuditLog.created_at.desc()).offset((page - 1) * size).limit(size)
    )
    logs = result.scalars().all()

    return {
        "items": [
            {
                "id": str(log.id),
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "user_id": str(log.user_id) if log.user_id else None,
                "ip_address": log.ip_address,
                "status": log.status,
                "created_at": log.created_at.isoformat(),
                "metadata": log.log_metadata,
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "size": size,
        "pages": math.ceil(total / size) if total > 0 else 0,
    }


@router.get("/overview", dependencies=[AdminRequired])
async def admin_overview(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    org_id = current_user.organization_id

    user_count = await db.execute(
        select(func.count()).where(User.organization_id == org_id)
    )
    assessment_count = await db.execute(
        select(func.count()).where(Assessment.organization_id == org_id)
    )

    return {
        "total_users": user_count.scalar_one(),
        "total_assessments": assessment_count.scalar_one(),
    }
