from sqlalchemy.orm import Session

from app.auth.permissions import PermissionService
from app.core.constants import (
    AuditAction,
    TaskHistoryEventType,
)
from app.models.task import Task
from app.models.task_comment import TaskComment
from app.models.user import User
from app.repositories.comment_repository import (
    CommentRepository,
)
from app.repositories.task_repository import TaskRepository
from app.schemas.comment import TaskCommentCreateRequest
from app.services.audit_service import AuditService
from app.services.task_history_service import (
    TaskHistoryService,
)
from app.services.task_permission_service import (
    TaskPermissionService,
)


class CommentServiceError(ValueError):
    """Base exception for task-comment failures."""


class CommentNotFoundError(CommentServiceError):
    """Raised when a task comment cannot be found."""


class CommentAlreadyDeletedError(CommentServiceError):
    """Raised when an already deleted comment is deleted again."""


class CommentPermissionError(CommentServiceError):
    """Raised when an actor cannot delete a comment."""


class CommentService:
    @staticmethod
    def get_comment(
        db: Session,
        *,
        comment_id: int,
    ) -> TaskComment | None:
        return CommentRepository.get_by_id(
            db,
            comment_id=comment_id,
        )

    @staticmethod
    def require_comment(
        db: Session,
        *,
        comment_id: int,
    ) -> TaskComment:
        comment = CommentService.get_comment(
            db,
            comment_id=comment_id,
        )

        if comment is None:
            raise CommentNotFoundError(
                "Comment was not found.",
            )

        return comment

    @staticmethod
    def list_for_task(
        db: Session,
        *,
        actor: User,
        task: Task,
        include_deleted: bool = False,
    ) -> list[TaskComment]:
        TaskPermissionService.require_view(
            db,
            actor=actor,
            task=task,
        )

        if include_deleted:
            can_manage_section = (
                PermissionService.can_manage_section(
                    db,
                    actor=actor,
                    section=task.section_list.section,
                )
            )

            if not can_manage_section:
                include_deleted = False

        return CommentRepository.list_for_task(
            db,
            task_id=task.id,
            include_deleted=include_deleted,
        )

    @staticmethod
    def add_comment(
        db: Session,
        *,
        actor: User,
        task: Task,
        comment_create: TaskCommentCreateRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> TaskComment:
        TaskPermissionService.require_comment(
            db,
            actor=actor,
            task=task,
        )

        comment = CommentRepository.create(
            db,
            task_id=task.id,
            user_id=actor.id,
            body=comment_create.body,
        )

        TaskHistoryService.record(
            db,
            task=task,
            actor=actor,
            event_type=TaskHistoryEventType.COMMENT_ADDED,
            summary=(
                f"{actor.display_name} added a comment."
            ),
            metadata_json={
                "comment_id": comment.id,
            },
        )

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.TASK_COMMENT_ADDED,
            summary=(
                f"{actor.display_name} commented on "
                f"{task.title}."
            ),
            entity_type="task",
            entity_id=task.id,
            metadata_json={
                "section_id": task.section_id,
                "comment_id": comment.id,
                "comment_content": comment.body,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()
            db.refresh(
                comment,
            )

        return comment

    @staticmethod
    def delete_comment(
        db: Session,
        *,
        actor: User,
        comment: TaskComment,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> TaskComment:
        if comment.is_deleted:
            raise CommentAlreadyDeletedError(
                "Comment is already deleted.",
            )

        task = TaskRepository.get_by_id(
            db,
            task_id=comment.task_id,
        )

        if task is None:
            raise CommentNotFoundError(
                "The comment's task was not found.",
            )

        TaskPermissionService.require_view(
            db,
            actor=actor,
            task=task,
        )

        is_author = (
            comment.user_id is not None
            and comment.user_id == actor.id
        )

        can_manage_section = (
            PermissionService.can_manage_section(
                db,
                actor=actor,
                section=task.section_list.section,
            )
        )

        if not is_author and not can_manage_section:
            raise CommentPermissionError(
                "You do not have permission to delete this comment.",
            )

        CommentRepository.soft_delete(
            db,
            comment=comment,
            deleted_by_user_id=actor.id,
        )

        TaskHistoryService.record(
            db,
            task=task,
            actor=actor,
            event_type=TaskHistoryEventType.COMMENT_DELETED,
            summary=(
                f"{actor.display_name} deleted a comment."
            ),
            metadata_json={
                "comment_id": comment.id,
                "comment_author_user_id": comment.user_id,
            },
        )

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.TASK_COMMENT_DELETED,
            summary=(
                f"{actor.display_name} deleted a comment "
                f"from {task.title}."
            ),
            entity_type="task",
            entity_id=task.id,
            metadata_json={
                "section_id": task.section_id,
                "comment_id": comment.id,
                "comment_author_user_id": comment.user_id,
                "deleted_comment_content": comment.body,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()
            db.refresh(
                comment,
            )

        return comment