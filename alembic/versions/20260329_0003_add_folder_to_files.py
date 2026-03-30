"""Add folder column to files for virtual directory structure."""

from __future__ import annotations

from alembic import op

revision = "20260329_0003"
down_revision = "20260328_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE files ADD COLUMN IF NOT EXISTS folder VARCHAR(1024) NOT NULL DEFAULT '/'"
    )
    op.execute("CREATE INDEX ix_files_folder ON files (token_id, folder)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_files_folder")
    op.execute("ALTER TABLE files DROP COLUMN IF EXISTS folder")
