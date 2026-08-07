from datetime import (
    datetime,
    time,
    timedelta,
    timezone,
)
from typing import Any
from zoneinfo import (
    ZoneInfo,
    ZoneInfoNotFoundError,
)
from sqlalchemy.orm import Session

from app.auth.permissions import PermissionDeniedError
from app.core.constants import (
    AuditAction,
    TaskHistoryEventType,
)
from app.core.timezone import utc_now
from app.models.section import Section
from app.models.section_list import SectionList
from app.models.task import Task
from app.models.user import User
from app.repositories.section_list_repository import (
    SectionListRepository,
)
from app.repositories.task_repository import TaskRepository
from app.schemas.my_tasks import (
    MyTaskSummary,
    MyTasksCompanyOption,
    MyTasksData,
    MyTasksFilterOptions,
    MyTasksMetrics,
    MyTasksSectionOption,
)
from app.schemas.task import (
    TaskCreateRequest,
    TaskFilterOptions,
    TaskMoveRequest,
    TaskReorderRequest,
    TaskUpdateRequest,
)
from app.services.audit_service import AuditService
from app.services.live_update_service import LiveUpdateService
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


class TaskLiveUpdateConflictError(TaskReorderError):
    """Raised when a board changed before a drag operation completed."""

    def __init__(
        self,
        message: str,
        *,
        current_revision: str,
    ) -> None:
        super().__init__(
            message,
        )
        self.current_revision = current_revision


class TaskAlreadyCompletedError(TaskServiceError):
    """Raised when an already completed task is completed again."""


class TaskNotCompletedError(TaskServiceError):
    """Raised when an open task is reopened."""


class TaskAlreadyDeletedError(TaskServiceError):
    """Raised when an already deleted task is deleted again."""


class TaskNotDeletedError(TaskServiceError):
    """Raised when a non-deleted task is restored."""

class MyTasksFilterError(TaskServiceError):
    """Raised when My Tasks filters are invalid."""

class DeletedTaskFilterError(TaskServiceError):
    """Raised when deleted-task filters are invalid."""

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
    def list_deleted_tasks(
        db: Session,
        *,
        actor: User,
        search: str | None = None,
        company_id: int | None = None,
        section_id: int | None = None,
        deleted_by_user_id: int | None = None,
        deleted_from: datetime | None = None,
        deleted_to: datetime | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[
        list[Task],
        int,
    ]:
        if not actor.is_administrator:
            raise PermissionDeniedError(
                "Administrator access is required.",
            )

        if page < 1:
            raise DeletedTaskFilterError(
                "The page number must be at least one.",
            )

        if page_size < 1 or page_size > 100:
            raise DeletedTaskFilterError(
                "The page size must be between 1 and 100.",
            )

        if (
            deleted_from is not None
            and deleted_to is not None
            and deleted_from >= deleted_to
        ):
            raise DeletedTaskFilterError(
                "The deletion start date must be before the end date.",
            )

        normalised_search = (
            search.strip()
            if search
            else None
        )

        if normalised_search == "":
            normalised_search = None

        total_items = TaskRepository.count_all_deleted(
            db,
            search=normalised_search,
            company_id=company_id,
            section_id=section_id,
            deleted_by_user_id=deleted_by_user_id,
            deleted_from=deleted_from,
            deleted_to=deleted_to,
        )

        tasks = TaskRepository.list_all_deleted(
            db,
            search=normalised_search,
            company_id=company_id,
            section_id=section_id,
            deleted_by_user_id=deleted_by_user_id,
            deleted_from=deleted_from,
            deleted_to=deleted_to,
            limit=page_size,
            offset=(
                page - 1
            ) * page_size,
        )

        return (
            tasks,
            total_items,
        )
    
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
    def get_my_tasks(
        db: Session,
        *,
        actor: User,
        filters: MyTasksFilterOptions | None = None,
        timezone_name: str = "Europe/London",
        due_soon_days: int = 7,
    ) -> MyTasksData:
        if not actor.can_authenticate:
            raise MyTasksFilterError(
                "An active user account is required.",
            )

        if due_soon_days < 1:
            raise MyTasksFilterError(
                "The due-soon period must be at least one day.",
            )

        resolved_filters = (
            filters
            if filters is not None
            else MyTasksFilterOptions()
        )

        (
            generated_at,
            today_start,
            tomorrow_start,
            due_soon_end,
        ) = TaskService._get_my_tasks_date_boundaries(
            timezone_name=timezone_name,
            due_soon_days=due_soon_days,
        )

        companies = TaskRepository.list_my_tasks_companies(
            db,
            user_id=actor.id,
        )

        company_ids = {
            company.id
            for company in companies
        }

        if (
            resolved_filters.company_id is not None
            and resolved_filters.company_id not in company_ids
        ):
            raise MyTasksFilterError(
                "The selected company is not available in My Tasks.",
            )

        sections = TaskRepository.list_my_tasks_sections(
            db,
            user_id=actor.id,
            company_id=resolved_filters.company_id,
        )

        section_ids = {
            section.id
            for section in sections
        }

        if (
            resolved_filters.section_id is not None
            and resolved_filters.section_id not in section_ids
        ):
            raise MyTasksFilterError(
                "The selected section is not available in My Tasks.",
            )

        tasks = TaskRepository.list_my_tasks(
            db,
            user_id=actor.id,
            state=resolved_filters.state,
            now=generated_at,
            today_start=today_start,
            tomorrow_start=tomorrow_start,
            due_soon_end=due_soon_end,
            company_id=resolved_filters.company_id,
            section_id=resolved_filters.section_id,
            search=resolved_filters.search,
        )

        metrics_data = TaskRepository.get_my_tasks_metrics(
            db,
            user_id=actor.id,
            now=generated_at,
            today_start=today_start,
            tomorrow_start=tomorrow_start,
            due_soon_end=due_soon_end,
        )

        return MyTasksData(
            generated_at=generated_at,
            filters=resolved_filters,
            metrics=MyTasksMetrics(
                **metrics_data,
            ),
            tasks=[
                TaskService._build_my_task_summary(
                    task,
                )
                for task in tasks
            ],
            companies=[
                MyTasksCompanyOption(
                    id=company.id,
                    name=company.name,
                )
                for company in companies
            ],
            sections=[
                MyTasksSectionOption(
                    id=section.id,
                    company_id=section.company_id,
                    name=section.name,
                    company_name=section.company.name,
                )
                for section in sections
            ],
        )

    @staticmethod
    def _build_my_task_summary(
        task: Task,
    ) -> MyTaskSummary:
        section_list = task.section_list
        section = section_list.section
        company = section.company

        return MyTaskSummary(
            id=task.id,
            title=task.title,
            description=task.description,
            company_id=company.id,
            company_name=company.name,
            section_id=section.id,
            section_name=section.name,
            section_list_id=section_list.id,
            section_list_name=section_list.name,
            due_at=task.due_at,
            completed_at=task.completed_at,
            updated_at=task.updated_at,
            state=task.state,
            assignee_names=[
                assignment.user.display_name
                for assignment in task.assignees
            ],
        )

    @staticmethod
    def _get_my_tasks_date_boundaries(
        *,
        timezone_name: str,
        due_soon_days: int,
    ) -> tuple[
        datetime,
        datetime,
        datetime,
        datetime,
    ]:
        try:
            local_timezone = ZoneInfo(
                timezone_name,
            )

        except ZoneInfoNotFoundError as exc:
            raise MyTasksFilterError(
                "The configured application timezone is invalid.",
            ) from exc

        generated_at = utc_now()

        local_now = generated_at.astimezone(
            local_timezone,
        )

        local_today = local_now.date()

        today_start = datetime.combine(
            local_today,
            time.min,
            tzinfo=local_timezone,
        ).astimezone(
            timezone.utc,
        )

        tomorrow_start = datetime.combine(
            local_today + timedelta(
                days=1,
            ),
            time.min,
            tzinfo=local_timezone,
        ).astimezone(
            timezone.utc,
        )

        due_soon_end = (
            generated_at
            + timedelta(
                days=due_soon_days,
            )
        )

        return (
            generated_at,
            today_start,
            tomorrow_start,
            due_soon_end,
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

        task.updated_at = utc_now()

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

        TaskService._require_current_section_revision(
            db,
            actor=actor,
            section_id=task.section_id,
            known_revision=move_request.known_revision,
        )

        previous_list_id = task.section_list_id
        previous_position = task.sort_position

        task.updated_at = utc_now()

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

        TaskService._require_current_section_revision(
            db,
            actor=actor,
            section_id=section.id,
            known_revision=reorder_request.known_revision,
        )

        active_lists = (
            SectionListRepository.list_for_section(
                db,
                section_id=section.id,
                include_archived=False,
            )
        )

        active_list_by_id = {
            section_list.id: section_list
            for section_list in active_lists
        }

        active_list_ids = set(
            active_list_by_id,
        )

        submitted_list_ids = {
            item.section_list_id
            for item in reorder_request.items
        }

        invalid_list_ids = (
            submitted_list_ids
            - active_list_ids
        )

        if invalid_list_ids:
            raise TaskReorderError(
                "The reorder request contains a list "
                "that is archived or does not belong "
                "to this section.",
            )

        section_tasks = (
            TaskRepository.list_for_section(
                db,
                section_id=section.id,
                state="all",
            )
        )

        reorderable_tasks = [
            task
            for task in section_tasks
            if (
                not task.is_deleted
                and task.section_list_id
                in active_list_ids
            )
        ]

        task_by_id = {
            task.id: task
            for task in reorderable_tasks
        }

        reorderable_task_ids = set(
            task_by_id,
        )

        submitted_task_ids = {
            item.task_id
            for item in reorder_request.items
        }

        unexpected_task_ids = (
            submitted_task_ids
            - reorderable_task_ids
        )

        if unexpected_task_ids:
            raise TaskReorderError(
                "The reorder request contains a task "
                "that is deleted or does not belong "
                "to this section.",
            )

        missing_task_ids = (
            reorderable_task_ids
            - submitted_task_ids
        )

        if missing_task_ids:
            raise TaskReorderError(
                "The reorder request must include every "
                "active task on the section board.",
            )

        requested_positions: dict[
            int,
            tuple[int, int],
        ] = {}

        changed_positions: dict[
            int,
            dict[str, int],
        ] = {}

        for item in reorder_request.items:
            task = task_by_id[
                item.task_id
            ]

            destination_list = active_list_by_id[
                item.section_list_id
            ]

            TaskPermissionService.require_active_task(
                task=task,
            )

            TaskPermissionService.require_same_section(
                task=task,
                section_list=destination_list,
            )

            requested_positions[task.id] = (
                item.section_list_id,
                item.sort_position,
            )

            if (
                task.section_list_id
                != item.section_list_id
                or task.sort_position
                != item.sort_position
            ):
                changed_positions[task.id] = {
                    "previous_section_list_id": (
                        task.section_list_id
                    ),
                    "section_list_id": (
                        item.section_list_id
                    ),
                    "previous_sort_position": (
                        task.sort_position
                    ),
                    "sort_position": (
                        item.sort_position
                    ),
                }

        if not changed_positions:
            return section_tasks

        changed_at = utc_now()

        for task_id in changed_positions:
            task_by_id[
                task_id
            ].updated_at = changed_at

        TaskRepository.update_positions(
            db,
            positions=requested_positions,
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
                "company_id": section.company_id,
                "section_id": section.id,
                "task_positions": {
                    str(task_id): values
                    for task_id, values
                    in changed_positions.items()
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

        task.updated_at = utc_now()

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

        task.updated_at = utc_now()

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

        task.updated_at = utc_now()

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

        task.updated_at = utc_now()

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
    def _require_current_section_revision(
        db: Session,
        *,
        actor: User,
        section_id: int,
        known_revision: str | None,
    ) -> None:
        if known_revision is None:
            return

        current = LiveUpdateService.get_section_revision(
            db,
            actor=actor,
            section_id=section_id,
        )

        if current.revision == known_revision:
            return

        raise TaskLiveUpdateConflictError(
            (
                "The section board changed while you were "
                "working. Reload the latest board and try again."
            ),
            current_revision=current.revision,
        )

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