from datetime import datetime
from app.models.company import Company

from sqlalchemy import (
    and_,
    case,
    func,
    or_,
    select,
)
from sqlalchemy.orm import (
    Session,
    joinedload,
    selectinload,
)

from app.core.timezone import utc_now
from app.models.section import Section
from app.models.section_list import SectionList
from app.models.task import Task
from app.models.task_assignee import TaskAssignee
from app.models.company import Company

class TaskRepository:
    @staticmethod
    def get_by_id(
        db: Session,
        *,
        task_id: int,
    ) -> Task | None:
        query = (
            select(Task)
            .options(
                joinedload(
                    Task.section_list,
                ).joinedload(
                    SectionList.section,
                ).joinedload(
                    Section.company,
                ),
                joinedload(
                    Task.section_list,
                ).joinedload(
                    SectionList.section,
                ).joinedload(
                    Section.created_by,
                ),
                joinedload(
                    Task.created_by,
                ),
                joinedload(
                    Task.completed_by,
                ),
                joinedload(
                    Task.deleted_by,
                ),
                selectinload(
                    Task.assignees,
                ).joinedload(
                    TaskAssignee.user,
                ),
                selectinload(
                    Task.comments,
                ),
                selectinload(
                    Task.history_events,
                ),
            )
            .where(
                Task.id == task_id,
            )
        )

        return db.scalar(
            query,
        )

    @staticmethod
    def list_for_list(
        db: Session,
        *,
        section_list_id: int,
        include_deleted: bool = False,
    ) -> list[Task]:
        query = (
            TaskRepository._base_list_query()
            .where(
                Task.section_list_id == section_list_id,
            )
        )

        if not include_deleted:
            query = query.where(
                Task.deleted_at.is_(None),
            )

        query = query.order_by(
            Task.sort_position.asc(),
            Task.id.asc(),
        )

        return list(
            db.scalars(
                query,
            ).unique().all(),
        )

    @staticmethod
    def list_for_section(
        db: Session,
        *,
        section_id: int,
        state: str = "all",
        section_list_id: int | None = None,
        assignee_user_id: int | None = None,
        search: str | None = None,
        due_from: datetime | None = None,
        due_to: datetime | None = None,
    ) -> list[Task]:
        query = (
            TaskRepository._base_list_query()
            .join(
                SectionList,
                SectionList.id == Task.section_list_id,
            )
            .where(
                SectionList.section_id == section_id,
            )
        )

        if section_list_id is not None:
            query = query.where(
                Task.section_list_id == section_list_id,
            )

        if assignee_user_id is not None:
            query = (
                query
                .join(
                    TaskAssignee,
                    TaskAssignee.task_id == Task.id,
                )
                .where(
                    TaskAssignee.user_id == assignee_user_id,
                )
            )

        if search is not None:
            pattern = f"%{search}%"

            query = query.where(
                or_(
                    Task.title.ilike(
                        pattern,
                    ),
                    Task.description.ilike(
                        pattern,
                    ),
                ),
            )

        if due_from is not None:
            query = query.where(
                Task.due_at >= due_from,
            )

        if due_to is not None:
            query = query.where(
                Task.due_at <= due_to,
            )

        query = TaskRepository._apply_state_filter(
            query,
            state=state,
        )

        query = query.order_by(
            SectionList.sort_position.asc(),
            SectionList.id.asc(),
            Task.sort_position.asc(),
            Task.id.asc(),
        )

        return list(
            db.scalars(
                query,
            ).unique().all(),
        )

    @staticmethod
    def list_assigned_to_user(
        db: Session,
        *,
        user_id: int,
        include_completed: bool = True,
        include_deleted: bool = False,
    ) -> list[Task]:
        query = (
            TaskRepository._base_list_query()
            .join(
                TaskAssignee,
                TaskAssignee.task_id == Task.id,
            )
            .where(
                TaskAssignee.user_id == user_id,
            )
        )

        if not include_completed:
            query = query.where(
                Task.completed_at.is_(None),
            )

        if not include_deleted:
            query = query.where(
                Task.deleted_at.is_(None),
            )

        query = query.order_by(
            Task.due_at.asc().nullslast(),
            Task.updated_at.desc(),
            Task.id.desc(),
        )

        return list(
            db.scalars(
                query,
            ).unique().all(),
        )

    @staticmethod
    def list_my_tasks(
        db: Session,
        *,
        user_id: int,
        state: str,
        now: datetime,
        today_start: datetime,
        tomorrow_start: datetime,
        due_soon_end: datetime,
        company_id: int | None = None,
        section_id: int | None = None,
        search: str | None = None,
    ) -> list[Task]:
        query = (
            TaskRepository._base_list_query()
            .join(
                TaskAssignee,
                TaskAssignee.task_id == Task.id,
            )
            .join(
                SectionList,
                SectionList.id == Task.section_list_id,
            )
            .join(
                Section,
                Section.id == SectionList.section_id,
            )
            .join(
                Company,
                Company.id == Section.company_id,
            )
            .where(
                TaskAssignee.user_id == user_id,
                Task.deleted_at.is_(None),
                Company.is_archived.is_(False),
                Section.is_archived.is_(False),
                SectionList.is_archived.is_(False),
            )
        )

        if company_id is not None:
            query = query.where(
                Company.id == company_id,
            )

        if section_id is not None:
            query = query.where(
                Section.id == section_id,
            )

        if search is not None:
            pattern = f"%{search}%"

            query = query.where(
                or_(
                    Task.title.ilike(
                        pattern,
                    ),
                    Task.description.ilike(
                        pattern,
                    ),
                ),
            )

        query = TaskRepository._apply_my_tasks_state_filter(
            query,
            state=state,
            now=now,
            today_start=today_start,
            tomorrow_start=tomorrow_start,
            due_soon_end=due_soon_end,
        )

        query = query.order_by(
            Task.completed_at.asc().nullsfirst(),
            Task.due_at.asc().nullslast(),
            Task.updated_at.desc(),
            Task.id.desc(),
        )

        return list(
            db.scalars(
                query,
            ).unique().all(),
        )

    @staticmethod
    def get_my_tasks_metrics(
        db: Session,
        *,
        user_id: int,
        now: datetime,
        today_start: datetime,
        tomorrow_start: datetime,
        due_soon_end: datetime,
    ) -> dict[str, int]:
        row = db.execute(
            select(
                func.count(
                    Task.id,
                ).label(
                    "all_count",
                ),
                func.count(
                    case(
                        (
                            Task.completed_at.is_(None),
                            Task.id,
                        ),
                    ),
                ).label(
                    "open_count",
                ),
                func.count(
                    case(
                        (
                            and_(
                                Task.completed_at.is_(None),
                                Task.due_at.is_not(None),
                                Task.due_at < now,
                            ),
                            Task.id,
                        ),
                    ),
                ).label(
                    "overdue_count",
                ),
                func.count(
                    case(
                        (
                            and_(
                                Task.completed_at.is_(None),
                                Task.due_at.is_not(None),
                                Task.due_at >= today_start,
                                Task.due_at < tomorrow_start,
                            ),
                            Task.id,
                        ),
                    ),
                ).label(
                    "due_today_count",
                ),
                func.count(
                    case(
                        (
                            and_(
                                Task.completed_at.is_(None),
                                Task.due_at.is_not(None),
                                Task.due_at >= now,
                                Task.due_at <= due_soon_end,
                            ),
                            Task.id,
                        ),
                    ),
                ).label(
                    "due_soon_count",
                ),
                func.count(
                    case(
                        (
                            Task.completed_at.is_not(None),
                            Task.id,
                        ),
                    ),
                ).label(
                    "completed_count",
                ),
            )
            .select_from(
                Task,
            )
            .join(
                TaskAssignee,
                TaskAssignee.task_id == Task.id,
            )
            .join(
                SectionList,
                SectionList.id == Task.section_list_id,
            )
            .join(
                Section,
                Section.id == SectionList.section_id,
            )
            .join(
                Company,
                Company.id == Section.company_id,
            )
            .where(
                TaskAssignee.user_id == user_id,
                Task.deleted_at.is_(None),
                Company.is_archived.is_(False),
                Section.is_archived.is_(False),
                SectionList.is_archived.is_(False),
            ),
        ).one()

        return {
            "all_count": int(
                row.all_count
                or 0,
            ),
            "open_count": int(
                row.open_count
                or 0,
            ),
            "overdue_count": int(
                row.overdue_count
                or 0,
            ),
            "due_today_count": int(
                row.due_today_count
                or 0,
            ),
            "due_soon_count": int(
                row.due_soon_count
                or 0,
            ),
            "completed_count": int(
                row.completed_count
                or 0,
            ),
        }

    @staticmethod
    def list_my_tasks_companies(
        db: Session,
        *,
        user_id: int,
    ) -> list[Company]:
        query = (
            select(
                Company,
            )
            .join(
                Section,
                Section.company_id == Company.id,
            )
            .join(
                SectionList,
                SectionList.section_id == Section.id,
            )
            .join(
                Task,
                Task.section_list_id == SectionList.id,
            )
            .join(
                TaskAssignee,
                TaskAssignee.task_id == Task.id,
            )
            .where(
                TaskAssignee.user_id == user_id,
                Task.deleted_at.is_(None),
                Company.is_archived.is_(False),
                Section.is_archived.is_(False),
                SectionList.is_archived.is_(False),
            )
            .order_by(
                Company.name.asc(),
                Company.id.asc(),
            )
            .distinct()
        )

        return list(
            db.scalars(
                query,
            ).unique().all(),
        )

    @staticmethod
    def list_my_tasks_sections(
        db: Session,
        *,
        user_id: int,
        company_id: int | None = None,
    ) -> list[Section]:
        query = (
            select(
                Section,
            )
            .join(
                Company,
                Company.id == Section.company_id,
            )
            .join(
                SectionList,
                SectionList.section_id == Section.id,
            )
            .join(
                Task,
                Task.section_list_id == SectionList.id,
            )
            .join(
                TaskAssignee,
                TaskAssignee.task_id == Task.id,
            )
            .where(
                TaskAssignee.user_id == user_id,
                Task.deleted_at.is_(None),
                Company.is_archived.is_(False),
                Section.is_archived.is_(False),
                SectionList.is_archived.is_(False),
            )
            .options(
                joinedload(
                    Section.company,
                ),
            )
        )

        if company_id is not None:
            query = query.where(
                Company.id == company_id,
            )

        query = (
            query
            .distinct()
            .order_by(
                Section.name.asc(),
                Section.id.asc(),
            )
        )

        return list(
            db.scalars(
                query,
            ).unique().all(),
        )

    @staticmethod
    def list_deleted_for_section(
        db: Session,
        *,
        section_id: int,
    ) -> list[Task]:
        query = (
            TaskRepository._base_list_query()
            .join(
                SectionList,
                SectionList.id == Task.section_list_id,
            )
            .where(
                SectionList.section_id == section_id,
                Task.deleted_at.is_not(None),
            )
            .order_by(
                Task.deleted_at.desc(),
                Task.id.desc(),
            )
        )

        return list(
            db.scalars(
                query,
            ).unique().all(),
        )

    @staticmethod
    def list_all_deleted(
        db: Session,
        *,
        search: str | None = None,
        company_id: int | None = None,
        section_id: int | None = None,
        deleted_by_user_id: int | None = None,
        deleted_from: datetime | None = None,
        deleted_to: datetime | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[Task]:
        query = (
            TaskRepository._base_list_query()
            .join(
                SectionList,
                SectionList.id
                == Task.section_list_id,
            )
            .join(
                Section,
                Section.id
                == SectionList.section_id,
            )
            .join(
                Company,
                Company.id
                == Section.company_id,
            )
            .where(
                Task.deleted_at.is_not(None),
            )
        )

        query = TaskRepository._apply_deleted_filters(
            query,
            search=search,
            company_id=company_id,
            section_id=section_id,
            deleted_by_user_id=deleted_by_user_id,
            deleted_from=deleted_from,
            deleted_to=deleted_to,
        )

        query = (
            query
            .order_by(
                Task.deleted_at.desc(),
                Task.id.desc(),
            )
            .limit(
                limit,
            )
            .offset(
                offset,
            )
        )

        return list(
            db.scalars(
                query,
            ).unique().all(),
        )

    @staticmethod
    def count_all_deleted(
        db: Session,
        *,
        search: str | None = None,
        company_id: int | None = None,
        section_id: int | None = None,
        deleted_by_user_id: int | None = None,
        deleted_from: datetime | None = None,
        deleted_to: datetime | None = None,
    ) -> int:
        query = (
            select(
                func.count(
                    Task.id,
                ),
            )
            .select_from(
                Task,
            )
            .join(
                SectionList,
                SectionList.id
                == Task.section_list_id,
            )
            .join(
                Section,
                Section.id
                == SectionList.section_id,
            )
            .join(
                Company,
                Company.id
                == Section.company_id,
            )
            .where(
                Task.deleted_at.is_not(None),
            )
        )

        query = TaskRepository._apply_deleted_filters(
            query,
            search=search,
            company_id=company_id,
            section_id=section_id,
            deleted_by_user_id=deleted_by_user_id,
            deleted_from=deleted_from,
            deleted_to=deleted_to,
        )

        return int(
            db.scalar(
                query,
            )
            or 0
        )

    @staticmethod
    def get_max_sort_position(
        db: Session,
        *,
        section_list_id: int,
        include_deleted: bool = False,
    ) -> int | None:
        query = (
            select(
                func.max(
                    Task.sort_position,
                ),
            )
            .where(
                Task.section_list_id == section_list_id,
            )
        )

        if not include_deleted:
            query = query.where(
                Task.deleted_at.is_(None),
            )

        result = db.scalar(
            query,
        )

        if result is None:
            return None

        return int(
            result,
        )

    @staticmethod
    def get_next_sort_position(
        db: Session,
        *,
        section_list_id: int,
        increment: int = 1000,
    ) -> int:
        maximum = TaskRepository.get_max_sort_position(
            db,
            section_list_id=section_list_id,
        )

        if maximum is None:
            return increment

        return maximum + increment

    @staticmethod
    def create(
        db: Session,
        *,
        section_list_id: int,
        created_by_user_id: int,
        title: str,
        description: str | None = None,
        due_at: datetime | None = None,
        sort_position: int | None = None,
    ) -> Task:
        resolved_sort_position = (
            sort_position
            if sort_position is not None
            else TaskRepository.get_next_sort_position(
                db,
                section_list_id=section_list_id,
            )
        )

        task = Task(
            section_list_id=section_list_id,
            created_by_user_id=created_by_user_id,
            title=title,
            description=description,
            due_at=due_at,
            sort_position=resolved_sort_position,
        )

        db.add(
            task,
        )
        db.flush()

        return task

    @staticmethod
    def update(
        db: Session,
        *,
        task: Task,
        title: str,
        description: str | None,
        due_at: datetime | None,
    ) -> Task:
        task.title = title
        task.description = description
        task.due_at = due_at

        db.flush()

        return task

    @staticmethod
    def move(
        db: Session,
        *,
        task: Task,
        section_list_id: int,
        sort_position: int,
    ) -> Task:
        task.section_list_id = section_list_id
        task.sort_position = sort_position

        db.flush()

        return task

    @staticmethod
    def set_completed(
        db: Session,
        *,
        task: Task,
        completed_by_user_id: int,
        completed_at: datetime | None = None,
    ) -> Task:
        task.completed_at = (
            completed_at
            if completed_at is not None
            else utc_now()
        )
        task.completed_by_user_id = completed_by_user_id

        db.flush()

        return task

    @staticmethod
    def set_reopened(
        db: Session,
        *,
        task: Task,
    ) -> Task:
        task.completed_at = None
        task.completed_by_user_id = None

        db.flush()

        return task

    @staticmethod
    def soft_delete(
        db: Session,
        *,
        task: Task,
        deleted_by_user_id: int,
        deleted_at: datetime | None = None,
    ) -> Task:
        task.deleted_at = (
            deleted_at
            if deleted_at is not None
            else utc_now()
        )
        task.deleted_by_user_id = deleted_by_user_id

        db.flush()

        return task

    @staticmethod
    def restore(
        db: Session,
        *,
        task: Task,
    ) -> Task:
        task.deleted_at = None
        task.deleted_by_user_id = None

        db.flush()

        return task

    @staticmethod
    def update_sort_position(
        db: Session,
        *,
        task: Task,
        sort_position: int,
    ) -> Task:
        task.sort_position = sort_position

        db.flush()

        return task

    @staticmethod
    def update_positions(
        db: Session,
        *,
        positions: dict[int, tuple[int, int]],
    ) -> None:
        """
        Update task list IDs and sort positions in one flush.

        ``positions`` maps:

        ``task_id -> (section_list_id, sort_position)``
        """
        if not positions:
            return

        tasks = list(
            db.scalars(
                select(Task).where(
                    Task.id.in_(
                        positions,
                    ),
                ),
            ).all(),
        )

        for task in tasks:
            (
                section_list_id,
                sort_position,
            ) = positions[
                task.id
            ]

            task.section_list_id = section_list_id
            task.sort_position = sort_position

        db.flush()

    @staticmethod
    def permanently_delete(
        db: Session,
        *,
        task: Task,
    ) -> None:
        db.delete(
            task,
        )
        db.flush()

    @staticmethod
    def _base_list_query():
        return (
            select(Task)
            .options(
                joinedload(
                    Task.section_list,
                ).joinedload(
                    SectionList.section,
                ).joinedload(
                    Section.company,
                ),
                joinedload(
                    Task.created_by,
                ),
                joinedload(
                    Task.completed_by,
                ),
                joinedload(
                    Task.deleted_by,
                ),
                selectinload(
                    Task.assignees,
                ).joinedload(
                    TaskAssignee.user,
                ),
            )
        )

    @staticmethod
    def _apply_state_filter(
        query,
        *,
        state: str,
    ):
        if state == "deleted":
            return query.where(
                Task.deleted_at.is_not(None),
            )

        query = query.where(
            Task.deleted_at.is_(None),
        )

        if state == "completed":
            return query.where(
                Task.completed_at.is_not(None),
            )

        if state == "overdue":
            return query.where(
                Task.completed_at.is_(None),
                Task.due_at.is_not(None),
                Task.due_at < utc_now(),
            )

        if state == "open":
            return query.where(
                Task.completed_at.is_(None),
            )

        return query
    
    @staticmethod
    def _apply_deleted_filters(
        query,
        *,
        search: str | None,
        company_id: int | None,
        section_id: int | None,
        deleted_by_user_id: int | None,
        deleted_from: datetime | None,
        deleted_to: datetime | None,
    ):
        if search:
            pattern = (
                f"%{search.strip()}%"
            )

            query = query.where(
                or_(
                    Task.title.ilike(
                        pattern,
                    ),
                    Task.description.ilike(
                        pattern,
                    ),
                    Company.name.ilike(
                        pattern,
                    ),
                    Section.name.ilike(
                        pattern,
                    ),
                    SectionList.name.ilike(
                        pattern,
                    ),
                ),
            )

        if company_id is not None:
            query = query.where(
                Company.id == company_id,
            )

        if section_id is not None:
            query = query.where(
                Section.id == section_id,
            )

        if deleted_by_user_id is not None:
            query = query.where(
                Task.deleted_by_user_id
                == deleted_by_user_id,
            )

        if deleted_from is not None:
            query = query.where(
                Task.deleted_at >= deleted_from,
            )

        if deleted_to is not None:
            query = query.where(
                Task.deleted_at < deleted_to,
            )

        return query
    
    @staticmethod
    def _apply_my_tasks_state_filter(
        query,
        *,
        state: str,
        now: datetime,
        today_start: datetime,
        tomorrow_start: datetime,
        due_soon_end: datetime,
    ):
        if state == "completed":
            return query.where(
                Task.completed_at.is_not(None),
            )

        if state == "overdue":
            return query.where(
                Task.completed_at.is_(None),
                Task.due_at.is_not(None),
                Task.due_at < now,
            )

        if state == "due_today":
            return query.where(
                Task.completed_at.is_(None),
                Task.due_at.is_not(None),
                Task.due_at >= today_start,
                Task.due_at < tomorrow_start,
            )

        if state == "due_soon":
            return query.where(
                Task.completed_at.is_(None),
                Task.due_at.is_not(None),
                Task.due_at >= now,
                Task.due_at <= due_soon_end,
            )

        if state == "open":
            return query.where(
                Task.completed_at.is_(None),
            )

        return query