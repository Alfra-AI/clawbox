"""Add drops table for ephemeral file sharing."""

from __future__ import annotations

from alembic import op

revision = "20260329_0005_drops"
down_revision = "20260329_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE drops (
            id UUID PRIMARY KEY,
            code VARCHAR(4) NOT NULL UNIQUE,
            filename VARCHAR(255) NOT NULL,
            content_type VARCHAR(100) NOT NULL,
            size_bytes BIGINT NOT NULL,
            storage_path VARCHAR(512) NOT NULL,
            max_downloads INTEGER DEFAULT 1,
            download_count INTEGER DEFAULT 0,
            expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now()
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX ix_drops_code ON drops (code)")
    op.execute("CREATE INDEX ix_drops_expires_at ON drops (expires_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS drops")
