"""Refresh caption-aware embeddings while keeping 768-dimension vectors.

Existing embeddings are dropped and must be re-generated via the
POST /files/embed endpoint after migration.
"""

from __future__ import annotations

from alembic import op

revision = "20260409_0007"
down_revision = "20260407_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop existing embeddings (incompatible dimensions)
    op.execute("DELETE FROM file_embeddings")

    # Keep the vector column at 768 dimensions
    op.execute(
        "ALTER TABLE file_embeddings "
        "ALTER COLUMN embedding TYPE vector(768)"
    )

    # Mark all previously-completed files as pending so they get re-embedded
    op.execute(
        "UPDATE files SET embedding_status = 'pending' "
        "WHERE embedding_status = 'completed'"
    )


def downgrade() -> None:
    # Drop existing embeddings (incompatible dimensions)
    op.execute("DELETE FROM file_embeddings")

    # Keep the vector column at 768 dimensions on downgrade as well
    op.execute(
        "ALTER TABLE file_embeddings "
        "ALTER COLUMN embedding TYPE vector(768)"
    )
