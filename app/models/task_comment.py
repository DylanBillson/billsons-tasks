from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.user import User


class TaskComment(
    Base,
    IntegerPrimaryKeyMixin,
    TimestampMixin,
):
    __tablename__ = "task_comments"

    __table_args__ = (
        CheckConstraint(
            "length(trim(body)) > 0",
            name="body_not_empty",
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
            "ix_task_comments_task_created",
            "task_id",
            "created_at",
            "id",
        ),
    )

    task_id: Mapped[int] = mapped_column(
        ForeignKey(
            "tasks.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    deleted_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    task: Mapped["Task"] = relationship(
        back_populates="comments",
        lazy="select",
    )

    user: Mapped["User | None"] = relationship(
        back_populates="task_comments",
        foreign_keys=[
            user_id,
        ],
        lazy="joined",
    )

    deleted_by: Mapped["User | None"] = relationship(
        back_populates="deleted_task_comments",
        foreign_keys=[
            deleted_by_user_id,
        ],
        lazy="joined",
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def __repr__(self) -> str:
        return (
            f"<TaskComment "
            f"id={self.id!r} "
            f"task_id={self.task_id!r} "
            f"user_id={self.user_id!r} "
            f"is_deleted={self.is_deleted!r}>"
        )