"""
Risk detection engine: pattern-matches against known emergency symptom combinations.
Uses keyword extraction + LLM-assisted assessment for nuanced detection.
This runs BEFORE the LLM response to catch obvious emergencies immediately.
"""
from __future__ import annotations

import re

# Emergency keyword patterns (lowercase)
CARDIAC_PATTERNS = [
    r"chest pain", r"chest tightness", r"chest pressure", r"chest heaviness",
    r"pain.{0,30}arm", r"pain.{0,30}jaw", r"pain.{0,30}shoulder",
    r"heart attack", r"palpitation", r"irregular heartbeat",
    r"heart racing", r"sweating.{0,30}(pain|chest)", r"shortness of breath.{0,30}(pain|chest)",
]

STROKE_PATTERNS = [
    r"face.{0,20}droop", r"arm.{0,20}weak", r"speech.{0,30}(slur|difficult|problem)",
    r"sudden.{0,30}(headache|severe head)", r"worst.{0,30}headache",
    r"thunderclap headache", r"vision.{0,20}(loss|blur|double|change)",
    r"confused", r"(can't|cannot|trouble).{0,20}speak", r"stroke",
    r"one side.{0,20}(numb|weak|paralyz)", r"(numb|weak).{0,20}one side",
]

SEPSIS_PATTERNS = [
    r"fever.{0,30}(confused|confusion|alter)", r"very high fever",
    r"temperature.{0,10}(10[3-9]|1[1-9][0-9])",
    r"(chills|rigors).{0,30}(sick|unwell|fever)",
    r"rapid.{0,20}(heart|pulse|breathing)", r"sepsis",
]

RESPIRATORY_PATTERNS = [
    r"can't breathe", r"cannot breathe", r"trouble breathing",
    r"shortness of breath", r"short of breath", r"difficulty breathing",
    r"(gasping|wheezing|stridor).{0,30}(bad|severe|worse)",
    r"blue.{0,20}(lips|fingertip|nail)", r"oxygen", r"choking",
    r"throat.{0,20}(clos|swell|tight)",
]

MENTAL_HEALTH_CRISIS_PATTERNS = [
    r"(want|thinking about|planning).{0,30}(kill|suicide|end.{0,10}life)",
    r"(suicid|self.harm|self-harm|overdos)",
    r"don't want to.{0,20}(live|be here|exist)",
    r"(hurt|harm).{0,20}(myself|yourself)",
    r"have a plan.{0,20}(kill|die|hurt)",
]

ANAPHYLAXIS_PATTERNS = [
    r"throat.{0,20}(swell|clos|tight)",
    r"(allergic reaction|anaphylax)",
    r"(tongue|lip|face).{0,20}swell",
    r"hive.{0,20}(breath|swell)",
    r"epipen", r"severe.{0,20}allerg",
]

PREGNANCY_EMERGENCY_PATTERNS = [
    r"pregnant.{0,30}(bleed|pain|cramp)",
    r"(bleed|pain).{0,30}pregnant",
    r"(no|decreased).{0,30}(baby|fetal).{0,30}(move|kick)",
    r"water broke", r"contractions.{0,20}(36|35|34|33|32|31|30)",
    r"premature", r"placenta",
]

SEVERE_BLEEDING_PATTERNS = [
    r"(can't|cannot|uncontrolled).{0,20}stop.{0,20}bleed",
    r"bleed.{0,20}(heavy|profuse|lot|a lot)",
    r"blood.{0,30}(everywhere|spurting|gushing|soaking)",
    r"(cut|wound|injury).{0,30}(deep|serious|bad|bad)",
]


def _is_negated(text: str, match_start: int) -> bool:
    # Extract lookback before the match (up to 100 characters)
    lookback = text[max(0, match_start - 100):match_start].lower()
    
    # Simple negation keywords
    negations = [
        r"\bno\b", r"\bnot\b", r"\bnever\b", r"\bdeny\b", r"\bdenies\b", 
        r"\bdenied\b", r"\bhaven't\b", r"\bhavent\b", r"\bdon't\b", r"\bdont\b",
        r"\bwithout\b", r"\brule out\b", r"\bruled out\b", r"\babsence of\b"
    ]
    
    # Split lookback by major clause boundaries (but keep conjunctions like 'and' / 'or'
    # which might propagate negations)
    clauses = re.split(r"[,.;]|\bbut\b|\bhowever\b", lookback)
    last_clause = clauses[-1]
    
    return any(re.search(neg, last_clause) for neg in negations)


def _matches_any(text: str, patterns: list[str]) -> bool:
    text_lower = text.lower()
    for p in patterns:
        for match in re.finditer(p, text_lower):
            if not _is_negated(text_lower, match.start()):
                return True
    return False


def detect_emergency_flags(text: str) -> dict[str, bool]:
    """
    Fast pattern-match against the conversation text to detect emergency flags.
    Returns a dict of detected risk categories.
    """
    flags: dict[str, bool] = {
        "cardiac": _matches_any(text, CARDIAC_PATTERNS),
        "stroke": _matches_any(text, STROKE_PATTERNS),
        "sepsis": _matches_any(text, SEPSIS_PATTERNS),
        "respiratory": _matches_any(text, RESPIRATORY_PATTERNS),
        "mental_health_crisis": _matches_any(text, MENTAL_HEALTH_CRISIS_PATTERNS),
        "anaphylaxis": _matches_any(text, ANAPHYLAXIS_PATTERNS),
        "pregnancy_complication": _matches_any(text, PREGNANCY_EMERGENCY_PATTERNS),
        "severe_bleeding": _matches_any(text, SEVERE_BLEEDING_PATTERNS),
    }
    flags["any_emergency"] = any(flags.values())
    return flags


def compute_risk_scores(flags: dict[str, bool], symptoms: list[dict]) -> dict[str, float]:
    """
    Convert boolean flags to weighted risk scores (0.0 - 1.0).
    LLM assessment will further refine these in the full assessment.
    """
    scores: dict[str, float] = {
        "cardiac_risk": 0.9 if flags.get("cardiac") else 0.0,
        "stroke_risk": 0.95 if flags.get("stroke") else 0.0,
        "sepsis_risk": 0.85 if flags.get("sepsis") else 0.0,
        "respiratory_risk": 0.90 if flags.get("respiratory") else 0.0,
        "mental_health_risk": 0.95 if flags.get("mental_health_crisis") else 0.0,
        "anaphylaxis_risk": 0.95 if flags.get("anaphylaxis") else 0.0,
        "pregnancy_risk": 0.85 if flags.get("pregnancy_complication") else 0.0,
        "medication_risk": 0.0,
    }

    # Boost scores based on symptom severity if available
    for symptom in symptoms:
        severity = symptom.get("severity", 0) or 0
        if severity >= 8:
            highest_category = max(scores, key=lambda k: scores[k])
            if scores[highest_category] > 0:
                scores[highest_category] = min(1.0, scores[highest_category] + 0.05)

    return scores


def determine_triage_level(
    flags: dict[str, bool],
    risk_scores: dict[str, float],
    llm_assessment: dict | None = None,
) -> tuple[str, float, float]:
    """
    Returns (triage_level, urgency_score, confidence_score).
    """
    # Use LLM assessment if available (since the LLM can understand negation, history, and context)
    if llm_assessment:
        level = llm_assessment.get("triage_level", "L3_MODERATE")
        urgency = llm_assessment.get("urgency_score", 0.5)
        confidence = llm_assessment.get("confidence_score", 0.7)
        return level, urgency, confidence

    # Hard emergency override (only if no LLM assessment is available)
    if flags.get("any_emergency"):
        max_risk = max(risk_scores.values()) if risk_scores else 0.95
        return "L1_EMERGENCY", max_risk, 0.90

    # Fallback: score-based determination
    max_score = max(risk_scores.values()) if risk_scores else 0.0

    if max_score >= 0.85:
        return "L1_EMERGENCY", max_score, 0.85
    elif max_score >= 0.65:
        return "L2_URGENT", max_score, 0.80
    elif max_score >= 0.40:
        return "L3_MODERATE", max_score, 0.75
    elif max_score >= 0.20:
        return "L4_LOW_RISK", max_score, 0.80
    else:
        return "L5_SELF_CARE", max_score, 0.85
