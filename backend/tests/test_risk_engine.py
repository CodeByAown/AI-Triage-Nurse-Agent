"""
Unit tests for the risk detection engine.
No LLM calls, no DB, no config required — pure pattern matching.
"""
import sys
import os

# Isolate these tests from the full app config
os.environ.setdefault("SECRET_KEY", "test-secret-key-" + "x" * 50)
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")

import pytest
from app.agents.risk_engine import (
    compute_risk_scores,
    detect_emergency_flags,
    determine_triage_level,
)


class TestEmergencyDetection:
    def test_cardiac_chest_pain(self):
        flags = detect_emergency_flags("I have chest pain radiating to my left arm")
        assert flags["cardiac"] is True
        assert flags["any_emergency"] is True

    def test_stroke_face_droop(self):
        flags = detect_emergency_flags("My face is drooping and I can't speak properly")
        assert flags["stroke"] is True
        assert flags["any_emergency"] is True

    def test_respiratory_distress(self):
        flags = detect_emergency_flags("I can't breathe and my lips are turning blue")
        assert flags["respiratory"] is True
        assert flags["any_emergency"] is True

    def test_mental_health_crisis(self):
        flags = detect_emergency_flags("I'm thinking about killing myself and I have a plan")
        assert flags["mental_health_crisis"] is True
        assert flags["any_emergency"] is True

    def test_anaphylaxis(self):
        flags = detect_emergency_flags("My throat is swelling after eating peanuts, allergic reaction")
        assert flags["anaphylaxis"] is True
        assert flags["any_emergency"] is True

    def test_no_emergency_cold(self):
        flags = detect_emergency_flags("I have a mild cold and runny nose")
        assert flags["any_emergency"] is False
        assert flags["cardiac"] is False
        assert flags["stroke"] is False

    def test_no_emergency_headache(self):
        flags = detect_emergency_flags("I have a mild headache that started this morning")
        assert flags["any_emergency"] is False

    def test_cardiac_heart_attack(self):
        flags = detect_emergency_flags("I think I'm having a heart attack")
        assert flags["cardiac"] is True

    def test_stroke_keywords(self):
        flags = detect_emergency_flags("stroke symptoms sudden headache worst of my life")
        assert flags["stroke"] is True

    def test_pregnancy_bleeding(self):
        flags = detect_emergency_flags("I'm pregnant and having heavy bleeding")
        assert flags["pregnancy_complication"] is True
        assert flags["any_emergency"] is True


class TestTriageLevelDetermination:
    def test_l1_emergency_from_flags(self):
        flags = {"any_emergency": True, "cardiac": True}
        scores = {"cardiac_risk": 0.9}
        level, urgency, confidence = determine_triage_level(flags, scores)
        assert level == "L1_EMERGENCY"
        assert urgency >= 0.85

    def test_l5_self_care_low_scores(self):
        flags = {"any_emergency": False}
        scores = {"cardiac_risk": 0.0, "stroke_risk": 0.0}
        level, urgency, confidence = determine_triage_level(flags, scores)
        assert level == "L5_SELF_CARE"

    def test_l2_urgent_medium_scores(self):
        flags = {"any_emergency": False}
        scores = {"cardiac_risk": 0.7}
        level, urgency, confidence = determine_triage_level(flags, scores)
        assert level == "L2_URGENT"

    def test_l3_moderate(self):
        flags = {"any_emergency": False}
        scores = {"cardiac_risk": 0.45}
        level, urgency, confidence = determine_triage_level(flags, scores)
        assert level == "L3_MODERATE"

    def test_l4_low_risk(self):
        flags = {"any_emergency": False}
        scores = {"cardiac_risk": 0.22}
        level, urgency, confidence = determine_triage_level(flags, scores)
        assert level == "L4_LOW_RISK"


class TestRiskScoreComputation:
    def test_cardiac_score_from_flags(self):
        flags = {"cardiac": True, "any_emergency": True}
        scores = compute_risk_scores(flags, [])
        assert scores["cardiac_risk"] == 0.9

    def test_no_risk_no_flags(self):
        flags = {"any_emergency": False}
        scores = compute_risk_scores(flags, [])
        assert scores["cardiac_risk"] == 0.0
        assert scores["stroke_risk"] == 0.0

    def test_mental_health_risk(self):
        flags = {"mental_health_crisis": True, "any_emergency": True}
        scores = compute_risk_scores(flags, [])
        assert scores["mental_health_risk"] == 0.95

    def test_high_severity_symptom_boosts_score(self):
        flags = {"cardiac": True, "any_emergency": True}
        symptoms = [{"name": "chest pain", "severity": 9}]
        scores = compute_risk_scores(flags, symptoms)
        assert scores["cardiac_risk"] > 0.9
