"""
Patient context assembly (V4 Phase 3 — Historical Context Retrieval).

When a patient returns, Maya should already know their conditions, medications,
allergies, prior symptoms, past assessments, open care items, and uploaded
reports — without making them repeat everything. This module pulls that history
from the memory tables and renders it into a compact text block that is injected
into Maya's system prompt.

Token discipline: the block is intentionally bounded (recent + active only) so
the prompt size stays roughly constant as a patient's history grows.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.document import Document, DocumentExtraction
from app.models.memory import (
    AssessmentMemory,
    CareAction,
    CareActionStatus,
    CareThread,
    ClinicalFact,
    FactCategory,
    FactStatus,
    ThreadStatus,
)

# Bounds — keep the injected history compact.
MAX_FACTS_PER_CATEGORY = 12
MAX_RECENT_ASSESSMENTS = 5
MAX_OPEN_ACTIONS = 8
MAX_RECENT_DOCUMENTS = 6


def _fmt_date(dt: datetime | None) -> str:
    return dt.strftime("%b %d, %Y") if dt else "unknown date"


async def assemble_patient_context(db: AsyncSession, patient_id: uuid.UUID) -> dict:
    """Gather a structured snapshot of everything Maya should remember.

    Returns a dict with keys: facts_by_category, recent_assessments, open_threads,
    open_actions, recent_documents. Safe: returns empty structure on any error.
    """
    ctx: dict = {
        "facts_by_category": {},
        "recent_assessments": [],
        "open_threads": [],
        "open_actions": [],
        "recent_documents": [],
    }
    try:
        # Active clinical facts grouped by category.
        facts = (
            await db.execute(
                select(ClinicalFact)
                .where(
                    ClinicalFact.patient_id == patient_id,
                    ClinicalFact.status == FactStatus.ACTIVE.value,
                )
                .order_by(ClinicalFact.updated_at.desc())
            )
        ).scalars().all()
        grouped: dict[str, list[ClinicalFact]] = {}
        for f in facts:
            grouped.setdefault(f.category, [])
            if len(grouped[f.category]) < MAX_FACTS_PER_CATEGORY:
                grouped[f.category].append(f)
        ctx["facts_by_category"] = grouped

        # Recent past assessments (memory narratives).
        ctx["recent_assessments"] = (
            await db.execute(
                select(AssessmentMemory)
                .where(AssessmentMemory.patient_id == patient_id)
                .order_by(AssessmentMemory.created_at.desc())
                .limit(MAX_RECENT_ASSESSMENTS)
            )
        ).scalars().all()

        # Open care threads.
        ctx["open_threads"] = (
            await db.execute(
                select(CareThread)
                .where(
                    CareThread.patient_id == patient_id,
                    CareThread.status != ThreadStatus.RESOLVED.value,
                )
                .order_by(CareThread.last_touched_at.desc().nullslast())
            )
        ).scalars().all()

        # Open care actions (open loops Maya should follow up on).
        ctx["open_actions"] = (
            await db.execute(
                select(CareAction)
                .where(
                    CareAction.patient_id == patient_id,
                    CareAction.status.in_([CareActionStatus.OPEN.value, CareActionStatus.IN_PROGRESS.value]),
                )
                .order_by(CareAction.due_at.asc().nullslast())
                .limit(MAX_OPEN_ACTIONS)
            )
        ).scalars().all()

        # Recent documents + their extraction summaries.
        docs = (
            await db.execute(
                select(Document)
                .where(Document.patient_id == patient_id)
                .order_by(Document.created_at.desc())
                .limit(MAX_RECENT_DOCUMENTS)
            )
        ).scalars().all()
        doc_views = []
        for d in docs:
            ext = (
                await db.execute(select(DocumentExtraction).where(DocumentExtraction.document_id == d.id))
            ).scalar_one_or_none()
            doc_views.append({"document": d, "extraction": ext})
        ctx["recent_documents"] = doc_views

    except Exception as e:  # noqa: BLE001
        logger.error("assemble_patient_context_failed", error=str(e), patient_id=str(patient_id))
    return ctx


def _category_label(cat: str) -> str:
    return {
        FactCategory.CONDITION.value: "Chronic conditions",
        FactCategory.MEDICATION.value: "Medications",
        FactCategory.ALLERGY.value: "Allergies",
        FactCategory.LAB.value: "Lab results",
        FactCategory.VITAL.value: "Vitals",
        FactCategory.SYMPTOM_HISTORY.value: "Past symptoms",
        FactCategory.PROCEDURE.value: "Procedures",
        FactCategory.LIFESTYLE.value: "Lifestyle",
    }.get(cat, cat.replace("_", " ").title())


def _fact_str(f: ClinicalFact) -> str:
    if f.value:
        unit = f" {f.unit}" if f.unit else ""
        return f"{f.label}: {f.value}{unit}"
    return f.label


def format_patient_history_block(ctx: dict) -> str:
    """Render the assembled context into a compact text block for the LLM.
    Returns '' when there is no prior history (e.g. a brand-new patient)."""
    has_any = (
        ctx.get("facts_by_category")
        or ctx.get("recent_assessments")
        or ctx.get("open_actions")
        or ctx.get("open_threads")
        or ctx.get("recent_documents")
    )
    if not has_any:
        return ""

    lines: list[str] = ["KNOWN PATIENT HISTORY (from previous visits — remembered by Maya):"]

    grouped = ctx.get("facts_by_category") or {}
    # Show clinically important categories first.
    order = [
        FactCategory.CONDITION.value, FactCategory.MEDICATION.value, FactCategory.ALLERGY.value,
        FactCategory.LAB.value, FactCategory.VITAL.value, FactCategory.SYMPTOM_HISTORY.value,
    ]
    for cat in order + [c for c in grouped if c not in order]:
        items = grouped.get(cat)
        if items:
            lines.append(f"- {_category_label(cat)}: " + "; ".join(_fact_str(f) for f in items))

    assessments = ctx.get("recent_assessments") or []
    if assessments:
        lines.append("- Recent assessments:")
        for m in assessments:
            lvl = f" [{m.triage_level}]" if m.triage_level else ""
            lines.append(f"    • {_fmt_date(m.created_at)}{lvl}: {(m.chief_complaint or 'assessment').strip()}")

    actions = ctx.get("open_actions") or []
    if actions:
        lines.append("- Open care items to follow up on:")
        for a in actions:
            due = f" (due {_fmt_date(a.due_at)})" if a.due_at else ""
            lines.append(f"    • {a.description.strip()}{due}")

    docs = ctx.get("recent_documents") or []
    if docs:
        lines.append("- Uploaded medical documents (you CAN read these — use their contents to answer the patient):")
        for dv in docs:
            d = dv["document"]
            ext = dv.get("extraction")
            header = f"    • {_fmt_date(d.created_at)} {d.doc_type.replace('_', ' ')}: {d.original_filename}"
            lines.append(header)

            if ext is None or d.status == "extraction_failed":
                lines.append(
                    "        (This document could not be read automatically. If the patient "
                    "asks about it, say you weren't able to read it and ask them to re-upload a "
                    "clearer copy or describe its contents.)"
                )
                continue

            if ext.summary:
                lines.append(f"        Summary: {ext.summary.strip()}")

            findings = ext.structured or []
            if findings:
                rendered = []
                for f in findings[:12]:
                    if not isinstance(f, dict):
                        continue
                    label = f.get("label")
                    if not label:
                        continue
                    val = f.get("value")
                    unit = f.get("unit")
                    piece = str(label)
                    if val is not None:
                        piece += f": {val}{(' ' + unit) if unit else ''}"
                    rendered.append(piece)
                if rendered:
                    lines.append("        Findings: " + "; ".join(rendered))

            # A bounded excerpt of the real extracted text so Maya can quote specifics.
            text = (ext.extracted_text or "").strip()
            if text:
                excerpt = " ".join(text.split())[:700]
                lines.append(f"        Contents: {excerpt}")

            if not ext.summary and not findings and not text:
                lines.append(
                    "        (No readable content was extracted. If asked, tell the patient you "
                    "couldn't read it and ask them to re-upload a clearer copy.)"
                )

    return "\n".join(lines)


async def get_patient_history_block(db: AsyncSession, patient_id: uuid.UUID) -> str:
    """Convenience: assemble + format in one call."""
    ctx = await assemble_patient_context(db, patient_id)
    return format_patient_history_block(ctx)
