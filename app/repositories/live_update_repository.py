from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.section import Section
from app.models.section_list import SectionList
from app.models.task import Task
from app.models.task_assignee import TaskAssignee
from app.models.task_comment import TaskComment
from app.models.task_history_event import TaskHistoryEvent
from app.schemas.live_updates import (
    SectionLiveUpdateSnapshot,
    TaskLiveUpdateSnapshot,
)


class LiveUpdateRepository:
    @staticmethod
    def get_section_snapshot(
        db: Session,
        *,
        section_id: int,
    ) -> SectionLiveUpdateSnapshot | None:
        section_updated_at = db.scalar(
            select(
                Section.updated_at,
            ).where(
                Section.id == section_id,
            ),
        )

        if section_updated_at is None:
            return None

        section_list_stats = db.execute(
            select(
                func.count(
                    SectionList.id,
                ),
                func.max(
                    SectionList.updated_at,
                ),
            ).where(
                SectionList.section_id == section_id,
            ),
        ).one()

        task_stats = db.execute(
            select(
                func.count(
                    Task.id,
                ),
                func.max(
                    Task.updated_at,
                ),
            )
            .join(
                SectionList,
                SectionList.id == Task.section_list_id,
            )
            .where(
                SectionList.section_id == section_id,
            ),
        ).one()

        task_assignee_stats = db.execute(
            select(
                func.count(
                    TaskAssignee.id,
                ),
                func.max(
                    TaskAssignee.updated_at,
                ),
            )
            .join(
                Task,
                Task.id == TaskAssignee.task_id,
            )
            .join(
                SectionList,
                SectionList.id == Task.section_list_id,
            )
            .where(
                SectionList.section_id == section_id,
            ),
        ).one()

        return SectionLiveUpdateSnapshot(
            section_id=section_id,
            section_updated_at=section_updated_at,
            section_list_count=int(
                section_list_stats[0],
            ),
            latest_section_list_updated_at=(
                section_list_stats[1]
            ),
            task_count=int(
                task_stats[0],
            ),
            latest_task_updated_at=task_stats[1],
            task_assignee_count=int(
                task_assignee_stats[0],
            ),
            latest_task_assignee_updated_at=(
                task_assignee_stats[1]
            ),
        )

    @staticmethod
    def get_task_snapshot(
        db: Session,
        *,
        task_id: int,
    ) -> TaskLiveUpdateSnapshot | None:
        task_row = db.execute(
            select(
                Task.updated_at,
                SectionList.id,
                SectionList.updated_at,
                Section.id,
                Section.updated_at,
            )
            .join(
                SectionList,
                SectionList.id == Task.section_list_id,
            )
            .join(
                Section,
                Section.id == SectionList.section_id,
            )
            .where(
                Task.id == task_id,
            ),
        ).one_or_none()

        if task_row is None:
            return None

        comment_stats = db.execute(
            select(
                func.count(
                    TaskComment.id,
                ),
                func.max(
                    TaskComment.updated_at,
                ),
            ).where(
                TaskComment.task_id == task_id,
            ),
        ).one()

        history_stats = db.execute(
            select(
                func.count(
                    TaskHistoryEvent.id,
                ),
                func.max(
                    TaskHistoryEvent.created_at,
                ),
            ).where(
                TaskHistoryEvent.task_id == task_id,
            ),
        ).one()

        task_assignee_stats = db.execute(
            select(
                func.count(
                    TaskAssignee.id,
                ),
                func.max(
                    TaskAssignee.updated_at,
                ),
            ).where(
                TaskAssignee.task_id == task_id,
            ),
        ).one()

        return TaskLiveUpdateSnapshot(
            task_id=task_id,
            task_updated_at=task_row[0],
            section_list_id=task_row[1],
            section_list_updated_at=task_row[2],
            section_id=task_row[3],
            section_updated_at=task_row[4],
            comment_count=int(
                comment_stats[0],
            ),
            latest_comment_updated_at=(
                comment_stats[1]
            ),
            history_event_count=int(
                history_stats[0],
            ),
            latest_history_event_created_at=(
                history_stats[1]
            ),
            task_assignee_count=int(
                task_assignee_stats[0],
            ),
            latest_task_assignee_updated_at=(
                task_assignee_stats[1]
            ),
        )