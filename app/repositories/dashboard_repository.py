from datetime import datetime

from sqlalchemy import (
    and_,
    case,
    exists,
    func,
    or_,
    select,
)
from sqlalchemy.orm import (
    Session,
    joinedload,
    selectinload,
)

from app.models.company import Company
from app.models.company_membership import CompanyMembership
from app.models.section import Section
from app.models.section_list import SectionList
from app.models.section_membership import SectionMembership
from app.models.task import Task
from app.models.task_assignee import TaskAssignee
from app.models.user import User


class DashboardRepository:
    @staticmethod
    def get_metrics(
        db: Session,
        *,
        actor: User,
        now: datetime,
    ) -> dict[str, int | None]:
        company_query = (
            select(
                func.count(
                    func.distinct(
                        Company.id,
                    ),
                ),
            )
            .select_from(
                Company,
            )
            .where(
                Company.is_archived.is_(False),
            )
        )

        if not actor.is_administrator:
            company_query = company_query.where(
                exists(
                    select(
                        CompanyMembership.id,
                    ).where(
                        CompanyMembership.company_id
                        == Company.id,
                        CompanyMembership.user_id
                        == actor.id,
                    ),
                ),
            )

        company_count = int(
            db.scalar(
                company_query,
            )
            or 0
        )

        section_query = (
            select(
                func.count(
                    func.distinct(
                        Section.id,
                    ),
                ),
            )
            .select_from(
                Section,
            )
            .join(
                Company,
                Company.id == Section.company_id,
            )
            .where(
                Company.is_archived.is_(False),
                Section.is_archived.is_(False),
            )
        )

        if not actor.is_administrator:
            section_query = section_query.where(
                DashboardRepository._accessible_section_condition(
                    actor_id=actor.id,
                ),
            )

        section_count = int(
            db.scalar(
                section_query,
            )
            or 0
        )

        active_user_count: int | None = None

        if actor.is_administrator:
            active_user_count = int(
                db.scalar(
                    select(
                        func.count(
                            User.id,
                        ),
                    ).where(
                        User.is_active.is_(True),
                        User.is_anonymised.is_(False),
                    ),
                )
                or 0
            )

        task_query = (
            select(
                func.count(
                    case(
                        (
                            and_(
                                Task.deleted_at.is_(None),
                                Task.completed_at.is_(None),
                            ),
                            Task.id,
                        ),
                    ),
                ).label(
                    "open_task_count",
                ),
                func.count(
                    case(
                        (
                            and_(
                                Task.deleted_at.is_(None),
                                Task.completed_at.is_(None),
                                Task.due_at.is_not(None),
                                Task.due_at < now,
                            ),
                            Task.id,
                        ),
                    ),
                ).label(
                    "overdue_task_count",
                ),
                func.count(
                    case(
                        (
                            and_(
                                Task.deleted_at.is_(None),
                                Task.completed_at.is_not(None),
                            ),
                            Task.id,
                        ),
                    ),
                ).label(
                    "completed_task_count",
                ),
                func.count(
                    case(
                        (
                            Task.deleted_at.is_not(None),
                            Task.id,
                        ),
                    ),
                ).label(
                    "deleted_task_count",
                ),
            )
            .select_from(
                Task,
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
                Company.is_archived.is_(False),
                Section.is_archived.is_(False),
                SectionList.is_archived.is_(False),
            )
        )

        if not actor.is_administrator:
            task_query = task_query.where(
                DashboardRepository._accessible_section_condition(
                    actor_id=actor.id,
                ),
            )

        task_counts = db.execute(
            task_query,
        ).one()

        return {
            "company_count": company_count,
            "section_count": section_count,
            "active_user_count": active_user_count,
            "open_task_count": int(
                task_counts.open_task_count
                or 0
            ),
            "overdue_task_count": int(
                task_counts.overdue_task_count
                or 0
            ),
            "completed_task_count": int(
                task_counts.completed_task_count
                or 0
            ),
            "deleted_task_count": int(
                task_counts.deleted_task_count
                or 0
            ),
        }

    @staticmethod
    def list_company_summaries(
        db: Session,
        *,
        actor: User,
        now: datetime,
        limit: int = 20,
    ) -> list[dict[str, int | str]]:
        section_join_condition = and_(
            Section.company_id == Company.id,
            Section.is_archived.is_(False),
        )

        if not actor.is_administrator:
            section_join_condition = and_(
                section_join_condition,
                DashboardRepository._accessible_section_condition(
                    actor_id=actor.id,
                ),
            )

        query = (
            select(
                Company.id.label(
                    "company_id",
                ),
                Company.name.label(
                    "company_name",
                ),
                func.count(
                    func.distinct(
                        Section.id,
                    ),
                ).label(
                    "section_count",
                ),
                func.count(
                    func.distinct(
                        case(
                            (
                                and_(
                                    Task.deleted_at.is_(None),
                                    Task.completed_at.is_(None),
                                ),
                                Task.id,
                            ),
                        ),
                    ),
                ).label(
                    "open_task_count",
                ),
                func.count(
                    func.distinct(
                        case(
                            (
                                and_(
                                    Task.deleted_at.is_(None),
                                    Task.completed_at.is_(None),
                                    Task.due_at.is_not(None),
                                    Task.due_at < now,
                                ),
                                Task.id,
                            ),
                        ),
                    ),
                ).label(
                    "overdue_task_count",
                ),
                func.count(
                    func.distinct(
                        case(
                            (
                                and_(
                                    Task.deleted_at.is_(None),
                                    Task.completed_at.is_not(None),
                                ),
                                Task.id,
                            ),
                        ),
                    ),
                ).label(
                    "completed_task_count",
                ),
            )
            .select_from(
                Company,
            )
            .outerjoin(
                Section,
                section_join_condition,
            )
            .outerjoin(
                SectionList,
                and_(
                    SectionList.section_id == Section.id,
                    SectionList.is_archived.is_(False),
                ),
            )
            .outerjoin(
                Task,
                Task.section_list_id == SectionList.id,
            )
            .where(
                Company.is_archived.is_(False),
            )
        )

        if not actor.is_administrator:
            query = query.where(
                exists(
                    select(
                        CompanyMembership.id,
                    ).where(
                        CompanyMembership.company_id
                        == Company.id,
                        CompanyMembership.user_id
                        == actor.id,
                    ),
                ),
            )

        query = (
            query
            .group_by(
                Company.id,
                Company.name,
            )
            .order_by(
                Company.name.asc(),
                Company.id.asc(),
            )
            .limit(
                limit,
            )
        )

        rows = db.execute(
            query,
        ).all()

        return [
            {
                "id": int(
                    row.company_id,
                ),
                "name": str(
                    row.company_name,
                ),
                "section_count": int(
                    row.section_count
                    or 0,
                ),
                "open_task_count": int(
                    row.open_task_count
                    or 0,
                ),
                "overdue_task_count": int(
                    row.overdue_task_count
                    or 0,
                ),
                "completed_task_count": int(
                    row.completed_task_count
                    or 0,
                ),
            }
            for row in rows
        ]

    @staticmethod
    def list_due_soon_tasks(
        db: Session,
        *,
        actor: User,
        due_from: datetime,
        due_to: datetime,
        limit: int = 10,
    ) -> list[Task]:
        query = (
            DashboardRepository._task_summary_query()
            .where(
                Task.deleted_at.is_(None),
                Task.completed_at.is_(None),
                Task.due_at.is_not(None),
                Task.due_at >= due_from,
                Task.due_at <= due_to,
            )
            .order_by(
                Task.due_at.asc(),
                Task.id.asc(),
            )
            .limit(
                limit,
            )
        )

        query = DashboardRepository._apply_task_access_scope(
            query,
            actor=actor,
        )

        return list(
            db.scalars(
                query,
            ).unique().all(),
        )

    @staticmethod
    def list_recent_tasks(
        db: Session,
        *,
        actor: User,
        limit: int = 10,
    ) -> list[Task]:
        query = (
            DashboardRepository._task_summary_query()
            .where(
                Task.deleted_at.is_(None),
            )
            .order_by(
                Task.updated_at.desc(),
                Task.id.desc(),
            )
            .limit(
                limit,
            )
        )

        query = DashboardRepository._apply_task_access_scope(
            query,
            actor=actor,
        )

        return list(
            db.scalars(
                query,
            ).unique().all(),
        )

    @staticmethod
    def _task_summary_query():
        return (
            select(
                Task,
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
            .options(
                joinedload(
                    Task.section_list,
                ).joinedload(
                    SectionList.section,
                ).joinedload(
                    Section.company,
                ),
                selectinload(
                    Task.assignees,
                ).joinedload(
                    TaskAssignee.user,
                ),
            )
            .where(
                Company.is_archived.is_(False),
                Section.is_archived.is_(False),
                SectionList.is_archived.is_(False),
            )
        )

    @staticmethod
    def _apply_task_access_scope(
        query,
        *,
        actor: User,
    ):
        if actor.is_administrator:
            return query

        return query.where(
            DashboardRepository._accessible_section_condition(
                actor_id=actor.id,
            ),
        )

    @staticmethod
    def _accessible_section_condition(
        *,
        actor_id: int,
    ):
        return or_(
            Section.created_by_user_id == actor_id,
            exists(
                select(
                    SectionMembership.id,
                ).where(
                    SectionMembership.section_id
                    == Section.id,
                    SectionMembership.user_id
                    == actor_id,
                ),
            ),
        )