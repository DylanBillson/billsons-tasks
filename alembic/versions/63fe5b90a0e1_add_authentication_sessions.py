"""add authentication sessions

Revision ID: 63fe5b90a0e1
Revises: 528e3bcd8c69
Create Date: 2026-07-22 09:40:20.267923

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# Revision identifiers, used by Alembic.
revision: str = "63fe5b90a0e1"
down_revision: str | None = "528e3bcd8c69"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the migration."""
    op.create_table(
        "sessions",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "session_token_hash",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "csrf_token_hash",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "remember_me",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "ip_address",
            sa.String(length=45),
            nullable=True,
        ),
        sa.Column(
            "user_agent",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_sessions_user_id_users",
            ondelete="CASCADE",
        ),
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


def downgrade() -> None:
    """Reverse the migration."""
    op.drop_index(
        "ix_sessions_revoked_at",
        table_name="sessions",
    )

    op.drop_index(
        "ix_sessions_last_seen_at",
        table_name="sessions",
    )

    op.drop_index(
        "ix_sessions_expires_at",
        table_name="sessions",
    )

    op.drop_index(
        "ix_sessions_user_id",
        table_name="sessions",
    )

    op.drop_index(
        "ix_sessions_session_token_hash",
        table_name="sessions",
    )

    op.drop_table(
        "sessions",
    )