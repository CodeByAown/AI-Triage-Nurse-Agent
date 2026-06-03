"""Patient memory & multi-modal foundation (V3/V4 Phase 1-5)

Revision ID: 002
Revises: 001
Create Date: 2026-06-03

ADDITIVE & REVERSIBLE. This migration only CREATEs new tables and ADDs two
nullable columns. It does not alter or drop anything that already exists, so the
current triage flow is unaffected.

New tables:
  care_threads, care_actions, clinical_facts, assessment_memory,
  patient_insights, timeline_events, documents, document_extractions,
  patient_observations
New columns:
  patients.user_id (nullable FK -> users)
  assessments.thread_id (nullable FK -> care_threads)

ROLLBACK INSTRUCTIONS
  Full rollback:    python -m alembic downgrade 001
  This drops the two added columns and all nine new tables (which are empty in a
  fresh deploy; in an established deploy any rows in these tables are removed).
  No existing table or column is modified, so downgrade restores the exact prior
  schema. To roll back without the CLI, run the SQL in downgrade() bottom-to-top.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _id_col() -> sa.Column:
    return sa.Column(
        "id", postgresql.UUID(as_uuid=True), primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
    )


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    # ── care_threads ──────────────────────────────────────────────────────────
    op.create_table(
        "care_threads",
        _id_col(),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="open"),
        sa.Column("severity", sa.String(50)),
        sa.Column("summary", sa.Text),
        sa.Column("opened_at", sa.DateTime(timezone=True)),
        sa.Column("last_touched_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_care_threads_patient_id", "care_threads", ["patient_id"])

    # ── documents (created before clinical_facts which FKs to it) ─────────────
    op.create_table(
        "documents",
        _id_col(),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE")),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assessments.id", ondelete="SET NULL")),
        sa.Column("doc_type", sa.String(40), nullable=False, server_default="other"),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(150)),
        sa.Column("file_size", sa.BigInteger),
        sa.Column("storage_backend", sa.String(20), nullable=False, server_default="local"),
        sa.Column("storage_path", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="uploaded"),
        sa.Column("error_detail", sa.Text),
        *_timestamps(),
    )
    op.create_index("ix_documents_patient_id", "documents", ["patient_id"])
    op.create_index("ix_documents_status", "documents", ["status"])

    # ── clinical_facts (self-FK + documents + assessments) ────────────────────
    op.create_table(
        "clinical_facts",
        _id_col(),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE")),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("value", sa.Text),
        sa.Column("value_num", sa.Float),
        sa.Column("unit", sa.String(50)),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("source", sa.String(30), nullable=False, server_default="patient_reported"),
        sa.Column("source_confidence", sa.Float),
        sa.Column("source_assessment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assessments.id", ondelete="SET NULL")),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="SET NULL")),
        sa.Column("effective_from", sa.DateTime(timezone=True)),
        sa.Column("effective_to", sa.DateTime(timezone=True)),
        sa.Column("superseded_by_fact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinical_facts.id", ondelete="SET NULL")),
        sa.Column("last_confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("fact_metadata", postgresql.JSONB, server_default="{}"),
        *_timestamps(),
    )
    op.create_index("ix_clinical_facts_patient_id", "clinical_facts", ["patient_id"])
    op.create_index("ix_clinical_facts_category", "clinical_facts", ["category"])
    op.create_index("ix_clinical_facts_status", "clinical_facts", ["status"])

    # ── assessment_memory ─────────────────────────────────────────────────────
    op.create_table(
        "assessment_memory",
        _id_col(),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE")),
        sa.Column("summary", sa.Text),
        sa.Column("chief_complaint", sa.Text),
        sa.Column("key_findings", postgresql.JSONB, server_default="[]"),
        sa.Column("recommendations", postgresql.JSONB, server_default="[]"),
        sa.Column("triage_level", sa.String(30)),
        *_timestamps(),
    )
    op.create_index("ix_assessment_memory_patient_id", "assessment_memory", ["patient_id"])

    # ── patient_insights ──────────────────────────────────────────────────────
    op.create_table(
        "patient_insights",
        _id_col(),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE")),
        sa.Column("insight_type", sa.String(40), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float),
        sa.Column("evidence", postgresql.JSONB, server_default="[]"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        *_timestamps(),
    )
    op.create_index("ix_patient_insights_patient_id", "patient_insights", ["patient_id"])

    # ── timeline_events ───────────────────────────────────────────────────────
    op.create_table(
        "timeline_events",
        _id_col(),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE")),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("severity", sa.String(50)),
        sa.Column("source_type", sa.String(40)),
        sa.Column("source_id", postgresql.UUID(as_uuid=True)),
        sa.Column("event_metadata", postgresql.JSONB, server_default="{}"),
        *_timestamps(),
    )
    op.create_index("ix_timeline_events_patient_id", "timeline_events", ["patient_id"])
    op.create_index("ix_timeline_events_occurred_at", "timeline_events", ["occurred_at"])
    op.create_index("ix_timeline_events_event_type", "timeline_events", ["event_type"])

    # ── care_actions (FKs care_threads + assessments) ─────────────────────────
    op.create_table(
        "care_actions",
        _id_col(),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE")),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("care_threads.id", ondelete="SET NULL")),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assessments.id", ondelete="SET NULL")),
        sa.Column("type", sa.String(30), nullable=False, server_default="recommendation"),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="open"),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("closed_via", sa.String(30)),
        *_timestamps(),
    )
    op.create_index("ix_care_actions_patient_id", "care_actions", ["patient_id"])
    op.create_index("ix_care_actions_status", "care_actions", ["status"])

    # ── document_extractions ──────────────────────────────────────────────────
    op.create_table(
        "document_extractions",
        _id_col(),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("extracted_text", sa.Text),
        sa.Column("structured", postgresql.JSONB, server_default="[]"),
        sa.Column("summary", sa.Text),
        sa.Column("model_used", sa.String(100)),
        *_timestamps(),
    )
    op.create_index("ix_document_extractions_patient_id", "document_extractions", ["patient_id"])

    # ── patient_observations ──────────────────────────────────────────────────
    op.create_table(
        "patient_observations",
        _id_col(),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE")),
        sa.Column("source_modality", sa.String(20), nullable=False),
        sa.Column("source_type", sa.String(40)),
        sa.Column("source_id", postgresql.UUID(as_uuid=True)),
        sa.Column("observation_type", sa.String(60)),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("structured", postgresql.JSONB, server_default="{}"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.Float),
        *_timestamps(),
    )
    op.create_index("ix_patient_observations_patient_id", "patient_observations", ["patient_id"])
    op.create_index("ix_patient_observations_observed_at", "patient_observations", ["observed_at"])

    # ── additive nullable columns on existing tables ──────────────────────────
    op.add_column("patients", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_patients_user_id", "patients", "users", ["user_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_patients_user_id", "patients", ["user_id"])

    op.add_column("assessments", sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_assessments_thread_id", "assessments", "care_threads", ["thread_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_assessments_thread_id", "assessments", ["thread_id"])


def downgrade() -> None:
    # Drop added columns first (reverse of upgrade) …
    op.drop_index("ix_assessments_thread_id", table_name="assessments")
    op.drop_constraint("fk_assessments_thread_id", "assessments", type_="foreignkey")
    op.drop_column("assessments", "thread_id")

    op.drop_index("ix_patients_user_id", table_name="patients")
    op.drop_constraint("fk_patients_user_id", "patients", type_="foreignkey")
    op.drop_column("patients", "user_id")

    # … then the new tables (children before parents).
    op.drop_table("patient_observations")
    op.drop_table("document_extractions")
    op.drop_table("care_actions")
    op.drop_table("timeline_events")
    op.drop_table("patient_insights")
    op.drop_table("assessment_memory")
    op.drop_table("clinical_facts")
    op.drop_table("documents")
    op.drop_table("care_threads")
