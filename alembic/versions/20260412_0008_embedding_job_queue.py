"""Add DB-backed embedding job queue.

Revision ID: 20260412_0008
Revises: 20260409_0007
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "20260412_0008"
down_revision = "20260409_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("files", sa.Column("last_embedded_at", sa.DateTime(), nullable=True))
    op.add_column("files", sa.Column("embedding_error_code", sa.String(length=100), nullable=True))

    op.create_table(
        "embedding_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("file_id", sa.UUID(), nullable=False),
        sa.Column("token_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("requested_by", sa.String(length=20), nullable=False, server_default="system"),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["token_id"], ["tokens.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_embedding_jobs_file_id", "embedding_jobs", ["file_id"], unique=False)
    op.create_index("ix_embedding_jobs_token_id", "embedding_jobs", ["token_id"], unique=False)
    op.create_index("ix_embedding_jobs_status", "embedding_jobs", ["status"], unique=False)
    op.create_index(
        "ix_embedding_jobs_status_priority_created",
        "embedding_jobs",
        ["status", "priority", "created_at"],
        unique=False,
    )
    op.execute(
        """
        CREATE UNIQUE INDEX ux_embedding_jobs_active_file
        ON embedding_jobs (file_id)
        WHERE status IN ('queued', 'leased', 'running')
        """
    )

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE files
            SET embedding_status = 'queued'
            WHERE embedding_status = 'pending'
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE files
            SET last_embedded_at = COALESCE(last_embedded_at, updated_at)
            WHERE embedding_status = 'completed'
            """
        )
    )

    pending_rows = bind.execute(
        sa.text(
            """
            SELECT id, token_id
            FROM files
            WHERE embedding_status = 'queued'
            """
        )
    ).fetchall()
    if pending_rows:
        jobs = [
            {
                "id": uuid.uuid4(),
                "file_id": row.id,
                "token_id": row.token_id,
                "status": "queued",
                "attempt_count": 0,
                "max_attempts": 3,
                "priority": 100,
                "requested_by": "migration",
            }
            for row in pending_rows
        ]
        embedding_jobs = sa.table(
            "embedding_jobs",
            sa.column("id", sa.UUID()),
            sa.column("file_id", sa.UUID()),
            sa.column("token_id", sa.UUID()),
            sa.column("status", sa.String()),
            sa.column("attempt_count", sa.Integer()),
            sa.column("max_attempts", sa.Integer()),
            sa.column("priority", sa.Integer()),
            sa.column("requested_by", sa.String()),
        )
        op.bulk_insert(embedding_jobs, jobs)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ux_embedding_jobs_active_file")
    op.drop_index("ix_embedding_jobs_status_priority_created", table_name="embedding_jobs")
    op.drop_index("ix_embedding_jobs_status", table_name="embedding_jobs")
    op.drop_index("ix_embedding_jobs_token_id", table_name="embedding_jobs")
    op.drop_index("ix_embedding_jobs_file_id", table_name="embedding_jobs")
    op.drop_table("embedding_jobs")
    op.drop_column("files", "embedding_error_code")
    op.drop_column("files", "last_embedded_at")
    op.execute(
        """
        UPDATE files
        SET embedding_status = CASE
            WHEN embedding_status IN ('queued', 'processing') THEN 'pending'
            ELSE embedding_status
        END
        """
    )
