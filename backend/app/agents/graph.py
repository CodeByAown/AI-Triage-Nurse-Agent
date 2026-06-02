"""
LangGraph triage state machine.
Uses an entry router to skip directly to the active conversational phase,
preventing runaway execution loops and enabling true multi-turn patient interaction.
"""
from __future__ import annotations

from typing import Any
from langgraph.graph import END, StateGraph

from app.agents.nodes import (
    adaptive_question_node,
    escalation_node,
    history_collection_node,
    intake_node,
    report_generation_node,
    risk_assessment_node,
    symptom_collection_node,
)
from app.agents.state import TriageState
from app.core.logging import logger


async def entry_router_node(state: TriageState) -> dict[str, Any]:
    """A safe pass-through entry node that routes to the saved conversational phase."""
    current = state.get("current_node", "intake")
    logger.info("triage_entry_router", current_node=current, turn_count=state.get("turn_count", 0))
    return {}


def route_entry(state: TriageState) -> str:
    """Determine the active node from state parameters."""
    return state.get("current_node", "intake")


def route_after_intake(state: TriageState) -> str:
    if state.get("requires_escalation"):
        logger.info("triage_route_after_intake", next_node="escalation")
        return "escalation"
    # Always yield execution to the frontend to wait for the patient's reply
    logger.info("triage_route_after_intake", next_node="END (waiting for input)")
    return END


def route_after_symptoms(state: TriageState) -> str:
    if state.get("requires_escalation"):
        logger.info("triage_route_after_symptoms", next_node="escalation")
        return "escalation"
    # Always yield execution to wait for the next symptom clarification
    logger.info("triage_route_after_symptoms", next_node="END (waiting for input)")
    return END


def route_after_history(state: TriageState) -> str:
    if state.get("requires_escalation"):
        logger.info("triage_route_after_history", next_node="escalation")
        return "escalation"
    # Yield to wait for the patient's history answer
    logger.info("triage_route_after_history", next_node="END (waiting for input)")
    return END


def route_adaptive(state: TriageState) -> str:
    if state.get("requires_escalation"):
        logger.info("triage_route_adaptive", next_node="escalation")
        return "escalation"
    if state.get("current_node") == "risk_assessment":
        logger.info("triage_route_adaptive", next_node="risk_assessment")
        return "risk_assessment"
    if state.get("is_complete"):
        logger.info("triage_route_adaptive", next_node="END (session complete)")
        return END
    logger.info("triage_route_adaptive", next_node="END (waiting for input)")
    return END


def route_after_risk(state: TriageState) -> str:
    if state.get("requires_escalation"):
        logger.info("triage_route_after_risk", next_node="escalation")
        return "escalation"
    logger.info("triage_route_after_risk", next_node="report_generation")
    return "report_generation"


def build_triage_graph() -> StateGraph:
    graph = StateGraph(TriageState)

    # Add active nodes + entry router node
    graph.add_node("entry_router", entry_router_node)
    graph.add_node("intake", intake_node)
    graph.add_node("symptom_collection", symptom_collection_node)
    graph.add_node("history_collection", history_collection_node)
    graph.add_node("adaptive_question", adaptive_question_node)
    graph.add_node("risk_assessment", risk_assessment_node)
    graph.add_node("report_generation", report_generation_node)
    graph.add_node("escalation", escalation_node)

    # Hardcode entry point to our pass-through router
    graph.set_entry_point("entry_router")

    # Add dynamic entry edges
    graph.add_conditional_edges(
        "entry_router",
        route_entry,
        {
            "intake": "intake",
            "symptom_collection": "symptom_collection",
            "history_collection": "history_collection",
            "adaptive_question": "adaptive_question",
            "risk_assessment": "risk_assessment",
            "report_generation": "report_generation",
            "escalation": "escalation",
        },
    )

    # Add conditional step edges
    graph.add_conditional_edges(
        "intake",
        route_after_intake,
        {"escalation": "escalation", END: END},
    )
    graph.add_conditional_edges(
        "symptom_collection",
        route_after_symptoms,
        {"escalation": "escalation", END: END},
    )
    graph.add_conditional_edges(
        "history_collection",
        route_after_history,
        {"escalation": "escalation", END: END},
    )
    graph.add_conditional_edges(
        "adaptive_question",
        route_adaptive,
        {"risk_assessment": "risk_assessment", "escalation": "escalation", END: END},
    )
    graph.add_conditional_edges(
        "risk_assessment",
        route_after_risk,
        {"report_generation": "report_generation", "escalation": "escalation"},
    )
    graph.add_edge("report_generation", END)
    graph.add_edge("escalation", END)

    return graph


_compiled_graph = None


def get_triage_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_triage_graph().compile()
    return _compiled_graph
