from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.task_history_event import TaskHistoryEvent


class TaskHistoryRepository:
    @staticmethod
    def get_by_id(
        db: Session,
        *,
        history_event_id: int,
    ) -> TaskHistoryEvent | None:
        query = (
            select(TaskHistoryEvent)
            .options(
                joinedload(
                    TaskHistoryEvent.task,
                ),
                joinedload(
                    TaskHistoryEvent.user,
                ),
            )
            .where(
                TaskHistoryEvent.id == history_event_id,
            )
        )

        return db.scalar(
            query,
        )

    @staticmethod
    def list_for_task(
        db: Session,
        *,
        task_id: int,
        limit: int = 250,
        offset: int = 0,
    ) -> list[TaskHistoryEvent]:
        query = (
            select(TaskHistoryEvent)
            .options(
                joinedload(
                    TaskHistoryEvent.user,
                ),
            )
            .where(
                TaskHistoryEvent.task_id == task_id,
            )
            .order_by(
                TaskHistoryEvent.created_at.desc(),
                TaskHistoryEvent.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        return list(
            db.scalars(
                query,
            ).all(),
        )

    @staticmethod
    def create(
        db: Session,
        *,
        task_id: int,
        event_type: str,
        summary: str,
        user_id: int | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> TaskHistoryEvent:
        history_event = TaskHistoryEvent(
            task_id=task_id,
            user_id=user_id,
            event_type=event_type,
            summary=summary,
            metadata_json=metadata_json or {},
        )

        db.add(
            history_event,
        )
        db.flush()

        return history_event

    @staticmethod
    def delete_for_task(
        db: Session,
        *,
        task_id: int,
    ) -> int:
        events = list(
            db.scalars(
                select(TaskHistoryEvent).where(
                    TaskHistoryEvent.task_id == task_id,
                ),
            ).all(),
        )

        for event in events:
            db.delete(
                event,
            )

        db.flush()

        return len(
            events,
        )