"""Add ai_access_enabled for demo gating.

Revision ID: 0010_demo_ai_access
Revises: 0009_audio_file_hash
Create Date: 2026-08-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_demo_ai_access"
down_revision: str | Sequence[str] | None = "0009_audio_file_hash"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWNER_EMAIL = "alledesenvolvimento@gmail.com"


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "ai_access_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.execute(
        "UPDATE users SET ai_access_enabled = true "
        f"WHERE lower(email) = lower('{OWNER_EMAIL}')"
    )


def downgrade() -> None:
    op.drop_column("users", "ai_access_enabled")
