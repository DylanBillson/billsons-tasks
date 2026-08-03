from sqlalchemy.orm import Session

from app.auth.permissions import PermissionService
from app.core.constants import (
    AuditAction,
    TaskHistoryEventType,
)
from app.models.task import Task
from app.models.task_assignee import TaskAssignee
from app.models.user import User
from app.repositories.company_membership_repository import (
    CompanyMembershipRepository,
)
from app.repositories.task_assignee_repository import (
    TaskAssigneeRepository,
)
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.schemas.task_assignee import (
    TaskAssigneeCreateRequest,
    TaskAssigneeReplaceRequest,
)
from app.services.audit_service import AuditService
from app.services.task_history_service import (
    TaskHistoryService,
)
from app.services.task_permission_service import (
    TaskPermissionService,
)


class TaskAssigneeServiceError(ValueError):
    """Base exception for task-assignee failures."""


class TaskAssigneeNotFoundError(
    TaskAssigneeServiceError,
):
    """Raised when a task assignment cannot be found."""


class TaskAssigneeUserNotFoundError(
    TaskAssigneeServiceError,
):
    """Raised when an assignee user cannot be found."""


class TaskAssigneeUserUnavailableError(
    TaskAssigneeServiceError,
):
    """Raised when an assignee cannot authenticate."""


class TaskAssigneeCompanyMembershipRequiredError(
    TaskAssigneeServiceError,
):
    """Raised when an assignee is not in the parent company."""


class TaskAssigneeSectionAccessRequiredError(
    TaskAssigneeServiceError,
):
    """Raised when an assignee has no access to the section."""


class TaskAssigneeAlreadyExistsError(
    TaskAssigneeServiceError,
):
    """Raised when a user is already assigned to a task."""


class TaskAssigneeService:
    @staticmethod
    def get_assignment(
        db: Session,
        *,
        task_id: int,
        user_id: int,
    ) -> TaskAssignee | None:
        return TaskAssigneeRepository.get_by_task_and_user(
            db,
            task_id=task_id,
            user_id=user_id,
        )

    @staticmethod
    def require_assignment(
        db: Session,
        *,
        task_id: int,
        user_id: int,
    ) -> TaskAssignee:
        assignment = (
            TaskAssigneeService.get_assignment(
                db,
                task_id=task_id,
                user_id=user_id,
            )
        )

        if assignment is None:
            raise TaskAssigneeNotFoundError(
                "Task assignment was not found.",
            )

        return assignment

    @staticmethod
    def list_for_task(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> list[TaskAssignee]:
        TaskPermissionService.require_view(
            db,
            actor=actor,
            task=task,
        )

        return TaskAssigneeRepository.list_for_task(
            db,
            task_id=task.id,
        )

    @staticmethod
    def add_assignee(
        db: Session,
        *,
        actor: User,
        task: Task,
        create_request: TaskAssigneeCreateRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> TaskAssignee:
        TaskPermissionService.require_manage_assignees(
            db,
            actor=actor,
            task=task,
        )

        user = TaskAssigneeService._require_eligible_user(
            db,
            task=task,
            user_id=create_request.user_id,
        )

        existing = TaskAssigneeRepository.get_by_task_and_user(
            db,
            task_id=task.id,
            user_id=user.id,
        )

        if existing is not None:
            raise TaskAssigneeAlreadyExistsError(
                "This user is already assigned to the task.",
            )

        assignment = TaskAssigneeRepository.create(
            db,
            task_id=task.id,
            user_id=user.id,
        )

        TaskHistoryService.record(
            db,
            task=task,
            actor=actor,
            event_type=TaskHistoryEventType.ASSIGNEE_ADDED,
            summary=(
                f"{actor.display_name} assigned "
                f"{user.display_name}."
            ),
            metadata_json={
                "assignee_user_id": user.id,
                "assignee_display_name": user.display_name,
            },
        )

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.TASK_ASSIGNEE_ADDED,
            summary=(
                f"{actor.display_name} assigned "
                f"{user.display_name} to {task.title}."
            ),
            entity_type="task",
            entity_id=task.id,
            metadata_json={
                "section_id": task.section_id,
                "assignee_user_id": user.id,
                "assignee_display_name": user.display_name,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()
            db.refresh(
                assignment,
            )

        return assignment

    @staticmethod
    def remove_assignee(
        db: Session,
        *,
        actor: User,
        assignment: TaskAssignee,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> None:
        task = TaskRepository.get_by_id(
            db,
            task_id=assignment.task_id,
        )

        if task is None:
            raise TaskAssigneeNotFoundError(
                "The assignment's task was not found.",
            )

        TaskPermissionService.require_manage_assignees(
            db,
            actor=actor,
            task=task,
        )

        user_id = assignment.user_id
        display_name = assignment.user.display_name

        TaskAssigneeRepository.delete(
            db,
            assignment=assignment,
        )

        TaskHistoryService.record(
            db,
            task=task,
            actor=actor,
            event_type=TaskHistoryEventType.ASSIGNEE_REMOVED,
            summary=(
                f"{actor.display_name} unassigned "
                f"{display_name}."
            ),
            metadata_json={
                "assignee_user_id": user_id,
                "assignee_display_name": display_name,
            },
        )

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.TASK_ASSIGNEE_REMOVED,
            summary=(
                f"{actor.display_name} removed "
                f"{display_name} from {task.title}."
            ),
            entity_type="task",
            entity_id=task.id,
            metadata_json={
                "section_id": task.section_id,
                "assignee_user_id": user_id,
                "assignee_display_name": display_name,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()

    @staticmethod
    def replace_assignees(
        db: Session,
        *,
        actor: User,
        task: Task,
        replace_request: TaskAssigneeReplaceRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> list[TaskAssignee]:
        TaskPermissionService.require_manage_assignees(
            db,
            actor=actor,
            task=task,
        )

        requested_user_ids = set(
            replace_request.user_ids,
        )

        eligible_users = {
            user_id: TaskAssigneeService._require_eligible_user(
                db,
                task=task,
                user_id=user_id,
            )
            for user_id in requested_user_ids
        }

        existing_assignments = (
            TaskAssigneeRepository.list_for_task(
                db,
                task_id=task.id,
            )
        )

        existing_by_user_id = {
            assignment.user_id: assignment
            for assignment in existing_assignments
        }

        removed_user_ids = (
            set(existing_by_user_id)
            - requested_user_ids
        )

        added_user_ids = (
            requested_user_ids
            - set(existing_by_user_id)
        )

        for user_id in removed_user_ids:
            assignment = existing_by_user_id[
                user_id
            ]

            display_name = assignment.user.display_name

            TaskAssigneeRepository.delete(
                db,
                assignment=assignment,
            )

            TaskHistoryService.record(
                db,
                task=task,
                actor=actor,
                event_type=(
                    TaskHistoryEventType.ASSIGNEE_REMOVED
                ),
                summary=(
                    f"{actor.display_name} unassigned "
                    f"{display_name}."
                ),
                metadata_json={
                    "assignee_user_id": user_id,
                    "assignee_display_name": display_name,
                },
            )

        for user_id in added_user_ids:
            user = eligible_users[user_id]

            TaskAssigneeRepository.create(
                db,
                task_id=task.id,
                user_id=user.id,
            )

            TaskHistoryService.record(
                db,
                task=task,
                actor=actor,
                event_type=(
                    TaskHistoryEventType.ASSIGNEE_ADDED
                ),
                summary=(
                    f"{actor.display_name} assigned "
                    f"{user.display_name}."
                ),
                metadata_json={
                    "assignee_user_id": user.id,
                    "assignee_display_name": user.display_name,
                },
            )

        if removed_user_ids or added_user_ids:
            AuditService.record(
                db,
                user=actor,
                action=AuditAction.TASK_UPDATED,
                summary=(
                    f"{actor.display_name} updated assignees "
                    f"for {task.title}."
                ),
                entity_type="task",
                entity_id=task.id,
                metadata_json={
                    "section_id": task.section_id,
                    "added_user_ids": sorted(
                        added_user_ids,
                    ),
                    "removed_user_ids": sorted(
                        removed_user_ids,
                    ),
                },
                ip_address=ip_address,
                user_agent=user_agent,
            )

        if commit:
            db.commit()

        return TaskAssigneeRepository.list_for_task(
            db,
            task_id=task.id,
        )

    @staticmethod
    def _require_eligible_user(
        db: Session,
        *,
        task: Task,
        user_id: int,
    ) -> User:
        user = UserRepository.get_by_id(
            db,
            user_id=user_id,
        )

        if user is None:
            raise TaskAssigneeUserNotFoundError(
                "The selected user was not found.",
            )

        if not user.can_authenticate:
            raise TaskAssigneeUserUnavailableError(
                "The selected user is not available.",
            )

        section = task.section_list.section
        company = section.company

        is_administrator = (
            PermissionService.is_administrator(
                user,
            )
        )

        if (
            not is_administrator
            and not CompanyMembershipRepository.exists(
                db,
                company_id=company.id,
                user_id=user.id,
            )
        ):
            raise (
                TaskAssigneeCompanyMembershipRequiredError(
                    "The selected user is not a member "
                    "of the task's company.",
                )
            )

        if not PermissionService.can_view_section(
            db,
            actor=user,
            section=section,
        ):
            raise TaskAssigneeSectionAccessRequiredError(
                "The selected user does not have access "
                "to the task's section.",
            )

        return user