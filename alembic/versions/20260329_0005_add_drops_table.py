"""Add drop_sessions and drop_files tables for ephemeral sharing."""

from __future__ import annotations

from alembic import op

revision = "20260329_0005_drops"
down_revision = "20260329_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS drops")
    op.execute(
        """
        CREATE TABLE drop_sessions (
            id UUID PRIMARY KEY,
            code VARCHAR(4) NOT NULL UNIQUE,
            text_content TEXT,
            expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now()
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX ix_drop_sessions_code ON drop_sessions (code)")
    op.execute("CREATE INDEX ix_drop_sessions_expires_at ON drop_sessions (expires_at)")

    op.execute(
        """
        CREATE TABLE drop_files (
            id UUID PRIMARY KEY,
            session_id UUID NOT NULL REFERENCES drop_sessions(id) ON DELETE CASCADE,
            filename VARCHAR(255) NOT NULL,
            content_type VARCHAR(100) NOT NULL,
            size_bytes BIGINT NOT NULL,
            storage_path VARCHAR(512) NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_drop_files_session_id ON drop_files (session_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS drop_files")
    op.execute("DROP TABLE IF EXISTS drop_sessions")
