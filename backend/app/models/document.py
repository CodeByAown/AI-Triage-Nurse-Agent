"""
Document & multi-modal observation models (V3/V4 Phase 2/4/5).

``documents`` holds uploaded medical files (labs, imaging, prescriptions,
discharge summaries, records). ``document_extractions`` holds the OCR/LLM result.
``patient_observations`` is the common substrate every modality (text, voice,
image, pdf, lab…) normalizes into before it becomes memory — so spoken input is
treated exactly like typed input (V4 §4).
"""
import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:  # pragma: no cover
    pass


class DocumentType(str, enum.Enum):
    LAB_REPORT = "lab_report"
    IMAGING_REPORT = "imaging_report"
    PRESCRIPTION = "prescription"
    DISCHARGE_SUMMARY = "discharge_summary"
    MEDICAL_RECORD = "medical_record"
    OTHER = "other"


class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    EXTRACTION_FAILED = "extraction_failed"


class ObservationModality(str, enum.Enum):
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    PDF = "pdf"
    LAB = "lab"
    RX = "rx"
    IMAGING = "imaging"
    NOTE = "note"


class Document(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "documents"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="SET NULL"), index=True
    )

    doc_type: Mapped[str] = mapped_column(String(40), default=DocumentType.OTHER.value, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(150))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    storage_backend: Mapped[str] = mapped_column(String(20), default="local", nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)

    status: Mapped[str] = mapped_column(String(30), default=DocumentStatus.UPLOADED.value, nullable=False, index=True)
    error_detail: Mapped[str | None] = mapped_column(Text)


class DocumentExtraction(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "document_extractions"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    extracted_text: Mapped[str | None] = mapped_column(Text)
    structured: Mapped[list] = mapped_column(JSONB, default=list)   # [{label,value,unit,...}]
    summary: Mapped[str | None] = mapped_column(Text)
    model_used: Mapped[str | None] = mapped_column(String(100))


class PatientObservation(Base, UUIDMixin, TimestampMixin):
    """Common substrate for every modality before it becomes memory (V4 §4)."""

    __tablename__ = "patient_observations"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    source_modality: Mapped[str] = mapped_column(String(20), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(40))
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    observation_type: Mapped[str | None] = mapped_column(String(60))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    structured: Mapped[dict] = mapped_column(JSONB, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    confidence: Mapped[float | None] = mapped_column(Float)
