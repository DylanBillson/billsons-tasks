from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.user import User


class TaskAssignee(
    Base,
    IntegerPrimaryKeyMixin,
    TimestampMixin,
):
    __tablename__ = "task_assignees"

    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "user_id",
            name="uq_task_assignees_task_id_user_id",
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

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    task: Mapped["Task"] = relationship(
        back_populates="assignees",
        lazy="select",
    )

    user: Mapped["User"] = relationship(
        back_populates="task_assignments",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return (
            f"<TaskAssignee "
            f"id={self.id!r} "
            f"task_id={self.task_id!r} "
            f"user_id={self.user_id!r}>"
        )