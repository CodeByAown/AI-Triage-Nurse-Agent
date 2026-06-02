"""
LangGraph triage state schema.
All agent nodes read from and write to this typed state.
"""
from __future__ import annotations

from typing import Annotated, Any
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class PatientInfo(TypedDict, total=False):
    first_name: str
    last_name: str
    age: int | None
    biological_sex: str | None
    is_pregnant: bool | None
    chronic_conditions: list[str]
    current_medications: list[dict]
    allergies: list[str]
    smoker: bool | None
    alcohol_use: str | None


class SymptomInfo(TypedDict, total=False):
    name: str
    severity: int | None       # 1-10
    duration: str | None
    onset: str | None
    location: str | None
    character: str | None
    aggravating_factors: list[str]
    relieving_factors: list[str]
    is_primary: bool


class RiskFlags(TypedDict, total=False):
    cardiac: bool
    stroke: bool
    sepsis: bool
    respiratory: bool
    mental_health_crisis: bool
    suicidal_ideation: bool
    anaphylaxis: bool
    pregnancy_complication: bool
    medication_reaction: bool
    any_emergency: bool


class TriageState(TypedDict):
    # Conversation history (LangGraph managed)
    messages: Annotated[list[BaseMessage], add_messages]

    # Patient demographics
    patient_info: PatientInfo

    # Collected symptoms
    symptoms: list[SymptomInfo]
    chief_complaint: str

    # Risk assessment
    risk_flags: RiskFlags
    risk_scores: dict[str, float]

    # Triage output
    triage_level: str | None        # L1–L5
    urgency_score: float | None
    confidence_score: float | None

    # Workflow control
    current_node: str
    turn_count: int
    max_turns: int
    is_complete: bool
    requires_escalation: bool
    collection_phase: str           # intake / symptoms / history / final

    # Information collection flags
    has_demographics: bool
    has_symptoms: bool
    has_history: bool
    has_medications: bool

    # Generated report
    triage_report: dict[str, Any] | None

    # Session metadata
    session_token: str
    assessment_id: str
    organization_id: str
