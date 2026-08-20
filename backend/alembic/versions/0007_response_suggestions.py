"""Response suggestions table.

Revision ID: 0007_response_suggestions
Revises: 0006_audio_transcriptions
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_response_suggestions"
down_revision: str | Sequence[str] | None = "0006_audio_transcriptions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "response_suggestions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("suggested_text", sa.Text(), nullable=False),
        sa.Column("based_on_message_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="fk_response_suggestions_conversation_id_conversations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["based_on_message_id"],
            ["messages.id"],
            name="fk_response_suggestions_based_on_message_id_messages",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_response_suggestions"),
    )
    op.create_index(
        "ix_response_suggestions_conversation_id",
        "response_suggestions",
        ["conversation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_response_suggestions_conversation_id",
        table_name="response_suggestions",
    )
    op.drop_table("response_suggestions")
