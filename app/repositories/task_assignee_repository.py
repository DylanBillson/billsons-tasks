from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.task_assignee import TaskAssignee


class TaskAssigneeRepository:
    @staticmethod
    def get_by_id(
        db: Session,
        *,
        task_assignee_id: int,
    ) -> TaskAssignee | None:
        query = (
            select(TaskAssignee)
            .options(
                joinedload(
                    TaskAssignee.task,
                ),
                joinedload(
                    TaskAssignee.user,
                ),
            )
            .where(
                TaskAssignee.id == task_assignee_id,
            )
        )

        return db.scalar(
            query,
        )

    @staticmethod
    def get_by_task_and_user(
        db: Session,
        *,
        task_id: int,
        user_id: int,
    ) -> TaskAssignee | None:
        query = (
            select(TaskAssignee)
            .options(
                joinedload(
                    TaskAssignee.task,
                ),
                joinedload(
                    TaskAssignee.user,
                ),
            )
            .where(
                TaskAssignee.task_id == task_id,
                TaskAssignee.user_id == user_id,
            )
        )

        return db.scalar(
            query,
        )

    @staticmethod
    def exists(
        db: Session,
        *,
        task_id: int,
        user_id: int,
    ) -> bool:
        query = (
            select(
                TaskAssignee.id,
            )
            .where(
                TaskAssignee.task_id == task_id,
                TaskAssignee.user_id == user_id,
            )
            .limit(1)
        )

        return db.scalar(
            query,
        ) is not None

    @staticmethod
    def list_for_task(
        db: Session,
        *,
        task_id: int,
    ) -> list[TaskAssignee]:
        query = (
            select(TaskAssignee)
            .options(
                joinedload(
                    TaskAssignee.user,
                ),
            )
            .where(
                TaskAssignee.task_id == task_id,
            )
            .order_by(
                TaskAssignee.id.asc(),
            )
        )

        assignments = list(
            db.scalars(
                query,
            ).all(),
        )

        return sorted(
            assignments,
            key=lambda assignment: (
                assignment.user.display_name.casefold(),
                assignment.user.username.casefold(),
                assignment.id,
            ),
        )

    @staticmethod
    def list_for_user(
        db: Session,
        *,
        user_id: int,
    ) -> list[TaskAssignee]:
        query = (
            select(TaskAssignee)
            .options(
                joinedload(
                    TaskAssignee.task,
                ),
            )
            .where(
                TaskAssignee.user_id == user_id,
            )
            .order_by(
                TaskAssignee.created_at.desc(),
                TaskAssignee.id.desc(),
            )
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
    ) -> TaskAssignee:
        assignment = TaskAssignee(
            task_id=task_id,
            user_id=user_id,
        )

        db.add(
            assignment,
        )
        db.flush()

        return assignment

    @staticmethod
    def delete(
        db: Session,
        *,
        assignment: TaskAssignee,
    ) -> None:
        db.delete(
            assignment,
        )
        db.flush()

    @staticmethod
    def delete_all_for_task_except(
        db: Session,
        *,
        task_id: int,
        retained_user_ids: set[int],
    ) -> list[int]:
        assignments = list(
            db.scalars(
                select(TaskAssignee).where(
                    TaskAssignee.task_id == task_id,
                ),
            ).all(),
        )

        removed_user_ids: list[int] = []

        for assignment in assignments:
            if assignment.user_id in retained_user_ids:
                continue

            removed_user_ids.append(
                assignment.user_id,
            )

            db.delete(
                assignment,
            )

        db.flush()

        return removed_user_ids