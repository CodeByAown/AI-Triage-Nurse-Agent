"""Richer patient-facing triage report guidance

Revision ID: 003
Revises: 002
Create Date: 2026-06-05

ADDITIVE & REVERSIBLE. This migration only ADDs four nullable JSONB columns to
the existing ``triage_reports`` table to store more detailed, patient-facing
guidance. It does not alter or drop anything that already exists, so existing
reports and the current triage flow are unaffected. New columns default to an
empty JSON array; older rows simply have no values (rendered as empty sections).

New columns on triage_reports:
  what_to_do_now      (JSONB, ordered action steps)
  medication_guidance (JSONB, list of {name, purpose, how_to_take, cautions})
  self_care_measures  (JSONB, detailed interim self-care sentences)
  warning_signs       (JSONB, specific red-flag symptoms)

ROLLBACK INSTRUCTIONS
  Full rollback:    python -m alembic downgrade 002
  This drops the four added columns. No existing column is modified, so downgrade
  restores the exact prior schema.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = (
    "what_to_do_now",
    "medication_guidance",
    "self_care_measures",
    "warning_signs",
)


def upgrade() -> None:
    for name in _COLUMNS:
        op.add_column(
            "triage_reports",
            sa.Column(
                name,
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
                server_default=sa.text("'[]'::jsonb"),
            ),
        )


def downgrade() -> None:
    for name in reversed(_COLUMNS):
        op.drop_column("triage_reports", name)
