"""
Patient memory write-back (V4 Phase 1).

Turns the transient artifacts of a triage session — demographics, symptoms, the
final report — into durable, structured memory: clinical_facts, assessment_memory,
timeline_events, and continuity care_threads / care_actions.

Design rules:
  • Everything here is best-effort and defensive. A failure to write memory must
    NEVER break the triage flow, so callers wrap these in try/except and the
    functions themselves swallow per-item errors.
  • Writes are de-duplicated so repeat assessments don't pile up identical facts.
  • Nothing is hard-deleted; superseding is done via status transitions.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.assessment import Assessment
from app.models.document import PatientObservation
from app.models.memory import (
    AssessmentMemory,
    CareAction,
    CareActionStatus,
    CareActionType,
    CareThread,
    ClinicalFact,
    FactCategory,
    FactSource,
    FactStatus,
    TimelineEvent,
    TimelineEventType,
)
from app.models.patient import Patient


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


async def upsert_clinical_fact(
    db: AsyncSession,
    *,
    patient_id: uuid.UUID,
    organization_id: uuid.UUID | None,
    category: str,
    label: str,
    value: str | None = None,
    value_num: float | None = None,
    unit: str | None = None,
    source: str = FactSource.PATIENT_REPORTED.value,
    source_confidence: float | None = None,
    source_assessment_id: uuid.UUID | None = None,
    source_document_id: uuid.UUID | None = None,
    observed_at: datetime | None = None,
) -> ClinicalFact | None:
    """Insert a clinical fact, or re-confirm an existing active one.

    De-dupe key = (patient, category, normalized label, normalized value). If a
    matching active fact exists we just bump ``last_confirmed_at`` rather than
    creating a duplicate. Returns the fact (new or existing) or None on error.
    """
    if not _norm(label):
        return None
    try:
        existing = (
            await db.execute(
                select(ClinicalFact).where(
                    ClinicalFact.patient_id == patient_id,
                    ClinicalFact.category == category,
                    ClinicalFact.status == FactStatus.ACTIVE.value,
                )
            )
        ).scalars().all()
        for f in existing:
            if _norm(f.label) == _norm(label) and _norm(f.value) == _norm(value):
                f.last_confirmed_at = datetime.now(timezone.utc)
                return f

        fact = ClinicalFact(
            patient_id=patient_id,
            organization_id=organization_id,
            category=category,
            label=label.strip()[:255],
            value=value,
            value_num=value_num,
            unit=unit,
            status=FactStatus.ACTIVE.value,
            source=source,
            source_confidence=source_confidence,
            source_assessment_id=source_assessment_id,
            source_document_id=source_document_id,
            effective_from=observed_at or datetime.now(timezone.utc),
            last_confirmed_at=datetime.now(timezone.utc),
        )
        db.add(fact)
        await db.flush()
        return fact
    except Exception as e:  # noqa: BLE001
        logger.error("clinical_fact_upsert_failed", error=str(e), label=label)
        return None


async def add_timeline_event(
    db: AsyncSession,
    *,
    patient_id: uuid.UUID,
    organization_id: uuid.UUID | None,
    event_type: str,
    title: str,
    description: str | None = None,
    occurred_at: datetime | None = None,
    severity: str | None = None,
    source_type: str | None = None,
    source_id: uuid.UUID | None = None,
    event_metadata: dict | None = None,
) -> TimelineEvent | None:
    try:
        ev = TimelineEvent(
            patient_id=patient_id,
            organization_id=organization_id,
            event_type=event_type,
            title=title[:255],
            description=description,
            occurred_at=occurred_at or datetime.now(timezone.utc),
            severity=severity,
            source_type=source_type,
            source_id=source_id,
            event_metadata=event_metadata or {},
        )
        db.add(ev)
        await db.flush()
        return ev
    except Exception as e:  # noqa: BLE001
        logger.error("timeline_event_failed", error=str(e), title=title)
        return None


async def sync_baseline_facts_from_patient(db: AsyncSession, patient: Patient) -> None:
    """Mirror the patient's intake JSONB (conditions/meds/allergies) into
    clinical_facts so they become first-class, queryable memory. Idempotent."""
    try:
        for cond in (patient.chronic_conditions or []):
            label = cond if isinstance(cond, str) else (cond.get("name") if isinstance(cond, dict) else None)
            if label:
                await upsert_clinical_fact(
                    db, patient_id=patient.id, organization_id=patient.organization_id,
                    category=FactCategory.CONDITION.value, label=str(label),
                    source=FactSource.PATIENT_REPORTED.value,
                )
        for med in (patient.current_medications or []):
            if isinstance(med, dict):
                label = med.get("name") or med.get("drug")
                value = med.get("dose") or med.get("dosage")
            else:
                label, value = str(med), None
            if label:
                await upsert_clinical_fact(
                    db, patient_id=patient.id, organization_id=patient.organization_id,
                    category=FactCategory.MEDICATION.value, label=str(label), value=value,
                    source=FactSource.PATIENT_REPORTED.value,
                )
        for allergy in (patient.allergies or []):
            label = allergy if isinstance(allergy, str) else (allergy.get("name") if isinstance(allergy, dict) else None)
            if label:
                await upsert_clinical_fact(
                    db, patient_id=patient.id, organization_id=patient.organization_id,
                    category=FactCategory.ALLERGY.value, label=str(label),
                    source=FactSource.PATIENT_REPORTED.value,
                )
    except Exception as e:  # noqa: BLE001
        logger.error("baseline_fact_sync_failed", error=str(e), patient_id=str(patient.id))


def _as_list(val) -> list:
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return [val]


async def record_completed_assessment(
    db: AsyncSession,
    *,
    assessment: Assessment,
    report_data: dict,
    state: dict,
) -> None:
    """Write durable memory for a just-completed assessment. Best-effort: any
    failure is logged and swallowed so the triage response is never affected."""
    try:
        patient_id = assessment.patient_id
        org_id = assessment.organization_id
        completed_at = assessment.completed_at or datetime.now(timezone.utc)
        triage_level = assessment.triage_level.value if assessment.triage_level else None
        chief = assessment.chief_complaint or state.get("chief_complaint") or "Triage assessment"

        # Mirror the patient's intake baseline (conditions/meds/allergies) into facts
        # so they're remembered in future visits.
        patient = (
            await db.execute(select(Patient).where(Patient.id == patient_id))
        ).scalar_one_or_none()
        if patient is not None:
            await sync_baseline_facts_from_patient(db, patient)

        # 1) Per-assessment memory (Maya's narrative of this visit) — one per assessment.
        existing_mem = (
            await db.execute(select(AssessmentMemory).where(AssessmentMemory.assessment_id == assessment.id))
        ).scalar_one_or_none()
        if existing_mem is None:
            summary_parts = [
                str(report_data.get("patient_summary") or "").strip(),
                str(report_data.get("symptoms_summary") or "").strip(),
            ]
            mem = AssessmentMemory(
                assessment_id=assessment.id,
                patient_id=patient_id,
                organization_id=org_id,
                summary="\n\n".join(p for p in summary_parts if p) or None,
                chief_complaint=str(chief)[:2000],
                key_findings=_as_list(report_data.get("clinical_concerns")),
                recommendations=[
                    r for r in [
                        str(report_data.get("recommended_next_step") or "").strip(),
                        str(report_data.get("followup_recommendation") or "").strip(),
                    ] if r
                ],
                triage_level=triage_level,
            )
            db.add(mem)
            await db.flush()

        # 2) Timeline event for the assessment itself.
        await add_timeline_event(
            db, patient_id=patient_id, organization_id=org_id,
            event_type=TimelineEventType.ASSESSMENT.value,
            title=str(chief)[:255],
            description=str(report_data.get("risk_assessment") or "").strip() or None,
            occurred_at=completed_at,
            severity=triage_level,
            source_type="assessment",
            source_id=assessment.id,
            event_metadata={"triage_level": triage_level, "requires_escalation": state.get("requires_escalation", False)},
        )

        # 3) Clinical facts from collected symptoms (symptom history).
        for sym in (state.get("symptoms") or []):
            if isinstance(sym, dict):
                name = sym.get("name")
                if name:
                    sev = sym.get("severity")
                    await upsert_clinical_fact(
                        db, patient_id=patient_id, organization_id=org_id,
                        category=FactCategory.SYMPTOM_HISTORY.value,
                        label=str(name),
                        value=f"severity {sev}/10" if sev else (sym.get("duration") or None),
                        source=FactSource.PATIENT_REPORTED.value,
                        source_assessment_id=assessment.id,
                        observed_at=completed_at,
                    )

        # 4) Continuity: open a follow-up care_action if the report recommends one.
        followup = str(report_data.get("followup_recommendation") or "").strip()
        next_step = str(report_data.get("recommended_next_step") or "").strip()
        action_text = followup or next_step
        if action_text:
            # Avoid duplicating an identical still-open action.
            open_actions = (
                await db.execute(
                    select(CareAction).where(
                        CareAction.patient_id == patient_id,
                        CareAction.status == CareActionStatus.OPEN.value,
                    )
                )
            ).scalars().all()
            if not any(_norm(a.description) == _norm(action_text) for a in open_actions):
                # Sooner follow-up for higher acuity.
                days = 2 if triage_level in ("L1_EMERGENCY", "L2_URGENT") else (7 if triage_level == "L3_MODERATE" else 14)
                db.add(CareAction(
                    patient_id=patient_id,
                    organization_id=org_id,
                    assessment_id=assessment.id,
                    type=CareActionType.FOLLOW_UP.value,
                    description=action_text[:2000],
                    status=CareActionStatus.OPEN.value,
                    due_at=completed_at + timedelta(days=days),
                ))
                await db.flush()

        logger.info("assessment_memory_recorded", assessment_id=str(assessment.id), patient_id=str(patient_id))
    except Exception as e:  # noqa: BLE001
        logger.error("record_completed_assessment_failed", error=str(e), assessment_id=str(assessment.id))


_FACT_EXTRACTION_PROMPT = """You extract durable medical facts a patient states about THEMSELVES from a single chat message.

Return ONLY a JSON object with these keys (each an array, empty if nothing applies):
- "conditions": chronic/ongoing diagnoses the patient HAS (e.g. "type 2 diabetes", "hypertension", "asthma"). Strings.
- "medications": drugs the patient currently takes. Objects {"name": str, "dose": str|null}.
- "allergies": substances the patient is allergic to. Strings.

STRICT RULES:
- Only include things the patient affirmatively states about their own health ("I have…", "I take…", "I'm allergic to…", "diagnosed with…").
- Do NOT include transient symptoms (headache, fever, pain) — those are not conditions.
- Do NOT include things they DENY, ask about, or that are hypothetical/negated ("I don't have diabetes" → nothing).
- Do NOT infer. If unsure, leave it out.
- Normalize obvious names (e.g. "sugar/diabetic" → "diabetes"); keep the patient's wording otherwise.

Message: __MESSAGE__

JSON:"""


def _extraction_llm():
    """A small, low-temperature LLM for structured fact extraction. Built lazily
    so importing this module never requires API keys."""
    from app.core.config import settings

    if settings.openai_api_key:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0,
            max_tokens=400,
        )
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        temperature=0,
        max_tokens=400,
    )


def _parse_json_object(raw: str) -> dict:
    raw = (raw or "").strip()
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()
    # Trim to the outermost object if the model added prose.
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        raw = raw[start : end + 1]
    import json as _json

    return _json.loads(raw)


async def capture_history_facts_from_message(
    db: AsyncSession,
    *,
    patient_id: uuid.UUID,
    organization_id: uuid.UUID | None,
    message: str,
    source_assessment_id: uuid.UUID | None = None,
) -> int:
    """Extract self-reported conditions/medications/allergies from a single patient
    message and persist them as clinical_facts so they're remembered immediately —
    even if the assessment never completes.

    Best-effort: returns the number of facts written; logs and swallows all errors.
    Intended for authenticated (persistent) patients only, to bound LLM cost.
    """
    text = (message or "").strip()
    # Cheap gate: skip trivial messages with no chance of clinical history.
    if len(text) < 4:
        return 0
    try:
        llm = _extraction_llm()
        prompt = _FACT_EXTRACTION_PROMPT.replace("__MESSAGE__", text[:2000])
        resp = await llm.ainvoke(prompt)
        data = _parse_json_object(getattr(resp, "content", "") or "")
    except Exception as e:  # noqa: BLE001
        logger.error("fact_extraction_failed", error=str(e), patient_id=str(patient_id))
        return 0

    written = 0
    try:
        for cond in (data.get("conditions") or []):
            label = cond if isinstance(cond, str) else (cond.get("name") if isinstance(cond, dict) else None)
            if label and str(label).strip():
                f = await upsert_clinical_fact(
                    db, patient_id=patient_id, organization_id=organization_id,
                    category=FactCategory.CONDITION.value, label=str(label),
                    source=FactSource.PATIENT_REPORTED.value,
                    source_assessment_id=source_assessment_id,
                )
                written += 1 if f else 0
        for med in (data.get("medications") or []):
            if isinstance(med, dict):
                label, value = med.get("name") or med.get("drug"), med.get("dose") or med.get("dosage")
            else:
                label, value = str(med), None
            if label and str(label).strip():
                f = await upsert_clinical_fact(
                    db, patient_id=patient_id, organization_id=organization_id,
                    category=FactCategory.MEDICATION.value, label=str(label), value=value,
                    source=FactSource.PATIENT_REPORTED.value,
                    source_assessment_id=source_assessment_id,
                )
                written += 1 if f else 0
        for allergy in (data.get("allergies") or []):
            label = allergy if isinstance(allergy, str) else (allergy.get("name") if isinstance(allergy, dict) else None)
            if label and str(label).strip():
                f = await upsert_clinical_fact(
                    db, patient_id=patient_id, organization_id=organization_id,
                    category=FactCategory.ALLERGY.value, label=str(label),
                    source=FactSource.PATIENT_REPORTED.value,
                    source_assessment_id=source_assessment_id,
                )
                written += 1 if f else 0
    except Exception as e:  # noqa: BLE001
        logger.error("fact_capture_persist_failed", error=str(e), patient_id=str(patient_id))

    if written:
        logger.info("history_facts_captured", patient_id=str(patient_id), count=written)
    return written


async def record_observation(
    db: AsyncSession,
    *,
    patient_id: uuid.UUID,
    organization_id: uuid.UUID | None,
    source_modality: str,
    content: str,
    observation_type: str | None = None,
    structured: dict | None = None,
    source_type: str | None = None,
    source_id: uuid.UUID | None = None,
    observed_at: datetime | None = None,
    confidence: float | None = None,
) -> PatientObservation | None:
    """Record a normalized observation from any modality (text/voice/document).
    This is the shared substrate that makes spoken input behave like typed input."""
    try:
        obs = PatientObservation(
            patient_id=patient_id,
            organization_id=organization_id,
            source_modality=source_modality,
            source_type=source_type,
            source_id=source_id,
            observation_type=observation_type,
            content=content,
            structured=structured or {},
            observed_at=observed_at or datetime.now(timezone.utc),
            confidence=confidence,
        )
        db.add(obs)
        await db.flush()
        return obs
    except Exception as e:  # noqa: BLE001
        logger.error("observation_record_failed", error=str(e), modality=source_modality)
        return None
