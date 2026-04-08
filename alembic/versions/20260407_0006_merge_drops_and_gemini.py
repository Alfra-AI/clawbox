"""Merge drops and gemini migration branches."""

from __future__ import annotations

from alembic import op

revision = "20260407_0006"
down_revision = ("20260329_0005_drops", "20260330_0005")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
