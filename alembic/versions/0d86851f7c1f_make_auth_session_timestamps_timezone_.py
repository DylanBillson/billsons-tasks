"""reconcile authentication sessions schema

Revision ID: 0d86851f7c1f
Revises: 63fe5b90a0e1
Create Date: 2026-07-30

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0d86851f7c1f"
down_revision: str | None = "63fe5b90a0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Bring the legacy sessions table in line with AuthSession."""

    # Preserve any existing session data.
    op.rename_table(
        "sessions",
        "auth_sessions",
    )

    # Remove indexes created for the legacy schema.
    op.drop_index(
        "ix_sessions_session_token_hash",
        table_name="auth_sessions",
    )
    op.drop_index(
        "ix_sessions_user_id",
        table_name="auth_sessions",
    )
    op.drop_index(
        "ix_sessions_expires_at",
        table_name="auth_sessions",
    )
    op.drop_index(
        "ix_sessions_last_seen_at",
        table_name="auth_sessions",
    )
    op.drop_index(
        "ix_sessions_revoked_at",
        table_name="auth_sessions",
    )

    op.alter_column(
        "auth_sessions",
        "session_token_hash",
        new_column_name="token_hash",
        existing_type=sa.String(length=128),
        existing_nullable=False,
    )

    op.alter_column(
        "auth_sessions",
        "token_hash",
        existing_type=sa.String(length=128),
        type_=sa.String(length=64),
        existing_nullable=False,
    )

    op.alter_column(
        "auth_sessions",
        "csrf_token_hash",
        existing_type=sa.String(length=128),
        type_=sa.String(length=64),
        existing_nullable=False,
    )

    op.alter_column(
        "auth_sessions",
        "user_agent",
        existing_type=sa.Text(),
        type_=sa.String(length=512),
        existing_nullable=True,
        postgresql_using="LEFT(user_agent, 512)",
    )

    op.add_column(
        "auth_sessions",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.add_column(
        "auth_sessions",
        sa.Column(
            "is_revoked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # Preserve the meaning of any legacy revoked_at values.
    op.execute(
        """
        UPDATE auth_sessions
        SET is_revoked = TRUE
        WHERE revoked_at IS NOT NULL
        """
    )

    op.create_index(
        "ix_auth_sessions_token_hash",
        "auth_sessions",
        ["token_hash"],
        unique=True,
    )

    op.create_index(
        "ix_auth_sessions_user_id",
        "auth_sessions",
        ["user_id"],
        unique=False,
    )

    op.create_index(
        "ix_auth_sessions_user_expires_at",
        "auth_sessions",
        ["user_id", "expires_at"],
        unique=False,
    )

    op.create_index(
        "ix_auth_sessions_expires_at",
        "auth_sessions",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    """Restore the legacy sessions schema."""

    op.drop_index(
        "ix_auth_sessions_expires_at",
        table_name="auth_sessions",
    )
    op.drop_index(
        "ix_auth_sessions_user_expires_at",
        table_name="auth_sessions",
    )
    op.drop_index(
        "ix_auth_sessions_user_id",
        table_name="auth_sessions",
    )
    op.drop_index(
        "ix_auth_sessions_token_hash",
        table_name="auth_sessions",
    )

    op.drop_column(
        "auth_sessions",
        "is_revoked",
    )

    op.drop_column(
        "auth_sessions",
        "updated_at",
    )

    op.alter_column(
        "auth_sessions",
        "user_agent",
        existing_type=sa.String(length=512),
        type_=sa.Text(),
        existing_nullable=True,
    )

    op.alter_column(
        "auth_sessions",
        "csrf_token_hash",
        existing_type=sa.String(length=64),
        type_=sa.String(length=128),
        existing_nullable=False,
    )

    op.alter_column(
        "auth_sessions",
        "token_hash",
        existing_type=sa.String(length=64),
        type_=sa.String(length=128),
        existing_nullable=False,
    )

    op.alter_column(
        "auth_sessions",
        "token_hash",
        new_column_name="session_token_hash",
        existing_type=sa.String(length=128),
        existing_nullable=False,
    )

    op.rename_table(
        "auth_sessions",
        "sessions",
    )

    op.create_index(
        "ix_sessions_session_token_hash",
        "sessions",
        ["session_token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_sessions_user_id",
        "sessions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_sessions_expires_at",
        "sessions",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_sessions_last_seen_at",
        "sessions",
        ["last_seen_at"],
        unique=False,
    )
    op.create_index(
        "ix_sessions_revoked_at",
        "sessions",
        ["revoked_at"],
        unique=False,
    )