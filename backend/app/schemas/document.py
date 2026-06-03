import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentExtractionOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    document_id: uuid.UUID
    extracted_text: str | None
    structured: list
    summary: str | None
    model_used: str | None
    created_at: datetime


class DocumentOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    patient_id: uuid.UUID
    assessment_id: uuid.UUID | None
    doc_type: str
    original_filename: str
    content_type: str | None
    file_size: int | None
    status: str
    error_detail: str | None
    created_at: datetime


class DocumentDetailOut(DocumentOut):
    extraction: DocumentExtractionOut | None = None


class TimelineEventOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    patient_id: uuid.UUID
    event_type: str
    title: str
    description: str | None
    occurred_at: datetime
    severity: str | None
    source_type: str | None
    source_id: uuid.UUID | None


class ClinicalFactOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    category: str
    label: str
    value: str | None
    unit: str | None
    status: str
    source: str
    updated_at: datetime


class CareActionOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    type: str
    description: str
    status: str
    due_at: datetime | None


class PatientMemoryOut(BaseModel):
    facts: list[ClinicalFactOut]
    open_actions: list[CareActionOut]
    history_block: str
