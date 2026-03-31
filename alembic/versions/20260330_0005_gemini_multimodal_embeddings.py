"""Switch embedding dimensions from 1536 (OpenAI) to 768 (Gemini).

Existing embeddings are dropped and must be re-generated via the
POST /files/embed endpoint after migration.
"""

from __future__ import annotations

from alembic import op

revision = "20260330_0005"
down_revision = "20260329_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop existing embeddings (incompatible dimensions)
    op.execute("DELETE FROM file_embeddings")

    # Change vector column from 1536 to 768 dimensions
    op.execute(
        "ALTER TABLE file_embeddings "
        "ALTER COLUMN embedding TYPE vector(768)"
    )

    # Mark all previously-completed files as pending so they get re-embedded
    op.execute(
        "UPDATE files SET embedding_status = 'pending' "
        "WHERE embedding_status = 'completed'"
    )

    # Mark multimodal files (image/video/audio) that were previously not_applicable as pending
    op.execute(
        """
        UPDATE files SET embedding_status = 'pending'
        WHERE embedding_status = 'not_applicable'
          AND (content_type LIKE 'image/%%'
               OR content_type LIKE 'video/%%'
               OR content_type LIKE 'audio/%%')
        """
    )


def downgrade() -> None:
    # Drop existing embeddings (incompatible dimensions)
    op.execute("DELETE FROM file_embeddings")

    # Revert vector column back to 1536 dimensions
    op.execute(
        "ALTER TABLE file_embeddings "
        "ALTER COLUMN embedding TYPE vector(1536)"
    )

    # Mark multimodal files back as not_applicable
    op.execute(
        """
        UPDATE files SET embedding_status = 'not_applicable'
        WHERE content_type LIKE 'image/%%'
           OR content_type LIKE 'video/%%'
           OR content_type LIKE 'audio/%%'
        """
    )
