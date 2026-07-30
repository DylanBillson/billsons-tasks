"""Initial schema.

Revision ID: 528e3bcd8c69
Revises:
Create Date: 2026-07-22 00:21:21.567928
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# Revision identifiers, used by Alembic.
revision: str = "528e3bcd8c69"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the migration."""
    op.create_table(
        "application_settings",
        sa.Column(
            "key",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "value",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "value_type",
            sa.String(length=32),
            server_default=sa.text("'string'"),
            nullable=False,
        ),
        sa.Column(
            "is_public",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_application_settings"),
        ),
        sa.UniqueConstraint(
            "key",
            name=op.f("uq_application_settings_key"),
        ),
    )

    op.create_table(
        "users",
        sa.Column(
            "username",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "display_name",
            sa.String(length=150),
            nullable=False,
        ),
        sa.Column(
            "password_hash",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "global_role",
            sa.String(length=32),
            server_default=sa.text("'user'"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "is_anonymised",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "anonymised_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_users"),
        ),
        sa.UniqueConstraint(
            "username",
            name=op.f("uq_users_username"),
        ),
    )

    op.create_table(
        "audit_logs",
        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "action",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "entity_type",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "entity_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "summary",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(
                astext_type=sa.Text(),
            ),
            nullable=False,
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
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_audit_logs_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_audit_logs"),
        ),
    )

    op.create_index(
        op.f("ix_audit_logs_action"),
        "audit_logs",
        ["action"],
        unique=False,
    )

    op.create_index(
        op.f("ix_audit_logs_user_id"),
        "audit_logs",
        ["user_id"],
        unique=False,
    )

    op.create_index(
        "ix_audit_logs_created_at",
        "audit_logs",
        ["created_at"],
        unique=False,
    )

    op.create_index(
        "ix_audit_logs_entity",
        "audit_logs",
        [
            "entity_type",
            "entity_id",
        ],
        unique=False,
    )


def downgrade() -> None:
    """Reverse the migration."""
    op.drop_index(
        "ix_audit_logs_entity",
        table_name="audit_logs",
    )

    op.drop_index(
        "ix_audit_logs_created_at",
        table_name="audit_logs",
    )

    op.drop_index(
        op.f("ix_audit_logs_user_id"),
        table_name="audit_logs",
    )

    op.drop_index(
        op.f("ix_audit_logs_action"),
        table_name="audit_logs",
    )

    op.drop_table("audit_logs")
    op.drop_table("users")
    op.drop_table("application_settings")