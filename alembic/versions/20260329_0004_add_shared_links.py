"""Add shared_links table for file sharing."""

from __future__ import annotations

from alembic import op

revision = "20260329_0004"
down_revision = "20260329_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE shared_links (
            id UUID PRIMARY KEY,
            file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
            code VARCHAR(10) NOT NULL UNIQUE,
            expires_at TIMESTAMP WITHOUT TIME ZONE,
            max_downloads INTEGER,
            download_count INTEGER DEFAULT 0,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now()
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX ix_shared_links_code ON shared_links (code)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS shared_links")
