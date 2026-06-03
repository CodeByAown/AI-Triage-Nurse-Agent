"""
Patient memory & continuity-of-care models (V3/V4 Phase 1).

These tables give Maya a durable, cross-conversation memory so she remembers and
reasons about a patient's history rather than treating each assessment in
isolation. Status/type fields are stored as plain strings (validated by the
Python enums below) rather than native PostgreSQL enums — this keeps migrations
fully additive and reversible.

All rows are scoped by ``patient_id`` (and ``organization_id`` for tenant
isolation). Nothing here is required by the existing triage flow; it is written
*alongside* it, so current functionality is preserved.
"""
import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:  # pragma: no cover
    pass


# ── Controlled vocabularies (app-level validation; stored as strings) ──────────
class FactCategory(str, enum.Enum):
    CONDITION = "condition"
    MEDICATION = "medication"
    ALLERGY = "allergy"
    VITAL = "vital"
    LAB = "lab"
    SYMPTOM_HISTORY = "symptom_history"
    PROCEDURE = "procedure"
    LIFESTYLE = "lifestyle"
    OTHER = "other"


class FactStatus(str, enum.Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RESOLVED = "resolved"
    REFUTED = "refuted"


class FactSource(str, enum.Enum):
    PATIENT_REPORTED = "patient_reported"
    VOICE_REPORTED = "voice_reported"
    DOCUMENT_EXTRACTED = "document_extracted"
    CLINICIAN_ENTERED = "clinician_entered"
    MAYA_INFERRED = "maya_inferred"


class ThreadStatus(str, enum.Enum):
    OPEN = "open"
    MONITORING = "monitoring"
    RESOLVED = "resolved"


class CareActionType(str, enum.Enum):
    RECOMMENDATION = "recommendation"
    REFERRAL = "referral"
    SELF_MONITORING = "self_monitoring"
    MEDICATION = "medication"
    LAB_ORDER = "lab_order"
    FOLLOW_UP = "follow_up"


class CareActionStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DECLINED = "declined"
    EXPIRED = "expired"


class TimelineEventType(str, enum.Enum):
    ASSESSMENT = "assessment"
    DOCUMENT = "document"
    OBSERVATION = "observation"
    MEDICATION = "medication"
    FOLLOW_UP = "follow_up"
    CLINICAL_FACT = "clinical_fact"
    ESCALATION = "escalation"
    NOTE = "note"


# ── Continuity of care ────────────────────────────────────────────────────────
class CareThread(Base, UUIDMixin, TimestampMixin):
    """A persistent health concern that spans multiple visits (V4 §2.1)."""

    __tablename__ = "care_threads"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=ThreadStatus.OPEN.value, nullable=False)
    severity: Mapped[str | None] = mapped_column(String(50))
    summary: Mapped[str | None] = mapped_column(Text)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_touched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CareAction(Base, UUIDMixin, TimestampMixin):
    """An unfinished care action ('open loop') Maya tracks across visits (V4 §2.2)."""

    __tablename__ = "care_actions"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    thread_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("care_threads.id", ondelete="SET NULL"), index=True
    )
    assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="SET NULL"), index=True
    )
    type: Mapped[str] = mapped_column(String(30), default=CareActionType.RECOMMENDATION.value, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=CareActionStatus.OPEN.value, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_via: Mapped[str | None] = mapped_column(String(30))


# ── Clinical facts (the core memory substrate) ────────────────────────────────
class ClinicalFact(Base, UUIDMixin, TimestampMixin):
    """A single durable clinical fact about a patient with provenance + lifecycle.

    Examples: condition 'Hypertension', medication 'Lisinopril 10mg',
    lab 'HbA1c = 8.2%'. Facts transition through statuses (V4 §2) and are never
    hard-deleted, preserving an auditable history.
    """

    __tablename__ = "clinical_facts"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str | None] = mapped_column(Text)
    value_num: Mapped[float | None] = mapped_column(Float)  # for trends (e.g. 8.2)
    unit: Mapped[str | None] = mapped_column(String(50))

    status: Mapped[str] = mapped_column(String(20), default=FactStatus.ACTIVE.value, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(30), default=FactSource.PATIENT_REPORTED.value, nullable=False)
    source_confidence: Mapped[float | None] = mapped_column(Float)

    source_assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="SET NULL"), index=True
    )
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), index=True
    )

    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_by_fact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinical_facts.id", ondelete="SET NULL")
    )
    last_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    fact_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)


# ── Per-assessment memory (Maya's narrative of one visit) ──────────────────────
class AssessmentMemory(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "assessment_memory"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    summary: Mapped[str | None] = mapped_column(Text)
    chief_complaint: Mapped[str | None] = mapped_column(Text)
    key_findings: Mapped[list] = mapped_column(JSONB, default=list)
    recommendations: Mapped[list] = mapped_column(JSONB, default=list)
    triage_level: Mapped[str | None] = mapped_column(String(30))


# ── Longitudinal patient insights (trends / behavioral observations) ───────────
class PatientInsight(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "patient_insights"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    insight_type: Mapped[str] = mapped_column(String(40), nullable=False)  # trend|behavioral|risk
    content: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    evidence: Mapped[list] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── Timeline (unified chronological record) ────────────────────────────────────
class TimelineEvent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "timeline_events"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    severity: Mapped[str | None] = mapped_column(String(50))
    # Polymorphic pointer to the originating row (assessment/document/observation…)
    source_type: Mapped[str | None] = mapped_column(String(40))
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    event_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
