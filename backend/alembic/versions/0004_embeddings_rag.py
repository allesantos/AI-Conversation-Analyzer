"""Embeddings + jobs + HNSW index.

Revision ID: 0004_embeddings_rag
Revises: 0003_conversation_analyses
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_embeddings_rag"
down_revision: str | Sequence[str] | None = "0003_conversation_analyses"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "message_embeddings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("message_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="fk_message_embeddings_conversation_id_conversations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_message_embeddings"),
    )
    op.create_index(
        "ix_message_embeddings_conversation_id",
        "message_embeddings",
        ["conversation_id"],
        unique=False,
    )
    op.execute(
        "ALTER TABLE message_embeddings "
        "ALTER COLUMN embedding TYPE vector(1536) "
        "USING embedding::vector(1536)"
    )
    op.execute(
        "CREATE INDEX ix_message_embeddings_hnsw "
        "ON message_embeddings USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "conversation_embedding_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("chunks_embedded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_embedded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding_model", sa.String(length=64), nullable=False, server_default=""),
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
            name="fk_conversation_embedding_jobs_conversation_id_conversations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_conversation_embedding_jobs"),
        sa.UniqueConstraint(
            "conversation_id",
            name="uq_conversation_embedding_jobs_conversation_id",
        ),
    )

    op.create_table(
        "embedding_usage_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("chunks_embedded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_embedded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding_model", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("embedding_provider", sa.String(length=32), nullable=False, server_default=""),
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
            name="fk_embedding_usage_records_conversation_id_conversations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_embedding_usage_records"),
        sa.UniqueConstraint(
            "conversation_id",
            name="uq_embedding_usage_records_conversation_id",
        ),
    )


def downgrade() -> None:
    op.drop_table("embedding_usage_records")
    op.drop_table("conversation_embedding_jobs")
    op.execute("DROP INDEX IF EXISTS ix_message_embeddings_hnsw")
    op.drop_index("ix_message_embeddings_conversation_id", table_name="message_embeddings")
    op.drop_table("message_embeddings")
