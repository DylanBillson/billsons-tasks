from sqlalchemy.orm import Session

from app.auth.permissions import (
    PermissionDeniedError,
    PermissionService,
)
from app.models.section import Section
from app.models.section_list import SectionList
from app.models.task import Task
from app.models.user import User


class TaskPermissionService:
    """
    Task-focused permission facade.

    The underlying permission rules remain in PermissionService. This facade
    gives task-related services a concise API and centralises task-specific
    validation and error messages.
    """

    @staticmethod
    def can_view(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> bool:
        return PermissionService.can_view_task(
            db,
            actor=actor,
            task=task,
        )

    @staticmethod
    def can_create(
        db: Session,
        *,
        actor: User,
        section_list: SectionList,
    ) -> bool:
        return PermissionService.can_create_task(
            db,
            actor=actor,
            section_list=section_list,
        )

    @staticmethod
    def can_update(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> bool:
        return PermissionService.can_update_task(
            db,
            actor=actor,
            task=task,
        )

    @staticmethod
    def can_move(
        db: Session,
        *,
        actor: User,
        task: Task,
        destination_list: SectionList,
    ) -> bool:
        return PermissionService.can_move_task(
            db,
            actor=actor,
            task=task,
            destination_list=destination_list,
        )

    @staticmethod
    def can_reorder(
        db: Session,
        *,
        actor: User,
        section: Section,
    ) -> bool:
        return PermissionService.can_reorder_tasks(
            db,
            actor=actor,
            section=section,
        )

    @staticmethod
    def can_complete(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> bool:
        return PermissionService.can_complete_task(
            db,
            actor=actor,
            task=task,
        )

    @staticmethod
    def can_comment(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> bool:
        return PermissionService.can_comment_on_task(
            db,
            actor=actor,
            task=task,
        )

    @staticmethod
    def can_manage_assignees(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> bool:
        return PermissionService.can_manage_task_assignees(
            db,
            actor=actor,
            task=task,
        )

    @staticmethod
    def can_delete(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> bool:
        return PermissionService.can_delete_task(
            db,
            actor=actor,
            task=task,
        )

    @staticmethod
    def can_restore(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> bool:
        return PermissionService.can_restore_task(
            db,
            actor=actor,
            task=task,
        )

    @staticmethod
    def can_permanently_delete(
        *,
        actor: User,
        task: Task,
    ) -> bool:
        return PermissionService.can_permanently_delete_task(
            actor=actor,
            task=task,
        )

    @staticmethod
    def require_view(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> None:
        PermissionService.require_task_access(
            db,
            actor=actor,
            task=task,
        )

    @staticmethod
    def require_create(
        db: Session,
        *,
        actor: User,
        section_list: SectionList,
    ) -> None:
        PermissionService.require_task_creation(
            db,
            actor=actor,
            section_list=section_list,
        )

    @staticmethod
    def require_update(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> None:
        PermissionService.require_task_update(
            db,
            actor=actor,
            task=task,
        )

    @staticmethod
    def require_move(
        db: Session,
        *,
        actor: User,
        task: Task,
        destination_list: SectionList,
    ) -> None:
        PermissionService.require_task_movement(
            db,
            actor=actor,
            task=task,
            destination_list=destination_list,
        )

    @staticmethod
    def require_reorder(
        db: Session,
        *,
        actor: User,
        section: Section,
    ) -> None:
        PermissionService.require_task_reordering(
            db,
            actor=actor,
            section=section,
        )

    @staticmethod
    def require_complete(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> None:
        PermissionService.require_task_completion(
            db,
            actor=actor,
            task=task,
        )

    @staticmethod
    def require_comment(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> None:
        PermissionService.require_task_commenting(
            db,
            actor=actor,
            task=task,
        )

    @staticmethod
    def require_manage_assignees(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> None:
        PermissionService.require_task_assignee_management(
            db,
            actor=actor,
            task=task,
        )

    @staticmethod
    def require_delete(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> None:
        PermissionService.require_task_deletion(
            db,
            actor=actor,
            task=task,
        )

    @staticmethod
    def require_restore(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> None:
        PermissionService.require_task_restoration(
            db,
            actor=actor,
            task=task,
        )

    @staticmethod
    def require_permanent_delete(
        *,
        actor: User,
        task: Task,
    ) -> None:
        PermissionService.require_task_permanent_deletion(
            actor=actor,
            task=task,
        )

    @staticmethod
    def require_same_section(
        *,
        task: Task,
        section_list: SectionList,
    ) -> None:
        """
        Reject moving or associating a task with a list in another section.

        This validation is independent of the actor's role. Even an
        administrator must use a deliberate cross-section workflow rather
        than modifying a task through a same-section operation.
        """
        if task.section_id != section_list.section_id:
            raise PermissionDeniedError(
                "The task and list must belong to the same section.",
            )

    @staticmethod
    def require_active_task(
        *,
        task: Task,
    ) -> None:
        if task.is_deleted:
            raise PermissionDeniedError(
                "Deleted tasks cannot be modified.",
            )

    @staticmethod
    def require_active_destination_list(
        *,
        section_list: SectionList,
    ) -> None:
        if section_list.section.company.is_archived:
            raise PermissionDeniedError(
                "Tasks cannot be moved into an archived company.",
            )

        if section_list.section.is_archived:
            raise PermissionDeniedError(
                "Tasks cannot be moved into an archived section.",
            )

        if section_list.is_archived:
            raise PermissionDeniedError(
                "Tasks cannot be moved into an archived list.",
            )