"""Add companies, sections and memberships.

Revision ID: 12fcb97b79f4
Revises: 0d86851f7c1f
Create Date: 2026-07-31 09:53:36.288146
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# Revision identifiers, used by Alembic.
revision: str = "12fcb97b79f4"
down_revision: str | None = "0d86851f7c1f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column(
            "name",
            sa.String(length=150),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
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
            name="pk_companies",
        ),
        sa.UniqueConstraint(
            "name",
            name="uq_companies_name",
        ),
    )

    op.create_index(
        "ix_companies_is_archived",
        "companies",
        [
            "is_archived",
        ],
        unique=False,
    )

    op.create_table(
        "company_memberships",
        sa.Column(
            "company_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.String(length=32),
            server_default=sa.text("'employee'"),
            nullable=False,
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
        sa.CheckConstraint(
            "role IN ('manager', 'employee')",
            name=(
                "ck_company_memberships_"
                "company_membership_role"
            ),
        ),
        sa.ForeignKeyConstraint(
            [
                "company_id",
            ],
            [
                "companies.id",
            ],
            name=(
                "fk_company_memberships_"
                "company_id_companies"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            [
                "user_id",
            ],
            [
                "users.id",
            ],
            name=(
                "fk_company_memberships_"
                "user_id_users"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_company_memberships",
        ),
        sa.UniqueConstraint(
            "company_id",
            "user_id",
            name=(
                "uq_company_memberships_"
                "company_id_user_id"
            ),
        ),
    )

    op.create_index(
        "ix_company_memberships_company_id",
        "company_memberships",
        [
            "company_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_company_memberships_role",
        "company_memberships",
        [
            "role",
        ],
        unique=False,
    )

    op.create_index(
        "ix_company_memberships_user_id",
        "company_memberships",
        [
            "user_id",
        ],
        unique=False,
    )

    op.create_table(
        "sections",
        sa.Column(
            "company_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(length=150),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
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
            [
                "company_id",
            ],
            [
                "companies.id",
            ],
            name="fk_sections_company_id_companies",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            [
                "created_by_user_id",
            ],
            [
                "users.id",
            ],
            name=(
                "fk_sections_"
                "created_by_user_id_users"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_sections",
        ),
        sa.UniqueConstraint(
            "company_id",
            "name",
            name="uq_sections_company_id_name",
        ),
    )

    op.create_index(
        "ix_sections_company_id",
        "sections",
        [
            "company_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_sections_created_by_user_id",
        "sections",
        [
            "created_by_user_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_sections_is_archived",
        "sections",
        [
            "is_archived",
        ],
        unique=False,
    )

    op.create_table(
        "section_memberships",
        sa.Column(
            "section_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=False,
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
            [
                "section_id",
            ],
            [
                "sections.id",
            ],
            name=(
                "fk_section_memberships_"
                "section_id_sections"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            [
                "user_id",
            ],
            [
                "users.id",
            ],
            name=(
                "fk_section_memberships_"
                "user_id_users"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_section_memberships",
        ),
        sa.UniqueConstraint(
            "section_id",
            "user_id",
            name=(
                "uq_section_memberships_"
                "section_id_user_id"
            ),
        ),
    )

    op.create_index(
        "ix_section_memberships_section_id",
        "section_memberships",
        [
            "section_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_section_memberships_user_id",
        "section_memberships",
        [
            "user_id",
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table(
        "section_memberships",
    )

    op.drop_table(
        "sections",
    )

    op.drop_table(
        "company_memberships",
    )

    op.drop_table(
        "companies",
    )