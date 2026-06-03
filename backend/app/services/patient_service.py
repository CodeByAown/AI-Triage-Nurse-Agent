"""
Patient identity resolution (V4 Phase 2 — cross-conversation continuity).

A self-registered patient has a ``users`` row but no clinical ``patients`` record.
Without a stable patient identity, every triage conversation would create a fresh
throwaway patient and Maya could never remember anyone. This module resolves —
and lazily creates — the single persistent ``Patient`` that belongs to a login
account, linking it via ``patients.user_id``. All of that patient's assessments,
documents, and clinical facts then accumulate against one record.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.user import User


async def _default_organization_id(db: AsyncSession, user: User):
    """Pick the organization a self-service patient record should live under.

    Prefer the user's own org (clinic-invited patients); otherwise fall back to
    the first active organization (self-registered patients have no org)."""
    if user.organization_id is not None:
        return user.organization_id
    org = (
        await db.execute(select(Organization).where(Organization.is_active == True).limit(1))  # noqa: E712
    ).scalar_one_or_none()
    return org.id if org else None


async def resolve_patient_for_user(db: AsyncSession, user: User) -> Patient | None:
    """Return the persistent Patient linked to this user, creating it on first use.

    Idempotent: a user always maps to exactly one Patient (by ``user_id``). Returns
    None only if no organization exists to anchor the record (misconfigured install).
    """
    existing = (
        await db.execute(select(Patient).where(Patient.user_id == user.id))
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    org_id = await _default_organization_id(db, user)
    if org_id is None:
        logger.error("resolve_patient_no_org", user_id=str(user.id))
        return None

    patient = Patient(
        first_name=(user.first_name or "Patient").strip() or "Patient",
        last_name=(user.last_name or "").strip() or "Account",
        email=user.email,
        organization_id=org_id,
        user_id=user.id,
    )
    db.add(patient)
    await db.flush()
    await db.refresh(patient)
    logger.info("patient_record_created_for_user", user_id=str(user.id), patient_id=str(patient.id))
    return patient
