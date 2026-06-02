from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.models.assessment import Assessment, AssessmentStatus, TriageLevel, TriageReport, RiskScore

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard")
async def get_dashboard_stats(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=365),
) -> dict:
    """Main analytics dashboard metrics."""
    org_id = current_user.organization_id
    since = datetime.now(timezone.utc) - timedelta(days=days)

    base = select(Assessment).where(
        Assessment.organization_id == org_id,
        Assessment.created_at >= since,
    )

    # Total assessments
    total_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = total_result.scalar_one()

    # By status
    completed_result = await db.execute(
        select(func.count()).select_from(
            base.where(Assessment.status == AssessmentStatus.COMPLETED).subquery()
        )
    )
    completed = completed_result.scalar_one()

    escalated_result = await db.execute(
        select(func.count()).select_from(
            base.where(Assessment.status == AssessmentStatus.ESCALATED).subquery()
        )
    )
    escalated = escalated_result.scalar_one()

    # Emergency cases
    emergency_result = await db.execute(
        select(func.count()).select_from(
            base.where(Assessment.triage_level == TriageLevel.L1_EMERGENCY).subquery()
        )
    )
    emergency = emergency_result.scalar_one()

    # Urgent cases
    urgent_result = await db.execute(
        select(func.count()).select_from(
            base.where(Assessment.triage_level == TriageLevel.L2_URGENT).subquery()
        )
    )
    urgent = urgent_result.scalar_one()

    # Triage level distribution
    level_dist_result = await db.execute(
        select(Assessment.triage_level, func.count().label("count"))
        .where(
            Assessment.organization_id == org_id,
            Assessment.created_at >= since,
            Assessment.triage_level.isnot(None),
        )
        .group_by(Assessment.triage_level)
    )
    level_distribution = {
        row.triage_level.value: row.count
        for row in level_dist_result.all()
        if row.triage_level
    }

    # Average triage time (seconds)
    avg_time_result = await db.execute(
        select(
            func.avg(
                func.extract("epoch", Assessment.completed_at - Assessment.started_at)
            )
        ).where(
            Assessment.organization_id == org_id,
            Assessment.completed_at.isnot(None),
            Assessment.created_at >= since,
        )
    )
    avg_time_seconds = avg_time_result.scalar_one() or 0

    # Daily trend (last N days)
    daily_result = await db.execute(
        select(
            func.date_trunc("day", Assessment.created_at).label("day"),
            func.count().label("count"),
        )
        .where(
            Assessment.organization_id == org_id,
            Assessment.created_at >= since,
        )
        .group_by("day")
        .order_by("day")
    )
    daily_trend = [
        {"date": row.day.strftime("%Y-%m-%d"), "count": row.count}
        for row in daily_result.all()
    ]

    # High risk rate
    high_risk = emergency + urgent
    high_risk_rate = round((high_risk / total * 100), 1) if total > 0 else 0

    return {
        "period_days": days,
        "total_assessments": total,
        "completed_assessments": completed,
        "escalated_assessments": escalated,
        "emergency_cases": emergency,
        "urgent_cases": urgent,
        "high_risk_cases": high_risk,
        "high_risk_rate": high_risk_rate,
        "avg_triage_time_seconds": round(avg_time_seconds),
        "avg_triage_time_minutes": round(avg_time_seconds / 60, 1),
        "level_distribution": level_distribution,
        "daily_trend": daily_trend,
        "completion_rate": round((completed / total * 100), 1) if total > 0 else 0,
    }


@router.get("/risk-breakdown")
async def get_risk_breakdown(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30),
) -> dict:
    """Detailed risk category breakdown from risk scores."""
    org_id = current_user.organization_id
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(
            func.avg(RiskScore.cardiac_risk),
            func.avg(RiskScore.stroke_risk),
            func.avg(RiskScore.sepsis_risk),
            func.avg(RiskScore.respiratory_risk),
            func.avg(RiskScore.mental_health_risk),
            func.avg(RiskScore.anaphylaxis_risk),
            func.count(),
        )
        .join(Assessment, RiskScore.assessment_id == Assessment.id)
        .where(
            Assessment.organization_id == org_id,
            Assessment.created_at >= since,
        )
    )
    row = result.one()

    return {
        "cardiac_avg": round(float(row[0] or 0), 3),
        "stroke_avg": round(float(row[1] or 0), 3),
        "sepsis_avg": round(float(row[2] or 0), 3),
        "respiratory_avg": round(float(row[3] or 0), 3),
        "mental_health_avg": round(float(row[4] or 0), 3),
        "anaphylaxis_avg": round(float(row[5] or 0), 3),
        "total_scored": row[6] or 0,
    }
