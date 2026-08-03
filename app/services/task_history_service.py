from typing import Any

from sqlalchemy.orm import Session

from app.core.constants import TaskHistoryEventType
from app.models.task import Task
from app.models.task_history_event import TaskHistoryEvent
from app.models.user import User
from app.repositories.task_history_repository import (
    TaskHistoryRepository,
)
from app.services.audit_service import AuditService


class TaskHistoryServiceError(ValueError):
    """Base exception for task-history failures."""


class TaskHistoryEventNotFoundError(TaskHistoryServiceError):
    """Raised when a task-history event cannot be found."""


class TaskHistoryService:
    @staticmethod
    def get_event(
        db: Session,
        *,
        history_event_id: int,
    ) -> TaskHistoryEvent | None:
        return TaskHistoryRepository.get_by_id(
            db,
            history_event_id=history_event_id,
        )

    @staticmethod
    def require_event(
        db: Session,
        *,
        history_event_id: int,
    ) -> TaskHistoryEvent:
        event = TaskHistoryService.get_event(
            db,
            history_event_id=history_event_id,
        )

        if event is None:
            raise TaskHistoryEventNotFoundError(
                "Task history event was not found.",
            )

        return event

    @staticmethod
    def list_for_task(
        db: Session,
        *,
        task: Task,
        limit: int = 250,
        offset: int = 0,
    ) -> list[TaskHistoryEvent]:
        return TaskHistoryRepository.list_for_task(
            db,
            task_id=task.id,
            limit=TaskHistoryService._normalise_limit(
                limit,
            ),
            offset=max(
                offset,
                0,
            ),
        )

    @staticmethod
    def record(
        db: Session,
        *,
        task: Task,
        event_type: str | TaskHistoryEventType,
        summary: str,
        actor: User | None = None,
        user_id: int | None = None,
        metadata_json: dict[str, Any] | None = None,
        commit: bool = False,
    ) -> TaskHistoryEvent:
        resolved_user_id = (
            actor.id
            if actor is not None
            else user_id
        )

        event = TaskHistoryRepository.create(
            db,
            task_id=task.id,
            user_id=resolved_user_id,
            event_type=TaskHistoryService.normalise_event_type(
                event_type,
            ),
            summary=TaskHistoryService.normalise_summary(
                summary,
            ),
            metadata_json=AuditService.sanitise_metadata(
                metadata_json or {},
            ),
        )

        if commit:
            db.commit()
            db.refresh(
                event,
            )

        return event

    @staticmethod
    def record_created(
        db: Session,
        *,
        task: Task,
        actor: User,
        commit: bool = False,
    ) -> TaskHistoryEvent:
        return TaskHistoryService.record(
            db,
            task=task,
            actor=actor,
            event_type=TaskHistoryEventType.CREATED,
            summary=(
                f"{actor.display_name} created this task."
            ),
            metadata_json={
                "section_list_id": task.section_list_id,
                "title": task.title,
                "due_at": task.due_at,
            },
            commit=commit,
        )

    @staticmethod
    def record_updated(
        db: Session,
        *,
        task: Task,
        actor: User,
        changes: dict[str, Any],
        commit: bool = False,
    ) -> TaskHistoryEvent:
        return TaskHistoryService.record(
            db,
            task=task,
            actor=actor,
            event_type=TaskHistoryEventType.UPDATED,
            summary=(
                f"{actor.display_name} updated this task."
            ),
            metadata_json={
                "changes": changes,
            },
            commit=commit,
        )

    @staticmethod
    def normalise_event_type(
        event_type: str | TaskHistoryEventType,
    ) -> str:
        if isinstance(
            event_type,
            TaskHistoryEventType,
        ):
            return event_type.value

        value = event_type.strip()

        if not value:
            raise TaskHistoryServiceError(
                "Task history event type cannot be empty.",
            )

        return value

    @staticmethod
    def normalise_summary(
        summary: str,
    ) -> str:
        value = summary.strip()

        if not value:
            raise TaskHistoryServiceError(
                "Task history summary cannot be empty.",
            )

        return value

    @staticmethod
    def _normalise_limit(
        limit: int,
    ) -> int:
        return max(
            1,
            min(
                limit,
                500,
            ),
        )