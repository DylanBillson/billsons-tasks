from typing import Any

from sqlalchemy.orm import Session

from app.core.constants import (
    AuditAction,
    TaskHistoryEventType,
)
from app.models.section import Section
from app.models.section_list import SectionList
from app.models.task import Task
from app.models.user import User
from app.repositories.section_list_repository import (
    SectionListRepository,
)
from app.repositories.task_repository import TaskRepository
from app.schemas.task import (
    TaskCreateRequest,
    TaskFilterOptions,
    TaskMoveRequest,
    TaskReorderRequest,
    TaskUpdateRequest,
)
from app.services.audit_service import AuditService
from app.services.section_list_service import (
    SectionListNotFoundError,
    SectionListService,
)
from app.services.section_service import SectionService
from app.services.task_history_service import (
    TaskHistoryService,
)
from app.services.task_permission_service import (
    TaskPermissionService,
)


class TaskServiceError(ValueError):
    """Base exception for task-service failures."""


class TaskNotFoundError(TaskServiceError):
    """Raised when a task cannot be found."""


class TaskDestinationListNotFoundError(TaskServiceError):
    """Raised when a destination list cannot be found."""


class TaskReorderError(TaskServiceError):
    """Raised when a task reorder request is invalid."""


class TaskAlreadyCompletedError(TaskServiceError):
    """Raised when an already completed task is completed again."""


class TaskNotCompletedError(TaskServiceError):
    """Raised when an open task is reopened."""


class TaskAlreadyDeletedError(TaskServiceError):
    """Raised when an already deleted task is deleted again."""


class TaskNotDeletedError(TaskServiceError):
    """Raised when a non-deleted task is restored."""


class TaskService:
    @staticmethod
    def get_task(
        db: Session,
        *,
        task_id: int,
    ) -> Task | None:
        return TaskRepository.get_by_id(
            db,
            task_id=task_id,
        )

    @staticmethod
    def require_task(
        db: Session,
        *,
        task_id: int,
    ) -> Task:
        task = TaskService.get_task(
            db,
            task_id=task_id,
        )

        if task is None:
            raise TaskNotFoundError(
                "Task was not found.",
            )

        return task

    @staticmethod
    def get_accessible_task(
        db: Session,
        *,
        actor: User,
        task_id: int,
    ) -> Task:
        task = TaskService.require_task(
            db,
            task_id=task_id,
        )

        TaskPermissionService.require_view(
            db,
            actor=actor,
            task=task,
        )

        return task

    @staticmethod
    def list_for_section(
        db: Session,
        *,
        actor: User,
        section: Section,
        filters: TaskFilterOptions | None = None,
    ) -> list[Task]:
        from app.auth.permissions import PermissionService

        PermissionService.require_section_access(
            db,
            actor=actor,
            section=section,
        )

        resolved_filters = (
            filters
            if filters is not None
            else TaskFilterOptions()
        )

        if resolved_filters.section_list_id is not None:
            section_list = SectionListRepository.get_by_id(
                db,
                section_list_id=(
                    resolved_filters.section_list_id
                ),
            )

            if (
                section_list is None
                or section_list.section_id != section.id
            ):
                raise TaskServiceError(
                    "The selected list does not belong to this section.",
                )

        return TaskRepository.list_for_section(
            db,
            section_id=section.id,
            state=resolved_filters.state,
            section_list_id=(
                resolved_filters.section_list_id
            ),
            assignee_user_id=(
                resolved_filters.assignee_user_id
            ),
            search=resolved_filters.search,
            due_from=resolved_filters.due_from,
            due_to=resolved_filters.due_to,
        )

    @staticmethod
    def list_for_section_id(
        db: Session,
        *,
        actor: User,
        section_id: int,
        filters: TaskFilterOptions | None = None,
    ) -> list[Task]:
        section = SectionService.require_section(
            db,
            section_id=section_id,
        )

        return TaskService.list_for_section(
            db,
            actor=actor,
            section=section,
            filters=filters,
        )

    @staticmethod
    def create_task(
        db: Session,
        *,
        actor: User,
        section_list: SectionList,
        task_create: TaskCreateRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> Task:
        if task_create.section_list_id != section_list.id:
            raise TaskServiceError(
                "The submitted list does not match the selected list.",
            )

        TaskPermissionService.require_create(
            db,
            actor=actor,
            section_list=section_list,
        )

        task = TaskRepository.create(
            db,
            section_list_id=section_list.id,
            created_by_user_id=actor.id,
            title=task_create.title,
            description=task_create.description,
            due_at=task_create.due_at,
        )

        TaskHistoryService.record_created(
            db,
            task=task,
            actor=actor,
        )

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.TASK_CREATED,
            summary=(
                f"{actor.display_name} created "
                f"{task.title}."
            ),
            entity_type="task",
            entity_id=task.id,
            metadata_json={
                "company_id": section_list.section.company_id,
                "section_id": section_list.section_id,
                "section_list_id": section_list.id,
                "title": task.title,
                "description": task.description,
                "due_at": task.due_at,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if task_create.assignee_user_ids:
            from app.schemas.task_assignee import (
                TaskAssigneeReplaceRequest,
            )
            from app.services.task_assignee_service import (
                TaskAssigneeService,
            )

            TaskAssigneeService.replace_assignees(
                db,
                actor=actor,
                task=task,
                replace_request=TaskAssigneeReplaceRequest(
                    user_ids=task_create.assignee_user_ids,
                ),
                ip_address=ip_address,
                user_agent=user_agent,
                commit=False,
            )

        if commit:
            db.commit()
            db.refresh(
                task,
            )

        return task

    @staticmethod
    def create_task_by_list_id(
        db: Session,
        *,
        actor: User,
        section_list_id: int,
        task_create: TaskCreateRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> Task:
        try:
            section_list = SectionListService.require_list(
                db,
                section_list_id=section_list_id,
            )

        except SectionListNotFoundError as exc:
            raise TaskDestinationListNotFoundError(
                "List was not found.",
            ) from exc

        return TaskService.create_task(
            db,
            actor=actor,
            section_list=section_list,
            task_create=task_create,
            ip_address=ip_address,
            user_agent=user_agent,
            commit=commit,
        )

    @staticmethod
    def update_task(
        db: Session,
        *,
        actor: User,
        task: Task,
        task_update: TaskUpdateRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> Task:
        TaskPermissionService.require_update(
            db,
            actor=actor,
            task=task,
        )

        changes: dict[str, Any] = {}

        if task.title != task_update.title:
            changes["title"] = {
                "previous": task.title,
                "current": task_update.title,
            }

        if task.description != task_update.description:
            changes["description"] = {
                "previous": task.description,
                "current": task_update.description,
            }

        if task.due_at != task_update.due_at:
            changes["due_at"] = {
                "previous": task.due_at,
                "current": task_update.due_at,
            }

        if not changes:
            return task

        TaskRepository.update(
            db,
            task=task,
            title=task_update.title,
            description=task_update.description,
            due_at=task_update.due_at,
        )

        TaskHistoryService.record_updated(
            db,
            task=task,
            actor=actor,
            changes=changes,
        )

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.TASK_UPDATED,
            summary=(
                f"{actor.display_name} updated "
                f"{task.title}."
            ),
            entity_type="task",
            entity_id=task.id,
            metadata_json={
                "section_id": task.section_id,
                "changes": changes,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()
            db.refresh(
                task,
            )

        return task

    @staticmethod
    def move_task(
        db: Session,
        *,
        actor: User,
        task: Task,
        destination_list: SectionList,
        move_request: TaskMoveRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> Task:
        if move_request.destination_list_id != destination_list.id:
            raise TaskServiceError(
                "The submitted destination does not match the selected list.",
            )

        TaskPermissionService.require_same_section(
            task=task,
            section_list=destination_list,
        )

        TaskPermissionService.require_active_destination_list(
            section_list=destination_list,
        )

        TaskPermissionService.require_move(
            db,
            actor=actor,
            task=task,
            destination_list=destination_list,
        )

        previous_list_id = task.section_list_id
        previous_position = task.sort_position

        TaskRepository.move(
            db,
            task=task,
            section_list_id=destination_list.id,
            sort_position=move_request.sort_position,
        )

        TaskHistoryService.record(
            db,
            task=task,
            actor=actor,
            event_type=TaskHistoryEventType.MOVED,
            summary=(
                f"{actor.display_name} moved this task "
                f"to {destination_list.name}."
            ),
            metadata_json={
                "previous_list_id": previous_list_id,
                "section_list_id": destination_list.id,
                "previous_sort_position": previous_position,
                "sort_position": task.sort_position,
            },
        )

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.TASK_MOVED,
            summary=(
                f"{actor.display_name} moved "
                f"{task.title} to {destination_list.name}."
            ),
            entity_type="task",
            entity_id=task.id,
            metadata_json={
                "section_id": task.section_id,
                "previous_list_id": previous_list_id,
                "section_list_id": destination_list.id,
                "previous_sort_position": previous_position,
                "sort_position": task.sort_position,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()
            db.refresh(
                task,
            )

        return task

    @staticmethod
    def reorder_tasks(
        db: Session,
        *,
        actor: User,
        section: Section,
        reorder_request: TaskReorderRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> list[Task]:
        TaskPermissionService.require_reorder(
            db,
            actor=actor,
            section=section,
        )

        list_ids = {
            item.section_list_id
            for item in reorder_request.items
        }

        section_lists = (
            SectionListRepository.list_for_section(
                db,
                section_id=section.id,
                include_archived=True,
            )
        )

        list_by_id = {
            section_list.id: section_list
            for section_list in section_lists
        }

        if not list_ids.issubset(
            list_by_id,
        ):
            raise TaskReorderError(
                "The reorder request contains a list "
                "that does not belong to this section.",
            )

        for list_id in list_ids:
            TaskPermissionService.require_active_destination_list(
                section_list=list_by_id[list_id],
            )

        submitted_task_ids = {
            item.task_id
            for item in reorder_request.items
        }

        section_tasks = TaskRepository.list_for_section(
            db,
            section_id=section.id,
            state="all",
        )

        task_by_id = {
            task.id: task
            for task in section_tasks
        }

        if not submitted_task_ids.issubset(
            task_by_id,
        ):
            raise TaskReorderError(
                "The reorder request contains a task "
                "that does not belong to this section.",
            )

        positions: dict[int, tuple[int, int]] = {}

        for item in reorder_request.items:
            task = task_by_id[item.task_id]

            TaskPermissionService.require_active_task(
                task=task,
            )

            destination_list = list_by_id[
                item.section_list_id
            ]

            TaskPermissionService.require_same_section(
                task=task,
                section_list=destination_list,
            )

            positions[item.task_id] = (
                item.section_list_id,
                item.sort_position,
            )

        TaskRepository.update_positions(
            db,
            positions=positions,
        )

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.TASK_MOVED,
            summary=(
                f"{actor.display_name} reordered tasks "
                f"in {section.name}."
            ),
            entity_type="section",
            entity_id=section.id,
            metadata_json={
                "task_positions": {
                    str(task_id): {
                        "section_list_id": values[0],
                        "sort_position": values[1],
                    }
                    for task_id, values in positions.items()
                },
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()

        return TaskRepository.list_for_section(
            db,
            section_id=section.id,
            state="all",
        )

    @staticmethod
    def complete_task(
        db: Session,
        *,
        actor: User,
        task: Task,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> Task:
        TaskPermissionService.require_complete(
            db,
            actor=actor,
            task=task,
        )

        if task.is_completed:
            raise TaskAlreadyCompletedError(
                "Task is already completed.",
            )

        TaskRepository.set_completed(
            db,
            task=task,
            completed_by_user_id=actor.id,
        )

        TaskHistoryService.record(
            db,
            task=task,
            actor=actor,
            event_type=TaskHistoryEventType.COMPLETED,
            summary=(
                f"{actor.display_name} completed this task."
            ),
            metadata_json={
                "completed_at": task.completed_at,
            },
        )

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.TASK_COMPLETED,
            summary=(
                f"{actor.display_name} completed "
                f"{task.title}."
            ),
            entity_type="task",
            entity_id=task.id,
            metadata_json={
                "section_id": task.section_id,
                "completed_at": task.completed_at,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()
            db.refresh(
                task,
            )

        return task

    @staticmethod
    def reopen_task(
        db: Session,
        *,
        actor: User,
        task: Task,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> Task:
        TaskPermissionService.require_complete(
            db,
            actor=actor,
            task=task,
        )

        if not task.is_completed:
            raise TaskNotCompletedError(
                "Task is not completed.",
            )

        previous_completed_at = task.completed_at
        previous_completed_by_user_id = (
            task.completed_by_user_id
        )

        TaskRepository.set_reopened(
            db,
            task=task,
        )

        TaskHistoryService.record(
            db,
            task=task,
            actor=actor,
            event_type=TaskHistoryEventType.REOPENED,
            summary=(
                f"{actor.display_name} reopened this task."
            ),
            metadata_json={
                "previous_completed_at": (
                    previous_completed_at
                ),
                "previous_completed_by_user_id": (
                    previous_completed_by_user_id
                ),
            },
        )

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.TASK_REOPENED,
            summary=(
                f"{actor.display_name} reopened "
                f"{task.title}."
            ),
            entity_type="task",
            entity_id=task.id,
            metadata_json={
                "section_id": task.section_id,
                "previous_completed_at": (
                    previous_completed_at
                ),
                "previous_completed_by_user_id": (
                    previous_completed_by_user_id
                ),
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()
            db.refresh(
                task,
            )

        return task

    @staticmethod
    def delete_task(
        db: Session,
        *,
        actor: User,
        task: Task,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> Task:
        TaskPermissionService.require_delete(
            db,
            actor=actor,
            task=task,
        )

        if task.is_deleted:
            raise TaskAlreadyDeletedError(
                "Task is already deleted.",
            )

        TaskRepository.soft_delete(
            db,
            task=task,
            deleted_by_user_id=actor.id,
        )

        TaskHistoryService.record(
            db,
            task=task,
            actor=actor,
            event_type=TaskHistoryEventType.DELETED,
            summary=(
                f"{actor.display_name} deleted this task."
            ),
            metadata_json={
                "deleted_at": task.deleted_at,
            },
        )

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.TASK_DELETED,
            summary=(
                f"{actor.display_name} deleted "
                f"{task.title}."
            ),
            entity_type="task",
            entity_id=task.id,
            metadata_json={
                "section_id": task.section_id,
                "section_list_id": task.section_list_id,
                "title": task.title,
                "deleted_at": task.deleted_at,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()
            db.refresh(
                task,
            )

        return task

    @staticmethod
    def restore_task(
        db: Session,
        *,
        actor: User,
        task: Task,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> Task:
        if not task.is_deleted:
            raise TaskNotDeletedError(
                "Task is not deleted.",
            )

        TaskPermissionService.require_restore(
            db,
            actor=actor,
            task=task,
        )

        previous_deleted_at = task.deleted_at
        previous_deleted_by_user_id = (
            task.deleted_by_user_id
        )

        TaskRepository.restore(
            db,
            task=task,
        )

        TaskHistoryService.record(
            db,
            task=task,
            actor=actor,
            event_type=TaskHistoryEventType.RESTORED,
            summary=(
                f"{actor.display_name} restored this task."
            ),
            metadata_json={
                "previous_deleted_at": previous_deleted_at,
                "previous_deleted_by_user_id": (
                    previous_deleted_by_user_id
                ),
            },
        )

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.TASK_RESTORED,
            summary=(
                f"{actor.display_name} restored "
                f"{task.title}."
            ),
            entity_type="task",
            entity_id=task.id,
            metadata_json={
                "section_id": task.section_id,
                "previous_deleted_at": previous_deleted_at,
                "previous_deleted_by_user_id": (
                    previous_deleted_by_user_id
                ),
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()
            db.refresh(
                task,
            )

        return task

    @staticmethod
    def permanently_delete_task(
        db: Session,
        *,
        actor: User,
        task: Task,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> None:
        if not task.is_deleted:
            raise TaskNotDeletedError(
                "Only deleted tasks can be permanently deleted.",
            )

        TaskPermissionService.require_permanent_delete(
            actor=actor,
            task=task,
        )

        task_id = task.id
        task_title = task.title
        section_id = task.section_id
        section_list_id = task.section_list_id

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.TASK_PERMANENTLY_DELETED,
            summary=(
                f"{actor.display_name} permanently deleted "
                f"{task_title}."
            ),
            entity_type="task",
            entity_id=task_id,
            metadata_json={
                "section_id": section_id,
                "section_list_id": section_list_id,
                "title": task_title,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        TaskRepository.permanently_delete(
            db,
            task=task,
        )

        if commit:
            db.commit()