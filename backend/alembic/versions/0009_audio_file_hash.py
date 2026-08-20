"""Add file_hash to audio_transcriptions for Whisper dedupe.

Revision ID: 0009_audio_file_hash
Revises: 0008_ai_usage
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_audio_file_hash"
down_revision: str | Sequence[str] | None = "0008_ai_usage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "audio_transcriptions",
        sa.Column("file_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_audio_transcriptions_conversation_id_file_hash",
        "audio_transcriptions",
        ["conversation_id", "file_hash"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_audio_transcriptions_conversation_id_file_hash",
        table_name="audio_transcriptions",
    )
    op.drop_column("audio_transcriptions", "file_hash")
