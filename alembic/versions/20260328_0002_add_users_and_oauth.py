"""Add users table and link tokens to users for Google OAuth."""

from __future__ import annotations

from alembic import op

revision = "20260328_0002"
down_revision = "20260321_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE users (
            id UUID PRIMARY KEY,
            google_id VARCHAR(255) NOT NULL UNIQUE,
            email VARCHAR(255) NOT NULL,
            name VARCHAR(255),
            picture_url VARCHAR(512),
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_users_google_id ON users (google_id)")

    op.execute(
        "ALTER TABLE tokens ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id)"
    )
    op.execute("CREATE INDEX ix_tokens_user_id ON tokens (user_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tokens_user_id")
    op.execute("ALTER TABLE tokens DROP COLUMN IF EXISTS user_id")
    op.execute("DROP INDEX IF EXISTS ix_users_google_id")
    op.execute("DROP TABLE IF EXISTS users")
