"""
Manages triage sessions: persistence, state reconstruction, Redis caching.
"""
from __future__ import annotations

import secrets
import json
import uuid
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.agents.graph import get_triage_graph
from app.agents.state import TriageState
from app.core.config import settings
from app.core.logging import logger
from app.models.assessment import (
    Assessment,
    AssessmentStatus,
    Conversation,
    MessageRole,
    RiskScore,
    TriageLevel,
    TriageReport,
)
from app.models.patient import Patient


async def create_session(
    db: AsyncSession,
    patient_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> Assessment:
    """Create a new triage assessment session."""
    session_token = secrets.token_urlsafe(32)

    assessment = Assessment(
        patient_id=patient_id,
        organization_id=organization_id,
        session_token=session_token,
        status=AssessmentStatus.IN_PROGRESS,
        ai_model_used=settings.openai_model if settings.openai_api_key else settings.anthropic_model,
    )
    db.add(assessment)
    await db.flush()
    await db.refresh(assessment)

    logger.info("triage_session_created", session_token=session_token, patient_id=str(patient_id))
    return assessment


async def get_or_rebuild_state(
    db: AsyncSession,
    session_token: str,
) -> tuple[Assessment, TriageState]:
    """Retrieve assessment and rebuild LangGraph state from stored conversations."""
    result = await db.execute(
        select(Assessment).where(Assessment.session_token == session_token)
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise ValueError(f"Session not found: {session_token}")

    # Get patient for initial state
    patient_result = await db.execute(select(Patient).where(Patient.id == assessment.patient_id))
    patient = patient_result.scalar_one_or_none()

    # Reconstruct messages from DB
    conv_result = await db.execute(
        select(Conversation)
        .where(Conversation.assessment_id == assessment.id)
        .order_by(Conversation.created_at)
    )
    conversations = conv_result.scalars().all()

    messages = []
    for conv in conversations:
        if conv.role == MessageRole.USER:
            messages.append(HumanMessage(content=conv.content))
        elif conv.role == MessageRole.ASSISTANT:
            messages.append(AIMessage(content=conv.content))

    # Build state from stored graph_state + messages
    stored_state = assessment.graph_state or {}

    # Cross-conversation memory: assemble the patient's prior history once so Maya
    # remembers them. Best-effort — never blocks a session if memory is empty/errors.
    patient_history = ""
    if patient is not None:
        try:
            from app.services.context_service import get_patient_history_block

            patient_history = await get_patient_history_block(db, patient.id)
        except Exception as e:  # noqa: BLE001
            logger.error("patient_history_assembly_failed", error=str(e), session=session_token)

    state: TriageState = {
        "messages": messages,
        "patient_info": stored_state.get("patient_info", {
            "first_name": patient.first_name if patient else "",
            "last_name": patient.last_name if patient else "",
            "age": patient.age if patient else None,
            "biological_sex": patient.biological_sex.value if patient and patient.biological_sex else None,
            "is_pregnant": patient.is_pregnant,
            "chronic_conditions": patient.chronic_conditions or [],
            "current_medications": patient.current_medications or [],
            "allergies": patient.allergies or [],
        }),
        "symptoms": stored_state.get("symptoms", []),
        "chief_complaint": assessment.chief_complaint or stored_state.get("chief_complaint", ""),
        "risk_flags": stored_state.get("risk_flags", {}),
        "risk_scores": stored_state.get("risk_scores", {}),
        "triage_level": assessment.triage_level.value if assessment.triage_level else None,
        "urgency_score": assessment.urgency_score,
        "confidence_score": assessment.confidence_score,
        "current_node": stored_state.get("current_node", "intake"),
        "turn_count": stored_state.get("turn_count", 0),
        "max_turns": 15,
        "is_complete": assessment.status == AssessmentStatus.COMPLETED,
        "requires_escalation": stored_state.get("requires_escalation", False),
        "collection_phase": stored_state.get("collection_phase", "intake"),
        "has_demographics": stored_state.get("has_demographics", False),
        "has_symptoms": stored_state.get("has_symptoms", False),
        "has_history": stored_state.get("has_history", False),
        "has_medications": stored_state.get("has_medications", False),
        "triage_report": stored_state.get("triage_report"),
        "session_token": session_token,
        "assessment_id": str(assessment.id),
        "organization_id": str(assessment.organization_id),
        "patient_history": patient_history,
    }

    return assessment, state


async def process_message(
    db: AsyncSession,
    session_token: str,
    user_message: str,
) -> dict:
    """
    Main entry point: process a patient message through the triage graph.
    Returns the AI response and updated state info.
    """
    assessment, state = await get_or_rebuild_state(db, session_token)

    if assessment.status == AssessmentStatus.COMPLETED:
        return {
            "message": "This triage session has been completed. Please start a new assessment.",
            "node": "complete",
            "is_complete": True,
            "requires_escalation": False,
            "triage_level": assessment.triage_level.value if assessment.triage_level else None,
        }

    # Add user message to state
    state["messages"] = state["messages"] + [HumanMessage(content=user_message)]

    # Save user message to DB
    user_conv = Conversation(
        assessment_id=assessment.id,
        role=MessageRole.USER,
        content=user_message,
        node_name=state.get("current_node"),
    )
    db.add(user_conv)

    # Run through graph
    graph = get_triage_graph()
    try:
        result = await graph.ainvoke(state)
    except Exception as e:
        logger.error("graph_invocation_failed", error=str(e), session=session_token)
        raise

    # Extract AI response (last AIMessage)
    ai_response = ""
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage):
            ai_response = msg.content
            break

    # Save AI response to DB
    if ai_response:
        ai_conv = Conversation(
            assessment_id=assessment.id,
            role=MessageRole.ASSISTANT,
            content=ai_response,
            node_name=result.get("current_node"),
        )
        db.add(ai_conv)

    # Update assessment with new state
    assessment.graph_state = {
        "patient_info": result.get("patient_info", state.get("patient_info", {})),
        "symptoms": result.get("symptoms", state.get("symptoms", [])),
        "chief_complaint": result.get("chief_complaint", state.get("chief_complaint", "")),
        "risk_flags": result.get("risk_flags", {}),
        "risk_scores": result.get("risk_scores", {}),
        "current_node": result.get("current_node", "intake"),
        "turn_count": result.get("turn_count", 0),
        "collection_phase": result.get("collection_phase", "intake"),
        "has_demographics": result.get("has_demographics", False),
        "has_symptoms": result.get("has_symptoms", False),
        "has_history": result.get("has_history", False),
        "has_medications": result.get("has_medications", False),
        "requires_escalation": result.get("requires_escalation", False),
        "triage_report": result.get("triage_report"),
    }

    if result.get("triage_level"):
        try:
            assessment.triage_level = TriageLevel(result["triage_level"])
        except ValueError:
            pass

    if result.get("urgency_score") is not None:
        assessment.urgency_score = result["urgency_score"]
    if result.get("confidence_score") is not None:
        assessment.confidence_score = result["confidence_score"]

    is_complete = result.get("is_complete", False)
    requires_escalation = result.get("requires_escalation", False)

    if is_complete:
        assessment.status = (
            AssessmentStatus.ESCALATED if requires_escalation else AssessmentStatus.COMPLETED
        )
        assessment.completed_at = datetime.now(timezone.utc)

        # Persist triage report
        report_data = result.get("triage_report")
        if report_data:
            await _persist_report(db, assessment, report_data, result)

        # Write durable cross-conversation memory (facts, timeline, continuity).
        # Best-effort: failures are logged inside and never affect the response.
        try:
            from app.services.memory_service import record_completed_assessment

            await record_completed_assessment(
                db, assessment=assessment, report_data=report_data or {}, state=result
            )
        except Exception as e:  # noqa: BLE001
            logger.error("memory_writeback_failed", error=str(e), session=session_token)

    await db.flush()

    return {
        "message": ai_response,
        "node": result.get("current_node", "intake"),
        "is_complete": is_complete,
        "requires_escalation": requires_escalation,
        "triage_level": result.get("triage_level"),
    }


def _compose_next_step(report_data: dict) -> str:
    """Combine the recommended next step with self-care + warning signs so the
    persisted report carries the same actionable guidance shown in the chat."""
    next_step = str(report_data.get("recommended_next_step", "") or "").strip()
    sections = [next_step] if next_step else []

    self_care = report_data.get("self_care_measures") or []
    if isinstance(self_care, str):
        self_care = [self_care]
    if self_care:
        sections.append(
            "Interim self-care (general, not a prescription):\n"
            + "\n".join(f"- {str(i)}" for i in self_care if str(i).strip())
        )

    warnings = report_data.get("warning_signs") or []
    if isinstance(warnings, str):
        warnings = [warnings]
    if warnings:
        sections.append(
            "Seek emergency care immediately if:\n"
            + "\n".join(f"- {str(i)}" for i in warnings if str(i).strip())
        )

    return "\n\n".join(sections) if sections else "Please consult with a healthcare provider."


async def _persist_report(
    db: AsyncSession,
    assessment: Assessment,
    report_data: dict,
    state: dict,
) -> None:
    """Save triage report and risk scores to the database."""
    try:
        def to_str(val) -> str:
            if val is None:
                return ""
            if isinstance(val, (dict, list)):
                return json.dumps(val, indent=2)
            return str(val)

        def map_triage_level(val) -> str:
            if not val:
                return "L3_MODERATE"
            val_str = str(val).upper().strip()
            mapping = {
                "L1": "L1_EMERGENCY",
                "L2": "L2_URGENT",
                "L3": "L3_MODERATE",
                "L4": "L4_LOW_RISK",
                "L5": "L5_SELF_CARE",
                "EMERGENCY": "L1_EMERGENCY",
                "URGENT": "L2_URGENT",
                "MODERATE": "L3_MODERATE",
                "LOW_RISK": "L4_LOW_RISK",
                "SELF_CARE": "L5_SELF_CARE",
            }
            if val_str in mapping:
                return mapping[val_str]
            for k, v in mapping.items():
                if val_str.startswith(k):
                    return v
            try:
                return TriageLevel(val_str).value
            except ValueError:
                return "L3_MODERATE"

        report = TriageReport(
            assessment_id=assessment.id,
            patient_summary=to_str(report_data.get("patient_summary", "")),
            symptoms_summary=to_str(report_data.get("symptoms_summary", "")),
            risk_assessment=to_str(report_data.get("risk_assessment", "")),
            clinical_concerns=report_data.get("clinical_concerns", []),
            recommended_next_step=_compose_next_step(report_data),
            urgency_level=TriageLevel(
                map_triage_level(report_data.get("urgency_level", assessment.triage_level.value if assessment.triage_level else "L3_MODERATE"))
            ),
            urgency_rationale=to_str(report_data.get("urgency_rationale", "")),
            followup_recommendation=to_str(report_data.get("followup_recommendation", "")),
            escalation_notes=to_str(report_data.get("escalation_notes")) if report_data.get("escalation_notes") else None,
            care_pathway=report_data.get("care_pathway", "primary_care"),
            reasoning_chain=report_data.get("reasoning_chain", []),
            confidence_breakdown={},
        )
        db.add(report)

        # Risk scores
        risk_scores_data = state.get("risk_scores", {})
        overall = max(risk_scores_data.values()) if risk_scores_data else 0.0
        highest_cat = (
            max(risk_scores_data, key=lambda k: risk_scores_data[k])
            if risk_scores_data
            else None
        )

        risk_score = RiskScore(
            assessment_id=assessment.id,
            cardiac_risk=risk_scores_data.get("cardiac_risk", 0.0),
            stroke_risk=risk_scores_data.get("stroke_risk", 0.0),
            sepsis_risk=risk_scores_data.get("sepsis_risk", 0.0),
            respiratory_risk=risk_scores_data.get("respiratory_risk", 0.0),
            mental_health_risk=risk_scores_data.get("mental_health_risk", 0.0),
            anaphylaxis_risk=risk_scores_data.get("anaphylaxis_risk", 0.0),
            pregnancy_risk=risk_scores_data.get("pregnancy_risk", 0.0),
            medication_risk=risk_scores_data.get("medication_risk", 0.0),
            overall_score=overall,
            highest_risk_category=highest_cat,
        )
        db.add(risk_score)

    except Exception as e:
        logger.error("report_persist_failed", error=str(e), assessment_id=str(assessment.id))
