"""Audio transcriptions table.

Revision ID: 0006_audio_transcriptions
Revises: 0005_interest_engine
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_audio_transcriptions"
down_revision: str | Sequence[str] | None = "0005_interest_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audio_transcriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("transcribed_text", sa.Text(), nullable=True),
        sa.Column(
            "transcription_provider", sa.String(length=32), nullable=False, server_default=""
        ),
        sa.Column("transcription_model", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="fk_audio_transcriptions_conversation_id_conversations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name="fk_audio_transcriptions_message_id_messages",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audio_transcriptions"),
    )
    op.create_index(
        "ix_audio_transcriptions_conversation_id",
        "audio_transcriptions",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_audio_transcriptions_message_id",
        "audio_transcriptions",
        ["message_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_audio_transcriptions_message_id", table_name="audio_transcriptions")
    op.drop_index("ix_audio_transcriptions_conversation_id", table_name="audio_transcriptions")
    op.drop_table("audio_transcriptions")
