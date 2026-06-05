import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.assessment import AssessmentStatus, TriageLevel


class AssessmentCreate(BaseModel):
    patient_id: uuid.UUID
    chief_complaint: str | None = None


class AssessmentOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    patient_id: uuid.UUID
    session_token: str
    status: AssessmentStatus
    triage_level: TriageLevel | None
    urgency_score: float | None
    confidence_score: float | None
    chief_complaint: str | None
    ai_model_used: str | None
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime


class TriageMessageRequest(BaseModel):
    session_token: str
    message: str


class TriageMessageResponse(BaseModel):
    message: str
    node: str
    is_complete: bool
    requires_escalation: bool
    triage_level: TriageLevel | None = None


class TriageReportOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    assessment_id: uuid.UUID
    patient_summary: str
    symptoms_summary: str
    risk_assessment: str
    clinical_concerns: list
    recommended_next_step: str
    what_to_do_now: list = []
    medication_guidance: list = []
    self_care_measures: list = []
    warning_signs: list = []
    urgency_level: TriageLevel
    urgency_rationale: str
    followup_recommendation: str
    escalation_notes: str | None
    care_pathway: str
    reasoning_chain: list
    confidence_breakdown: dict
    report_pdf_url: str | None
    generated_at: datetime


class RiskScoreOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    assessment_id: uuid.UUID
    cardiac_risk: float
    stroke_risk: float
    sepsis_risk: float
    respiratory_risk: float
    mental_health_risk: float
    anaphylaxis_risk: float
    pregnancy_risk: float
    medication_risk: float
    overall_score: float
    highest_risk_category: str | None


class ConversationMessageOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    role: str
    content: str
    node_name: str | None
    created_at: datetime
