"""Interest fields + analysis_evidence.

Revision ID: 0005_interest_engine
Revises: 0004_embeddings_rag
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_interest_engine"
down_revision: str | Sequence[str] | None = "0004_embeddings_rag"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversation_analyses", sa.Column("interest_score", sa.Integer(), nullable=True))
    op.add_column(
        "conversation_analyses", sa.Column("interest_level", sa.String(length=16), nullable=True)
    )
    op.add_column(
        "conversation_analyses", sa.Column("confidence_score", sa.Integer(), nullable=True)
    )
    op.add_column(
        "conversation_analyses",
        sa.Column(
            "positive_signals",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "conversation_analyses",
        sa.Column(
            "neutral_signals",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "conversation_analyses",
        sa.Column(
            "negative_signals",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )

    op.create_table(
        "analysis_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_analysis_id", sa.Uuid(), nullable=False),
        sa.Column("signal_key", sa.String(length=64), nullable=False),
        sa.Column("signal_label", sa.String(length=200), nullable=False),
        sa.Column("polarity", sa.String(length=16), nullable=False),
        sa.Column("message_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("observation", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_analysis_id"],
            ["conversation_analyses.id"],
            name="fk_analysis_evidence_conversation_analysis_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_analysis_evidence"),
    )
    op.create_index(
        "ix_analysis_evidence_conversation_analysis_id",
        "analysis_evidence",
        ["conversation_analysis_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_analysis_evidence_conversation_analysis_id", table_name="analysis_evidence")
    op.drop_table("analysis_evidence")
    op.drop_column("conversation_analyses", "negative_signals")
    op.drop_column("conversation_analyses", "neutral_signals")
    op.drop_column("conversation_analyses", "positive_signals")
    op.drop_column("conversation_analyses", "confidence_score")
    op.drop_column("conversation_analyses", "interest_level")
    op.drop_column("conversation_analyses", "interest_score")
