"""Add section lists, tasks, comments and history.

Revision ID: 31bd15e38aea
Revises: 12fcb97b79f4
Create Date: 31bd15e38aea

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# Revision identifiers, used by Alembic.
revision: str = "31bd15e38aea"
down_revision: str | None = "12fcb97b79f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "section_lists",
        sa.Column(
            "section_id",
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
            "sort_position",
            sa.Integer(),
            server_default=sa.text("1000"),
            nullable=False,
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
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "sort_position >= 0",
            name="ck_section_lists_sort_position_non_negative",
        ),
        sa.ForeignKeyConstraint(
            [
                "section_id",
            ],
            [
                "sections.id",
            ],
            name="fk_section_lists_section_id_sections",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_section_lists",
        ),
        sa.UniqueConstraint(
            "section_id",
            "name",
            name="uq_section_lists_section_id_name",
        ),
    )

    op.create_index(
        "ix_section_lists_section_id",
        "section_lists",
        [
            "section_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_section_lists_sort_position",
        "section_lists",
        [
            "sort_position",
        ],
        unique=False,
    )

    op.create_index(
        "ix_section_lists_is_archived",
        "section_lists",
        [
            "is_archived",
        ],
        unique=False,
    )

    op.create_table(
        "tasks",
        sa.Column(
            "section_list_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.String(length=250),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "due_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "completed_by_user_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "sort_position",
            sa.Integer(),
            server_default=sa.text("1000"),
            nullable=False,
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "deleted_by_user_id",
            sa.Integer(),
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
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "sort_position >= 0",
            name="ck_tasks_sort_position_non_negative",
        ),
        sa.CheckConstraint(
            (
                "(completed_at IS NULL "
                "AND completed_by_user_id IS NULL) "
                "OR completed_at IS NOT NULL"
            ),
            name="ck_tasks_completion_fields_consistent",
        ),
        sa.CheckConstraint(
            (
                "(deleted_at IS NULL "
                "AND deleted_by_user_id IS NULL) "
                "OR deleted_at IS NOT NULL"
            ),
            name="ck_tasks_deletion_fields_consistent",
        ),
        sa.ForeignKeyConstraint(
            [
                "section_list_id",
            ],
            [
                "section_lists.id",
            ],
            name="fk_tasks_section_list_id_section_lists",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            [
                "created_by_user_id",
            ],
            [
                "users.id",
            ],
            name="fk_tasks_created_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "completed_by_user_id",
            ],
            [
                "users.id",
            ],
            name="fk_tasks_completed_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            [
                "deleted_by_user_id",
            ],
            [
                "users.id",
            ],
            name="fk_tasks_deleted_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_tasks",
        ),
    )

    op.create_index(
        "ix_tasks_section_list_id",
        "tasks",
        [
            "section_list_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_tasks_created_by_user_id",
        "tasks",
        [
            "created_by_user_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_tasks_due_at",
        "tasks",
        [
            "due_at",
        ],
        unique=False,
    )

    op.create_index(
        "ix_tasks_completed_by_user_id",
        "tasks",
        [
            "completed_by_user_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_tasks_deleted_by_user_id",
        "tasks",
        [
            "deleted_by_user_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_tasks_list_position",
        "tasks",
        [
            "section_list_id",
            "sort_position",
            "id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_tasks_due_at_active",
        "tasks",
        [
            "due_at",
        ],
        unique=False,
        postgresql_where=sa.text(
            "deleted_at IS NULL "
            "AND completed_at IS NULL"
        ),
    )

    op.create_index(
        "ix_tasks_deleted_at",
        "tasks",
        [
            "deleted_at",
        ],
        unique=False,
    )

    op.create_index(
        "ix_tasks_completed_at",
        "tasks",
        [
            "completed_at",
        ],
        unique=False,
    )

    op.create_table(
        "task_assignees",
        sa.Column(
            "task_id",
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
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            [
                "task_id",
            ],
            [
                "tasks.id",
            ],
            name="fk_task_assignees_task_id_tasks",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            [
                "user_id",
            ],
            [
                "users.id",
            ],
            name="fk_task_assignees_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_task_assignees",
        ),
        sa.UniqueConstraint(
            "task_id",
            "user_id",
            name="uq_task_assignees_task_id_user_id",
        ),
    )

    op.create_index(
        "ix_task_assignees_task_id",
        "task_assignees",
        [
            "task_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_task_assignees_user_id",
        "task_assignees",
        [
            "user_id",
        ],
        unique=False,
    )

    op.create_table(
        "task_comments",
        sa.Column(
            "task_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "body",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "deleted_by_user_id",
            sa.Integer(),
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
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(body)) > 0",
            name="ck_task_comments_body_not_empty",
        ),
        sa.CheckConstraint(
            (
                "(deleted_at IS NULL "
                "AND deleted_by_user_id IS NULL) "
                "OR deleted_at IS NOT NULL"
            ),
            name="ck_task_comments_deletion_fields_consistent",
        ),
        sa.ForeignKeyConstraint(
            [
                "task_id",
            ],
            [
                "tasks.id",
            ],
            name="fk_task_comments_task_id_tasks",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            [
                "user_id",
            ],
            [
                "users.id",
            ],
            name="fk_task_comments_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            [
                "deleted_by_user_id",
            ],
            [
                "users.id",
            ],
            name="fk_task_comments_deleted_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_task_comments",
        ),
    )

    op.create_index(
        "ix_task_comments_task_id",
        "task_comments",
        [
            "task_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_task_comments_user_id",
        "task_comments",
        [
            "user_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_task_comments_deleted_at",
        "task_comments",
        [
            "deleted_at",
        ],
        unique=False,
    )

    op.create_index(
        "ix_task_comments_deleted_by_user_id",
        "task_comments",
        [
            "deleted_by_user_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_task_comments_task_created",
        "task_comments",
        [
            "task_id",
            "created_at",
            "id",
        ],
        unique=False,
    )

    op.create_table(
        "task_history_events",
        sa.Column(
            "task_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "event_type",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "summary",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            [
                "task_id",
            ],
            [
                "tasks.id",
            ],
            name="fk_task_history_events_task_id_tasks",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            [
                "user_id",
            ],
            [
                "users.id",
            ],
            name="fk_task_history_events_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_task_history_events",
        ),
    )

    op.create_index(
        "ix_task_history_events_task_id",
        "task_history_events",
        [
            "task_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_task_history_events_user_id",
        "task_history_events",
        [
            "user_id",
        ],
        unique=False,
    )

    op.create_index(
        "ix_task_history_events_event_type",
        "task_history_events",
        [
            "event_type",
        ],
        unique=False,
    )

    op.create_index(
        "ix_task_history_events_task_created",
        "task_history_events",
        [
            "task_id",
            "created_at",
            "id",
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table(
        "task_history_events",
    )

    op.drop_table(
        "task_comments",
    )

    op.drop_table(
        "task_assignees",
    )

    op.drop_table(
        "tasks",
    )

    op.drop_table(
        "section_lists",
    )