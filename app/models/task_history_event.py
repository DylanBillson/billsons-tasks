from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.user import User


class TaskHistoryEvent(
    Base,
    IntegerPrimaryKeyMixin,
):
    __tablename__ = "task_history_events"

    __table_args__ = (
        Index(
            "ix_task_history_events_task_created",
            "task_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_task_history_events_event_type",
            "event_type",
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

    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    task: Mapped["Task"] = relationship(
        back_populates="history_events",
        lazy="select",
    )

    user: Mapped["User | None"] = relationship(
        back_populates="task_history_events",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return (
            f"<TaskHistoryEvent "
            f"id={self.id!r} "
            f"task_id={self.task_id!r} "
            f"user_id={self.user_id!r} "
            f"event_type={self.event_type!r}>"
        )