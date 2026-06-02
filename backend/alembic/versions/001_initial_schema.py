"""Initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable uuid-ossp extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ── organizations ─────────────────────────────────────────────────────
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("plan", sa.String(50), nullable=False, server_default="starter"),
        sa.Column("logo_url", sa.String(500)),
        sa.Column("website", sa.String(255)),
        sa.Column("phone", sa.String(50)),
        sa.Column("address", sa.Text),
        sa.Column("settings", postgresql.JSONB, server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"])

    # ── users ─────────────────────────────────────────────────────────────
    user_role_enum = postgresql.ENUM(
        "super_admin", "admin", "provider", "patient", "viewer",
        name="userrole"
    )
    user_role_enum.create(op.get_bind())

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("role", postgresql.ENUM("super_admin", "admin", "provider", "patient", "viewer", name="userrole", create_type=False), nullable=False, server_default="patient"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("avatar_url", sa.String(500)),
        sa.Column("phone", sa.String(50)),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── providers ─────────────────────────────────────────────────────────
    op.create_table(
        "providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(50)),
        sa.Column("specialty", sa.String(255)),
        sa.Column("npi", sa.String(20), unique=True),
        sa.Column("license_number", sa.String(100)),
        sa.Column("license_state", sa.String(50)),
        sa.Column("department", sa.String(255)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── patients ──────────────────────────────────────────────────────────
    sex_enum = postgresql.ENUM(
        "male", "female", "other", "prefer_not_to_say",
        name="biologicalsex"
    )
    sex_enum.create(op.get_bind())

    op.create_table(
        "patients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("mrn", sa.String(100)),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("date_of_birth", sa.Date),
        sa.Column("biological_sex", postgresql.ENUM("male", "female", "other", "prefer_not_to_say", name="biologicalsex", create_type=False)),
        sa.Column("gender_identity", sa.String(100)),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(50)),
        sa.Column("address", sa.Text),
        sa.Column("allergies", postgresql.JSONB, server_default="[]"),
        sa.Column("chronic_conditions", postgresql.JSONB, server_default="[]"),
        sa.Column("current_medications", postgresql.JSONB, server_default="[]"),
        sa.Column("past_surgeries", postgresql.JSONB, server_default="[]"),
        sa.Column("smoker", sa.Boolean),
        sa.Column("alcohol_use", sa.String(50)),
        sa.Column("exercise_frequency", sa.String(50)),
        sa.Column("is_pregnant", sa.Boolean),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_patients_mrn", "patients", ["mrn"])
    op.create_index("ix_patients_email", "patients", ["email"])

    # ── assessments ───────────────────────────────────────────────────────
    status_enum = postgresql.ENUM(
        "pending", "in_progress", "completed", "escalated", "abandoned",
        name="assessmentstatus"
    )
    status_enum.create(op.get_bind())

    triage_enum = postgresql.ENUM(
        "L1_EMERGENCY", "L2_URGENT", "L3_MODERATE", "L4_LOW_RISK", "L5_SELF_CARE",
        name="triagelevel"
    )
    triage_enum.create(op.get_bind())

    op.create_table(
        "assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_token", sa.String(100), nullable=False, unique=True),
        sa.Column("status", postgresql.ENUM("pending", "in_progress", "completed", "escalated", "abandoned", name="assessmentstatus", create_type=False), nullable=False, server_default="pending"),
        sa.Column("triage_level", postgresql.ENUM("L1_EMERGENCY", "L2_URGENT", "L3_MODERATE", "L4_LOW_RISK", "L5_SELF_CARE", name="triagelevel", create_type=False)),
        sa.Column("urgency_score", sa.Float),
        sa.Column("confidence_score", sa.Float),
        sa.Column("chief_complaint", sa.Text),
        sa.Column("ai_model_used", sa.String(100)),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("graph_state", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_assessments_patient_id", "assessments", ["patient_id"])
    op.create_index("ix_assessments_organization_id", "assessments", ["organization_id"])
    op.create_index("ix_assessments_session_token", "assessments", ["session_token"], unique=True)
    op.create_index("ix_assessments_status", "assessments", ["status"])

    # ── conversations ─────────────────────────────────────────────────────
    role_enum = postgresql.ENUM("system", "user", "assistant", name="messagerole")
    role_enum.create(op.get_bind())

    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", postgresql.ENUM("system", "user", "assistant", name="messagerole", create_type=False), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer),
        sa.Column("node_name", sa.String(100)),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_conversations_assessment_id", "conversations", ["assessment_id"])

    # ── symptoms ──────────────────────────────────────────────────────────
    op.create_table(
        "symptoms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("severity", sa.Integer),
        sa.Column("duration", sa.String(100)),
        sa.Column("onset", sa.String(255)),
        sa.Column("location", sa.String(255)),
        sa.Column("character", sa.String(255)),
        sa.Column("radiation", sa.String(255)),
        sa.Column("aggravating_factors", postgresql.JSONB, server_default="[]"),
        sa.Column("relieving_factors", postgresql.JSONB, server_default="[]"),
        sa.Column("is_primary", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── risk_factors ──────────────────────────────────────────────────────
    op.create_table(
        "risk_factors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("factor_type", sa.String(100), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("is_emergency_flag", sa.Boolean, server_default="false"),
        sa.Column("severity", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── triage_reports ────────────────────────────────────────────────────
    op.create_table(
        "triage_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("patient_summary", sa.Text, nullable=False),
        sa.Column("symptoms_summary", sa.Text, nullable=False),
        sa.Column("risk_assessment", sa.Text, nullable=False),
        sa.Column("clinical_concerns", postgresql.JSONB, server_default="[]"),
        sa.Column("recommended_next_step", sa.Text, nullable=False),
        sa.Column("urgency_level", postgresql.ENUM("L1_EMERGENCY", "L2_URGENT", "L3_MODERATE", "L4_LOW_RISK", "L5_SELF_CARE", name="triagelevel", create_type=False), nullable=False),
        sa.Column("urgency_rationale", sa.Text, nullable=False),
        sa.Column("followup_recommendation", sa.Text, nullable=False),
        sa.Column("escalation_notes", sa.Text),
        sa.Column("care_pathway", sa.String(100), nullable=False),
        sa.Column("reasoning_chain", postgresql.JSONB, server_default="[]"),
        sa.Column("confidence_breakdown", postgresql.JSONB, server_default="{}"),
        sa.Column("report_pdf_url", sa.String(500)),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── risk_scores ───────────────────────────────────────────────────────
    op.create_table(
        "risk_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("cardiac_risk", sa.Float, server_default="0.0"),
        sa.Column("stroke_risk", sa.Float, server_default="0.0"),
        sa.Column("sepsis_risk", sa.Float, server_default="0.0"),
        sa.Column("respiratory_risk", sa.Float, server_default="0.0"),
        sa.Column("mental_health_risk", sa.Float, server_default="0.0"),
        sa.Column("anaphylaxis_risk", sa.Float, server_default="0.0"),
        sa.Column("pregnancy_risk", sa.Float, server_default="0.0"),
        sa.Column("medication_risk", sa.Float, server_default="0.0"),
        sa.Column("overall_score", sa.Float, nullable=False),
        sa.Column("highest_risk_category", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── audit_logs ────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="SET NULL")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(100)),
        sa.Column("ip_address", sa.String(50)),
        sa.Column("user_agent", sa.Text),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("status", sa.String(20), server_default="success"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_audit_logs_organization_id", "audit_logs", ["organization_id"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])

    # ── notifications ─────────────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assessments.id", ondelete="SET NULL")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE")),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("recipient", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(500)),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("is_read", sa.Boolean, server_default="false"),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("audit_logs")
    op.drop_table("risk_scores")
    op.drop_table("triage_reports")
    op.drop_table("risk_factors")
    op.drop_table("symptoms")
    op.drop_table("conversations")
    op.drop_table("assessments")
    op.drop_table("patients")
    op.drop_table("providers")
    op.drop_table("users")
    op.drop_table("organizations")

    op.execute("DROP TYPE IF EXISTS messagerole")
    op.execute("DROP TYPE IF EXISTS triagelevel")
    op.execute("DROP TYPE IF EXISTS assessmentstatus")
    op.execute("DROP TYPE IF EXISTS biologicalsex")
    op.execute("DROP TYPE IF EXISTS userrole")
