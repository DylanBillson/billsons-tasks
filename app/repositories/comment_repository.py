from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.timezone import utc_now
from app.models.task_comment import TaskComment


class CommentRepository:
    @staticmethod
    def get_by_id(
        db: Session,
        *,
        comment_id: int,
    ) -> TaskComment | None:
        query = (
            select(TaskComment)
            .options(
                joinedload(
                    TaskComment.task,
                ),
                joinedload(
                    TaskComment.user,
                ),
                joinedload(
                    TaskComment.deleted_by,
                ),
            )
            .where(
                TaskComment.id == comment_id,
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
        include_deleted: bool = False,
    ) -> list[TaskComment]:
        query = (
            select(TaskComment)
            .options(
                joinedload(
                    TaskComment.user,
                ),
                joinedload(
                    TaskComment.deleted_by,
                ),
            )
            .where(
                TaskComment.task_id == task_id,
            )
        )

        if not include_deleted:
            query = query.where(
                TaskComment.deleted_at.is_(None),
            )

        query = query.order_by(
            TaskComment.created_at.asc(),
            TaskComment.id.asc(),
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
        user_id: int,
        body: str,
    ) -> TaskComment:
        comment = TaskComment(
            task_id=task_id,
            user_id=user_id,
            body=body,
        )

        db.add(
            comment,
        )
        db.flush()

        return comment

    @staticmethod
    def soft_delete(
        db: Session,
        *,
        comment: TaskComment,
        deleted_by_user_id: int,
        deleted_at: datetime | None = None,
    ) -> TaskComment:
        comment.deleted_at = (
            deleted_at
            if deleted_at is not None
            else utc_now()
        )
        comment.deleted_by_user_id = deleted_by_user_id

        db.flush()

        return comment

    @staticmethod
    def restore(
        db: Session,
        *,
        comment: TaskComment,
    ) -> TaskComment:
        comment.deleted_at = None
        comment.deleted_by_user_id = None

        db.flush()

        return comment

    @staticmethod
    def permanently_delete(
        db: Session,
        *,
        comment: TaskComment,
    ) -> None:
        db.delete(
            comment,
        )
        db.flush()