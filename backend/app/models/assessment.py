import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.patient import Patient


class TriageLevel(str, enum.Enum):
    L1_EMERGENCY = "L1_EMERGENCY"
    L2_URGENT = "L2_URGENT"
    L3_MODERATE = "L3_MODERATE"
    L4_LOW_RISK = "L4_LOW_RISK"
    L5_SELF_CARE = "L5_SELF_CARE"


class AssessmentStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ESCALATED = "escalated"
    ABANDONED = "abandoned"


class MessageRole(str, enum.Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


def _ev(cls):
    """Use enum .value (not .name) for PostgreSQL native enum storage."""
    return [e.value for e in cls]


class Assessment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "assessments"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_token: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    status: Mapped[AssessmentStatus] = mapped_column(
        Enum(AssessmentStatus, values_callable=_ev, create_type=False),
        default=AssessmentStatus.PENDING, nullable=False, index=True
    )
    triage_level: Mapped[TriageLevel | None] = mapped_column(
        Enum(TriageLevel, values_callable=_ev, create_type=False)
    )
    urgency_score: Mapped[float | None] = mapped_column(Float)
    confidence_score: Mapped[float | None] = mapped_column(Float)

    chief_complaint: Mapped[str | None] = mapped_column(Text)
    ai_model_used: Mapped[str | None] = mapped_column(String(100))

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # LangGraph state snapshot (for resumability)
    graph_state: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relationships
    patient: Mapped["Patient"] = relationship("Patient", back_populates="assessments")
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="assessment", cascade="all, delete-orphan",
        order_by="Conversation.created_at"
    )
    symptoms: Mapped[list["Symptom"]] = relationship(
        "Symptom", back_populates="assessment", cascade="all, delete-orphan"
    )
    risk_factors: Mapped[list["RiskFactor"]] = relationship(
        "RiskFactor", back_populates="assessment", cascade="all, delete-orphan"
    )
    triage_report: Mapped["TriageReport | None"] = relationship(
        "TriageReport", back_populates="assessment", uselist=False, cascade="all, delete-orphan"
    )
    risk_score: Mapped["RiskScore | None"] = relationship(
        "RiskScore", back_populates="assessment", uselist=False, cascade="all, delete-orphan"
    )


class Conversation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "conversations"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, values_callable=_ev, create_type=False), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    node_name: Mapped[str | None] = mapped_column(String(100))
    msg_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    assessment: Mapped["Assessment"] = relationship("Assessment", back_populates="conversations")


class Symptom(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "symptoms"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[int | None] = mapped_column(Integer)  # 1-10 scale
    duration: Mapped[str | None] = mapped_column(String(100))
    onset: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255))
    character: Mapped[str | None] = mapped_column(String(255))
    radiation: Mapped[str | None] = mapped_column(String(255))
    aggravating_factors: Mapped[list] = mapped_column(JSONB, default=list)
    relieving_factors: Mapped[list] = mapped_column(JSONB, default=list)
    is_primary: Mapped[bool] = mapped_column(default=False)

    assessment: Mapped["Assessment"] = relationship("Assessment", back_populates="symptoms")


class RiskFactor(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "risk_factors"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    factor_type: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    is_emergency_flag: Mapped[bool] = mapped_column(default=False)
    severity: Mapped[str | None] = mapped_column(String(50))

    assessment: Mapped["Assessment"] = relationship("Assessment", back_populates="risk_factors")


class TriageReport(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "triage_reports"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # Structured report sections
    patient_summary: Mapped[str] = mapped_column(Text, nullable=False)
    symptoms_summary: Mapped[str] = mapped_column(Text, nullable=False)
    risk_assessment: Mapped[str] = mapped_column(Text, nullable=False)
    clinical_concerns: Mapped[list] = mapped_column(JSONB, default=list)
    recommended_next_step: Mapped[str] = mapped_column(Text, nullable=False)
    urgency_level: Mapped[TriageLevel] = mapped_column(
        Enum(TriageLevel, values_callable=_ev, create_type=False), nullable=False
    )
    urgency_rationale: Mapped[str] = mapped_column(Text, nullable=False)
    followup_recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    escalation_notes: Mapped[str | None] = mapped_column(Text)
    care_pathway: Mapped[str] = mapped_column(String(100), nullable=False)

    # AI reasoning chain (for transparency)
    reasoning_chain: Mapped[list] = mapped_column(JSONB, default=list)
    confidence_breakdown: Mapped[dict] = mapped_column(JSONB, default=dict)

    report_pdf_url: Mapped[str | None] = mapped_column(String(500))
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    assessment: Mapped["Assessment"] = relationship("Assessment", back_populates="triage_report")


class RiskScore(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "risk_scores"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # Per-category risk (0.0 - 1.0)
    cardiac_risk: Mapped[float] = mapped_column(Float, default=0.0)
    stroke_risk: Mapped[float] = mapped_column(Float, default=0.0)
    sepsis_risk: Mapped[float] = mapped_column(Float, default=0.0)
    respiratory_risk: Mapped[float] = mapped_column(Float, default=0.0)
    mental_health_risk: Mapped[float] = mapped_column(Float, default=0.0)
    anaphylaxis_risk: Mapped[float] = mapped_column(Float, default=0.0)
    pregnancy_risk: Mapped[float] = mapped_column(Float, default=0.0)
    medication_risk: Mapped[float] = mapped_column(Float, default=0.0)

    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    highest_risk_category: Mapped[str | None] = mapped_column(String(100))

    assessment: Mapped["Assessment"] = relationship("Assessment", back_populates="risk_score")
