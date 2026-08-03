from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.timezone import utc_now
from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.section_list import SectionList
    from app.models.task_assignee import TaskAssignee
    from app.models.task_comment import TaskComment
    from app.models.task_history_event import TaskHistoryEvent
    from app.models.user import User


class Task(
    Base,
    IntegerPrimaryKeyMixin,
    TimestampMixin,
):
    __tablename__ = "tasks"

    __table_args__ = (
        CheckConstraint(
            "sort_position >= 0",
            name="sort_position_non_negative",
        ),
        CheckConstraint(
            (
                "(completed_at IS NULL AND "
                "completed_by_user_id IS NULL) "
                "OR completed_at IS NOT NULL"
            ),
            name="completion_fields_consistent",
        ),
        CheckConstraint(
            (
                "(deleted_at IS NULL AND "
                "deleted_by_user_id IS NULL) "
                "OR deleted_at IS NOT NULL"
            ),
            name="deletion_fields_consistent",
        ),
        Index(
            "ix_tasks_list_position",
            "section_list_id",
            "sort_position",
            "id",
        ),
        Index(
            "ix_tasks_due_at_active",
            "due_at",
            postgresql_where=text(
                "deleted_at IS NULL "
                "AND completed_at IS NULL"
            ),
        ),
        Index(
            "ix_tasks_deleted_at",
            "deleted_at",
        ),
        Index(
            "ix_tasks_completed_at",
            "completed_at",
        ),
    )

    section_list_id: Mapped[int] = mapped_column(
        ForeignKey(
            "section_lists.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    sort_position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1000,
        server_default=text("1000"),
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    deleted_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    section_list: Mapped["SectionList"] = relationship(
        back_populates="tasks",
        lazy="joined",
    )

    created_by: Mapped["User"] = relationship(
        back_populates="created_tasks",
        foreign_keys=[
            created_by_user_id,
        ],
        lazy="joined",
    )

    completed_by: Mapped["User | None"] = relationship(
        back_populates="completed_tasks",
        foreign_keys=[
            completed_by_user_id,
        ],
        lazy="joined",
    )

    deleted_by: Mapped["User | None"] = relationship(
        back_populates="deleted_tasks",
        foreign_keys=[
            deleted_by_user_id,
        ],
        lazy="joined",
    )

    assignees: Mapped[list["TaskAssignee"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="select",
    )

    comments: Mapped[list["TaskComment"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=(
            "TaskComment.created_at.asc(), "
            "TaskComment.id.asc()"
        ),
        lazy="select",
    )

    history_events: Mapped[list["TaskHistoryEvent"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=(
            "TaskHistoryEvent.created_at.desc(), "
            "TaskHistoryEvent.id.desc()"
        ),
        lazy="select",
    )

    @property
    def section_id(self) -> int:
        return self.section_list.section_id

    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def is_overdue(self) -> bool:
        if (
            self.due_at is None
            or self.is_completed
            or self.is_deleted
        ):
            return False

        return self.due_at < utc_now()

    @property
    def state(self) -> str:
        if self.is_deleted:
            return "deleted"

        if self.is_completed:
            return "completed"

        if self.is_overdue:
            return "overdue"

        return "open"

    def __repr__(self) -> str:
        return (
            f"<Task "
            f"id={self.id!r} "
            f"section_list_id={self.section_list_id!r} "
            f"title={self.title!r} "
            f"sort_position={self.sort_position!r} "
            f"state={self.state!r}>"
        )