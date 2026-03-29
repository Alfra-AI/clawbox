"""Add auto_organize setting to tokens."""

from __future__ import annotations

from alembic import op

revision = "20260329_0005"
down_revision = "20260329_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE tokens ADD COLUMN IF NOT EXISTS auto_organize BOOLEAN DEFAULT false"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE tokens DROP COLUMN IF EXISTS auto_organize")
