"""Bootstrap schema and embedding status state machine."""

from __future__ import annotations

from alembic import op

revision = "20260321_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tokens (
            id UUID PRIMARY KEY,
            storage_used_bytes BIGINT,
            storage_limit_bytes BIGINT,
            created_at TIMESTAMP WITHOUT TIME ZONE
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            id UUID PRIMARY KEY,
            token_id UUID NOT NULL REFERENCES tokens(id),
            filename VARCHAR(255) NOT NULL,
            content_type VARCHAR(100) NOT NULL,
            size_bytes BIGINT NOT NULL,
            storage_path VARCHAR(512) NOT NULL,
            embedding_status VARCHAR(20) NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE,
            updated_at TIMESTAMP WITHOUT TIME ZONE
        )
        """
    )

    op.execute(
        """
        ALTER TABLE files
        ADD COLUMN IF NOT EXISTS embedding_status VARCHAR(20)
        """
    )
    op.execute(
        """
        UPDATE files
        SET embedding_status = CASE
            WHEN content_type LIKE 'text/%%'
                OR content_type IN ('application/json', 'application/xml')
            THEN 'pending'
            ELSE 'not_applicable'
        END
        WHERE embedding_status IS NULL
        """
    )
    op.execute(
        """
        ALTER TABLE files
        ALTER COLUMN embedding_status SET NOT NULL
        """
    )
    op.execute(
        """
        ALTER TABLE files
        ALTER COLUMN embedding_status DROP DEFAULT
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS file_embeddings (
            id UUID PRIMARY KEY,
            file_id UUID NOT NULL REFERENCES files(id),
            chunk_index INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            embedding vector(1536) NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE
        )
        """
    )


def downgrade() -> None:
    raise NotImplementedError(
        "Downgrading the bootstrap migration is intentionally disabled to avoid data loss."
    )
