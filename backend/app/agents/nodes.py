"""
LangGraph node implementations.
Each node is a pure async function: (state) -> dict[str, Any]
"""
from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel

from app.agents.prompts import (
    ADAPTIVE_QUESTION_PROMPT,
    INTAKE_PROMPT,
    REPORT_GENERATION_PROMPT,
    RISK_ASSESSMENT_PROMPT,
    SYMPTOM_COLLECTION_PROMPT,
    TRIAGE_SYSTEM_PROMPT,
)
from app.agents.risk_engine import (
    compute_risk_scores,
    detect_emergency_flags,
    determine_triage_level,
)
from app.agents.state import TriageState
from app.core.config import settings
from app.core.logging import logger


def _build_llm() -> BaseChatModel:
    """Build the LLM instance based on which API key is available."""
    if settings.openai_api_key:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            max_tokens=settings.openai_max_tokens,
            temperature=0.3,
        )
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        max_tokens=settings.anthropic_max_tokens,
        temperature=0.3,
    )


# Shared LLM instance — initialized once at startup
llm = _build_llm()


def _format_patient_context(state: TriageState) -> str:
    """Render the patient's demographics + history into a context block for the LLM.

    This is the mechanism that makes Maya assess on the basis of the patient's
    history. It is injected into the system message on EVERY LLM call.
    """
    info = state.get("patient_info", {}) or {}

    def _fmt(value, unknown: str = "Unknown — ask the patient if relevant") -> str:
        if value is None or value == "" or value == []:
            return unknown
        if isinstance(value, list):
            parts = []
            for item in value:
                if isinstance(item, dict):
                    parts.append(item.get("name") or item.get("drug") or json.dumps(item))
                else:
                    parts.append(str(item))
            return ", ".join(parts) if parts else unknown
        return str(value)

    name = info.get("first_name") or "Unknown"
    age = info.get("age")
    sex = info.get("biological_sex")
    pregnant = info.get("is_pregnant")
    chief = state.get("chief_complaint") or "Not yet established"

    lines = [
        "PATIENT CLINICAL CONTEXT (factor this into every question and your risk assessment):",
        f"- Name: {name}",
        f"- Age: {_fmt(age)}",
        f"- Biological sex: {_fmt(sex)}",
        f"- Pregnancy status: {_fmt(pregnant)}",
        f"- Chronic conditions: {_fmt(info.get('chronic_conditions'))}",
        f"- Current medications: {_fmt(info.get('current_medications'))}",
        f"- Known allergies: {_fmt(info.get('allergies'))}",
        f"- Chief complaint: {chief}",
        "Respect all stated allergies and medications in any guidance. If a high-impact "
        "history item is unknown and relevant to the complaint, ask about it.",
    ]

    # Cross-conversation memory (prior facts, assessments, open care items). Maya
    # should confirm — not re-collect — anything already known here.
    history = (state.get("patient_history") or "").strip()
    if history:
        lines.append("")
        lines.append(history)
        lines.append(
            "Use the history above to provide continuity of care: acknowledge relevant "
            "prior facts, confirm rather than re-ask known information, and follow up on "
            "open items when appropriate. Do not assume unconfirmed details are still current."
        )

    return "\n".join(lines)


def _build_messages(state: TriageState, system_addon: str = "") -> list:
    """Build message list for LLM call: system prompt + patient context + conversation."""
    system_content = TRIAGE_SYSTEM_PROMPT + "\n\n" + _format_patient_context(state)
    if system_addon:
        system_content += f"\n\n{system_addon}"

    messages = [SystemMessage(content=system_content)]
    messages.extend(state["messages"])
    return messages


async def intake_node(state: TriageState) -> dict[str, Any]:
    """
    Collects basic demographics: name, age, sex.
    Runs on turn 0 to greet the patient, and turn 1 to collect demographics.
    """
    turn_count = state.get("turn_count", 0)
    logger.info("triage_node_executing", node="intake", turn_count=turn_count, session=state.get("session_token"))

    # Extract demographic info from latest user message
    latest_human = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None
    )

    # Turn 0: Opening message greeting the patient
    if not latest_human or latest_human.content == "[SESSION_START]":
        welcome = (
            "Hello! I'm Maya, Neural Hub's AI triage nurse. I'm here to help assess "
            "your symptoms and guide you to the right care.\n\n"
            "**Important:** I'm not a doctor, and this assessment doesn't replace professional "
            "medical advice. If you believe you have a medical emergency, please call **911** immediately.\n\n"
            "To get started, could you tell me your first name and age?"
        )
        logger.info("triage_node_transition", current="intake", next="intake (wait for user)", phase="intake")
        return {
            "messages": [AIMessage(content=welcome)],
            "current_node": "intake",
            "collection_phase": "intake",
            "turn_count": 0,
        }

    # Turn 1: Process demographics response
    user_text = latest_human.content
    flags = detect_emergency_flags(user_text)

    if flags["any_emergency"]:
        emergency_msg = (
            "⚠️ **EMERGENCY ALERT** — Based on what you've described, this sounds like "
            "it may require immediate emergency care.\n\n"
            "**Please call 911 or go to your nearest emergency room immediately.**\n"
            "Do not drive yourself. Do not wait.\n\n"
            "I'm also notifying the care team. Are you currently safe?"
        )
        logger.info("triage_node_transition", current="intake", next="escalation", phase="escalation", emergency=True)
        return {
            "messages": [AIMessage(content=emergency_msg)],
            "risk_flags": flags,
            "requires_escalation": True,
            "current_node": "escalation",
            "triage_level": "L1_EMERGENCY",
            "urgency_score": 0.98,
            "confidence_score": 0.90,
        }

    messages = _build_messages(state, INTAKE_PROMPT)
    response = await llm.ainvoke(messages)

    logger.info("triage_node_transition", current="intake", next="symptom_collection (wait for user)", phase="symptom_collection")
    return {
        "messages": [AIMessage(content=response.content)],
        "current_node": "symptom_collection",
        "collection_phase": "symptom_collection",
        "has_demographics": True,
        "turn_count": turn_count + 1,
    }


async def symptom_collection_node(state: TriageState) -> dict[str, Any]:
    """Collects detailed symptom information using OPQRST framework."""
    turn_count = state.get("turn_count", 0)
    logger.info("triage_node_executing", node="symptom_collection", turn_count=turn_count, session=state.get("session_token"))

    latest_human = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None
    )

    # Real-time emergency detection on every user message
    if latest_human:
        flags = detect_emergency_flags(latest_human.content)
        if flags["any_emergency"]:
            emergency_msg = (
                "⚠️ **EMERGENCY ALERT** — What you're describing sounds like a potential "
                "medical emergency.\n\n"
                "**Please call 911 immediately** or have someone take you to the nearest "
                "emergency room. This cannot wait.\n\n"
                "I am flagging your case for immediate escalation."
            )
            logger.info("triage_node_transition", current="symptom_collection", next="escalation", phase="escalation", emergency=True)
            return {
                "messages": [AIMessage(content=emergency_msg)],
                "risk_flags": {**state.get("risk_flags", {}), **flags},
                "requires_escalation": True,
                "triage_level": "L1_EMERGENCY",
                "current_node": "escalation",
                "urgency_score": 0.98,
                "confidence_score": 0.90,
            }

    try:
        messages = _build_messages(state, SYMPTOM_COLLECTION_PROMPT)
        response = await llm.ainvoke(messages)
        content = response.content
    except Exception as e:
        logger.error("symptom_collection_llm_failed", error=str(e), session=state.get("session_token"))
        content = (
            "Thank you for sharing that. So I can assess this properly, could you tell me "
            "when it started and how severe it feels on a scale of 1 to 10?"
        )

    logger.info("triage_node_transition", current="symptom_collection", next="history_collection (wait for user)", phase="history_collection")
    return {
        "messages": [AIMessage(content=content)],
        "current_node": "history_collection",
        "collection_phase": "history_collection",
        "turn_count": turn_count + 1,
        "has_symptoms": True,
    }


async def history_collection_node(state: TriageState) -> dict[str, Any]:
    """Gathers the medical history most relevant to the chief complaint."""
    turn_count = state.get("turn_count", 0)
    logger.info("triage_node_executing", node="history_collection", turn_count=turn_count, session=state.get("session_token"))

    latest_human = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None
    )

    # Real-time emergency detection still applies during history taking
    if latest_human:
        flags = detect_emergency_flags(latest_human.content)
        if flags["any_emergency"]:
            emergency_msg = (
                "⚠️ **EMERGENCY ALERT** — What you're describing sounds like a potential "
                "medical emergency.\n\n"
                "**Please call 911 immediately** or have someone take you to the nearest "
                "emergency room. This cannot wait.\n\n"
                "I am flagging your case for immediate escalation."
            )
            return {
                "messages": [AIMessage(content=emergency_msg)],
                "risk_flags": {**state.get("risk_flags", {}), **flags},
                "requires_escalation": True,
                "triage_level": "L1_EMERGENCY",
                "current_node": "escalation",
                "urgency_score": 0.98,
                "confidence_score": 0.90,
            }

    try:
        messages = _build_messages(state, HISTORY_COLLECTION_PROMPT)
        response = await llm.ainvoke(messages)
        content = response.content
    except Exception as e:
        logger.error("history_collection_llm_failed", error=str(e), session=state.get("session_token"))
        content = (
            "Thanks. Do you have any ongoing medical conditions, take any regular "
            "medications, or have any allergies I should know about?"
        )

    logger.info("triage_node_transition", current="history_collection", next="adaptive_question (wait for user)", phase="adaptive_question")
    return {
        "messages": [AIMessage(content=content)],
        "current_node": "adaptive_question",
        "collection_phase": "adaptive_question",
        "turn_count": turn_count + 1,
        "has_history": True,
    }


async def adaptive_question_node(state: TriageState) -> dict[str, Any]:
    """
    The core adaptive node. Generates the next most clinically relevant question.
    """
    turn_count = state.get("turn_count", 0)
    logger.info("triage_node_executing", node="adaptive_question", turn_count=turn_count, session=state.get("session_token"))

    latest_human = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None
    )

    # Real-time emergency detection
    if latest_human:
        flags = detect_emergency_flags(latest_human.content)
        if flags["any_emergency"]:
            emergency_msg = (
                "⚠️ **EMERGENCY ALERT** — I need to stop our conversation immediately.\n\n"
                "What you've described requires emergency care right now.\n\n"
                "**Please call 911 immediately.** If you cannot call, have someone near you "
                "call for you. Go to your nearest emergency room if you can get there safely.\n\n"
                "Your safety is the priority. Do not delay."
            )
            logger.info("triage_node_transition", current="adaptive_question", next="escalation", phase="escalation", emergency=True)
            return {
                "messages": [AIMessage(content=emergency_msg)],
                "risk_flags": {**state.get("risk_flags", {}), **flags},
                "requires_escalation": True,
                "triage_level": "L1_EMERGENCY",
                "current_node": "escalation",
                "urgency_score": 0.98,
            }

    max_turns = state.get("max_turns", 15)
    symptoms = state.get("symptoms", [])
    has_symptoms = state.get("has_symptoms", False)
    has_history = state.get("has_history", False)

    # Clinically-gated completion: we need a characterized complaint AND a history
    # pass, plus at least a couple of adaptive follow-ups. This prevents both
    # premature completion and runaway loops.
    info_complete = (
        turn_count >= 6
        and has_symptoms
        and has_history
    )

    if turn_count >= max_turns or info_complete:
        completion_msg = (
            "Thank you for sharing all of that information with me. I have everything I need "
            "to complete your triage assessment. Let me analyze your symptoms and compile "
            "your comprehensive triage report...\n\n"
            "_Generating your triage assessment..._"
        )
        logger.info("triage_node_transition", current="adaptive_question", next="risk_assessment", phase="risk_assessment", complete=True)
        return {
            "messages": [AIMessage(content=completion_msg)],
            "current_node": "risk_assessment",
            "is_complete": False,
            "turn_count": turn_count + 1,
        }

    # Generate adaptive question
    prompt_formatted = ADAPTIVE_QUESTION_PROMPT.format(
        chief_complaint=state.get("chief_complaint", "Not yet specified"),
        symptoms_collected=json.dumps([s.get("name", "") for s in symptoms]),
        demographics=json.dumps(state.get("patient_info", {})),
        history_collected=str(has_history),
        turn_count=turn_count,
        max_turns=max_turns,
    )

    try:
        messages = _build_messages(state, prompt_formatted)
        response = await llm.ainvoke(messages)
        content = response.content
    except Exception as e:
        logger.error("adaptive_question_llm_failed", error=str(e), session=state.get("session_token"))
        content = (
            "Thank you. Is there anything else about your symptoms or how you're feeling "
            "right now that you think I should know?"
        )

    logger.info("triage_node_transition", current="adaptive_question", next="adaptive_question (wait for user)", phase="adaptive_question")
    return {
        "messages": [AIMessage(content=content)],
        "current_node": "adaptive_question",
        "turn_count": turn_count + 1,
    }


async def risk_assessment_node(state: TriageState) -> dict[str, Any]:
    """
    Performs comprehensive risk assessment using pattern detection + LLM reasoning.
    """
    logger.info("triage_node", node="risk_assessment", session=state.get("session_token"))

    # Compile only user conversation text for pattern detection
    full_text = " ".join(
        m.content for m in state["messages"]
        if isinstance(m, HumanMessage) and hasattr(m, "content")
    )

    # Pattern-based detection
    flags = detect_emergency_flags(full_text)
    risk_scores = compute_risk_scores(flags, state.get("symptoms", []))

    # LLM-based risk assessment for nuanced scoring
    assessment_messages = _build_messages(state, RISK_ASSESSMENT_PROMPT)
    assessment_messages.append(
        HumanMessage(
            content=(
                "Based on all the information collected in this conversation, "
                "provide a structured risk assessment as JSON with these fields: "
                "triage_level (L1_EMERGENCY/L2_URGENT/L3_MODERATE/L4_LOW_RISK/L5_SELF_CARE), "
                "urgency_score (0.0-1.0), confidence_score (0.0-1.0), "
                "risk_reasoning (string), key_concerns (list of strings), "
                "cardiac_risk (0.0-1.0), stroke_risk (0.0-1.0), "
                "sepsis_risk (0.0-1.0), respiratory_risk (0.0-1.0), "
                "mental_health_risk (0.0-1.0). "
                "Respond ONLY with valid JSON."
            )
        )
    )

    try:
        llm_response = await llm.ainvoke(assessment_messages)
        raw = llm_response.content.strip()
        # Extract JSON if wrapped in markdown
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        llm_assessment = json.loads(raw)
    except Exception as e:
        logger.warning("risk_assessment_parse_failed", error=str(e))
        llm_assessment = None

    # Merge pattern detection with LLM assessment
    for key in ["cardiac_risk", "stroke_risk", "sepsis_risk", "respiratory_risk", "mental_health_risk"]:
        if llm_assessment and key in llm_assessment:
            risk_scores[key] = max(risk_scores.get(key, 0), float(llm_assessment[key]))

    # Override flags with LLM findings
    if llm_assessment:
        for cat in ["cardiac", "stroke", "sepsis", "respiratory", "mental_health_crisis"]:
            score_key = f"{cat.replace('_crisis', '')}_risk"
            if risk_scores.get(score_key, 0) >= 0.75:
                flags[cat] = True
        flags["any_emergency"] = any(
            v for k, v in flags.items() if k != "any_emergency"
        )

    triage_level, urgency_score, confidence_score = determine_triage_level(
        flags, risk_scores, llm_assessment
    )

    return {
        "risk_flags": flags,
        "risk_scores": risk_scores,
        "triage_level": triage_level,
        "urgency_score": urgency_score,
        "confidence_score": confidence_score,
        "requires_escalation": flags.get("any_emergency", False),
        "current_node": "report_generation",
    }


async def report_generation_node(state: TriageState) -> dict[str, Any]:
    """Generates the final structured triage report."""
    logger.info("triage_node", node="report_generation", session=state.get("session_token"))

    report_messages = _build_messages(state, REPORT_GENERATION_PROMPT)
    report_messages.append(
        HumanMessage(
            content=(
                f"Generate the complete triage report for this patient assessment. "
                f"The determined triage level is {state.get('triage_level', 'L3_MODERATE')} "
                f"with urgency score {state.get('urgency_score', 0.5):.2f}. "
                f"Format as JSON with these exact keys: "
                "patient_summary, symptoms_summary, risk_assessment, "
                "clinical_concerns (array), recommended_next_step, "
                "self_care_measures (array of safe interim/OTC measures respecting the "
                "patient's allergies and medications), "
                "warning_signs (array of red-flag symptoms that should prompt immediate care), "
                "urgency_level, urgency_rationale, followup_recommendation, escalation_notes, "
                "care_pathway (one of: emergency_services/emergency_department/urgent_care/"
                "primary_care/telehealth/home_care), "
                "reasoning_chain (array of reasoning steps). "
                "ONLY return valid JSON."
            )
        )
    )

    try:
        report_response = await llm.ainvoke(report_messages)
        raw = report_response.content.strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        report_data = json.loads(raw)
    except Exception as e:
        logger.error("report_generation_failed", error=str(e))
        # Fallback report
        report_data = {
            "patient_summary": "Assessment completed. See conversation for details.",
            "symptoms_summary": "Symptoms were discussed during the triage session.",
            "risk_assessment": "Assessment completed with AI triage assistance.",
            "clinical_concerns": [],
            "recommended_next_step": "Please consult with a healthcare provider.",
            "urgency_level": state.get("triage_level", "L3_MODERATE"),
            "urgency_rationale": "Based on symptoms reported.",
            "followup_recommendation": "Follow up with your primary care provider.",
            "self_care_measures": [],
            "warning_signs": [
                "Symptoms suddenly worsen",
                "New chest pain, difficulty breathing, or confusion",
                "High fever that will not come down",
            ],
            "escalation_notes": None,
            "care_pathway": "primary_care",
            "reasoning_chain": [],
        }

    # Generate patient-facing summary message
    level = state.get("triage_level", "L3_MODERATE")
    level_messages = {
        "L1_EMERGENCY": "🚨 **Emergency — Call 911 Immediately**\nThis assessment indicates a potential medical emergency. Please call 911 or go to your nearest emergency room right now.",
        "L2_URGENT": "⚠️ **Urgent Care Needed — Same Day**\nYour symptoms suggest you should be seen by a healthcare provider today. Please contact your doctor or go to an urgent care center.",
        "L3_MODERATE": "🟡 **Medical Attention Recommended — Within 24-72 Hours**\nYour symptoms warrant professional evaluation within the next 1-3 days. Please schedule an appointment with your provider.",
        "L4_LOW_RISK": "🟢 **Routine Care — Schedule an Appointment**\nYour symptoms appear to be low risk but should still be evaluated. Please schedule a routine appointment.",
        "L5_SELF_CARE": "✅ **Self-Care Appropriate**\nBased on your symptoms, home care may be appropriate. Monitor your symptoms and seek care if they worsen.",
    }

    def _bullets(items) -> str:
        if not items:
            return ""
        if isinstance(items, str):
            items = [items]
        return "\n".join(f"- {str(i)}" for i in items if str(i).strip())

    parts = [level_messages.get(level, "✅ **Assessment Complete**")]

    next_step = str(report_data.get("recommended_next_step", "")).strip()
    if next_step:
        parts.append(f"**What to do next:**\n{next_step}")

    self_care = report_data.get("self_care_measures") or []
    if self_care and level not in ("L1_EMERGENCY",):
        parts.append(
            "**In the meantime (general self-care — not a prescription):**\n"
            + _bullets(self_care)
            + "\n\n_Always check labels, mind your allergies and current medications, "
            "and ask a pharmacist or provider if unsure._"
        )

    warnings = report_data.get("warning_signs") or []
    if warnings:
        parts.append(
            "**⚠️ Seek emergency care immediately if you experience:**\n" + _bullets(warnings)
        )

    followup = str(report_data.get("followup_recommendation", "")).strip()
    if followup and followup.lower() not in next_step.lower():
        parts.append(f"**Follow-up:** {followup}")

    parts.append(
        "Your complete triage report has been generated for the care team. "
        "**Remember: this assessment does not replace evaluation by a licensed healthcare professional.**"
    )

    summary_message = "\n\n".join(p for p in parts if p and p.strip())

    return {
        "messages": [AIMessage(content=summary_message)],
        "triage_report": report_data,
        "is_complete": True,
        "current_node": "complete",
    }


async def escalation_node(state: TriageState) -> dict[str, Any]:
    """Handles emergency escalation — additional guidance and notifications."""
    logger.info("triage_node", node="escalation", session=state.get("session_token"))

    if state.get("is_complete"):
        return {}

    escalation_message = (
        "🚨 **EMERGENCY — PLEASE CALL 911 NOW**\n\n"
        "Based on your symptoms, this is a potential medical emergency that requires "
        "immediate professional care.\n\n"
        "**Actions to take RIGHT NOW:**\n"
        "1. Call **911** (or your local emergency number)\n"
        "2. If you cannot call, ask someone nearby to call for you\n"
        "3. Do not eat, drink, or take any medications unless instructed by emergency services\n"
        "4. Unlock your front door if possible to help emergency responders\n"
        "5. Stay as calm as possible and stay on the line with emergency services\n\n"
        "Your triage report has been flagged as **EMERGENCY** and will be available for "
        "the care team.\n\n"
        "**If your symptoms change or you feel worse, call 911 immediately. "
        "Do not wait for further instructions from this system.**\n\n"
        "*Neural Hub AI Triage — This is not a substitute for emergency medical care.*"
    )

    return {
        "messages": [AIMessage(content=escalation_message)],
        "is_complete": True,
        "current_node": "complete",
        "triage_level": "L1_EMERGENCY",
        "triage_report": {
            "patient_summary": "Emergency triage — escalated to emergency services.",
            "symptoms_summary": "Emergency symptoms detected.",
            "risk_assessment": "HIGH RISK — Emergency presentation detected.",
            "clinical_concerns": ["Emergency symptoms detected — immediate care required"],
            "recommended_next_step": "Call 911 / Go to Emergency Department immediately",
            "urgency_level": "L1_EMERGENCY",
            "urgency_rationale": "Emergency symptoms pattern detected.",
            "followup_recommendation": "Emergency care required immediately.",
            "escalation_notes": "EMERGENCY ESCALATION TRIGGERED — 911 instructed.",
            "care_pathway": "emergency_services",
            "reasoning_chain": ["Emergency keywords detected in patient input"],
        },
    }
