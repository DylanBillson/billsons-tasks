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


class CompanyRepository:
    @staticmethod
    def get_by_id(
        db: Session,
        company_id: int,
    ) -> Company | None:
        query = (
            select(Company)
            .options(
                selectinload(
                    Company.memberships,
                ),
                selectinload(
                    Company.sections,
                ),
            )
            .where(
                Company.id == company_id,
            )
        )

        return db.scalar(
            query,
        )

    @staticmethod
    def get_by_name(
        db: Session,
        name: str,
    ) -> Company | None:
        query = (
            select(Company)
            .where(
                Company.name == name,
            )
        )

        return db.scalar(
            query,
        )

    @staticmethod
    def list_all(
        db: Session,
        *,
        include_archived: bool = False,
    ) -> list[Company]:
        query = (
            select(Company)
            .options(
                selectinload(
                    Company.memberships,
                ),
            )
        )

        if not include_archived:
            query = query.where(
                Company.is_archived.is_(False),
            )

        query = query.order_by(
            Company.name.asc(),
            Company.id.asc(),
        )

        return list(
            db.scalars(
                query,
            ).all(),
        )

    @staticmethod
    def list_for_user(
        db: Session,
        *,
        user_id: int,
        include_archived: bool = False,
    ) -> list[Company]:
        query = (
            select(Company)
            .join(
                CompanyMembership,
                CompanyMembership.company_id
                == Company.id,
            )
            .options(
                selectinload(
                    Company.memberships,
                ),
            )
            .where(
                CompanyMembership.user_id
                == user_id,
            )
        )

        if not include_archived:
            query = query.where(
                Company.is_archived.is_(False),
            )

        query = (
            query
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
    def get_dashboard_metrics(
        db: Session,
        *,
        company_id: int,
        actor: User,
        now: datetime,
    ) -> dict[str, int]:
        section_scope = (
            CompanyRepository._accessible_section_condition(
                actor=actor,
            )
        )

        section_count = int(
            db.scalar(
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
                .where(
                    Section.company_id
                    == company_id,
                    Section.is_archived.is_(False),
                    section_scope,
                ),
            )
            or 0
        )

        member_count = int(
            db.scalar(
                select(
                    func.count(
                        CompanyMembership.id,
                    ),
                ).where(
                    CompanyMembership.company_id
                    == company_id,
                ),
            )
            or 0
        )

        task_counts = db.execute(
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
                SectionList.id
                == Task.section_list_id,
            )
            .join(
                Section,
                Section.id
                == SectionList.section_id,
            )
            .where(
                Section.company_id
                == company_id,
                Section.is_archived.is_(False),
                SectionList.is_archived.is_(False),
                section_scope,
            ),
        ).one()

        return {
            "section_count": section_count,
            "member_count": member_count,
            "open_task_count": int(
                task_counts.open_task_count
                or 0,
            ),
            "overdue_task_count": int(
                task_counts.overdue_task_count
                or 0,
            ),
            "completed_task_count": int(
                task_counts.completed_task_count
                or 0,
            ),
            "deleted_task_count": int(
                task_counts.deleted_task_count
                or 0,
            ),
        }

    @staticmethod
    def list_dashboard_due_soon_tasks(
        db: Session,
        *,
        company_id: int,
        actor: User,
        due_from: datetime,
        due_to: datetime,
        limit: int = 10,
    ) -> list[Task]:
        query = (
            CompanyRepository._dashboard_task_query()
            .where(
                Section.company_id
                == company_id,
                Task.deleted_at.is_(None),
                Task.completed_at.is_(None),
                Task.due_at.is_not(None),
                Task.due_at >= due_from,
                Task.due_at <= due_to,
                CompanyRepository._accessible_section_condition(
                    actor=actor,
                ),
            )
            .order_by(
                Task.due_at.asc(),
                Task.id.asc(),
            )
            .limit(
                limit,
            )
        )

        return list(
            db.scalars(
                query,
            ).unique().all(),
        )

    @staticmethod
    def list_dashboard_recent_tasks(
        db: Session,
        *,
        company_id: int,
        actor: User,
        limit: int = 10,
    ) -> list[Task]:
        query = (
            CompanyRepository._dashboard_task_query()
            .where(
                Section.company_id
                == company_id,
                Task.deleted_at.is_(None),
                CompanyRepository._accessible_section_condition(
                    actor=actor,
                ),
            )
            .order_by(
                Task.updated_at.desc(),
                Task.id.desc(),
            )
            .limit(
                limit,
            )
        )

        return list(
            db.scalars(
                query,
            ).unique().all(),
        )

    @staticmethod
    def create(
        db: Session,
        *,
        name: str,
        description: str | None = None,
    ) -> Company:
        company = Company(
            name=name,
            description=description,
        )

        db.add(
            company,
        )
        db.flush()

        return company

    @staticmethod
    def update(
        db: Session,
        *,
        company: Company,
        name: str,
        description: str | None,
    ) -> Company:
        company.name = name
        company.description = description

        db.flush()

        return company

    @staticmethod
    def set_archived(
        db: Session,
        *,
        company: Company,
        is_archived: bool,
    ) -> Company:
        company.is_archived = is_archived

        db.flush()

        return company

    @staticmethod
    def delete(
        db: Session,
        *,
        company: Company,
    ) -> None:
        db.delete(
            company,
        )
        db.flush()

    @staticmethod
    def _dashboard_task_query():
        return (
            select(
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
            .options(
                joinedload(
                    Task.section_list,
                )
                .joinedload(
                    SectionList.section,
                )
                .joinedload(
                    Section.company,
                ),
                selectinload(
                    Task.assignees,
                ).joinedload(
                    TaskAssignee.user,
                ),
            )
            .where(
                Section.is_archived.is_(False),
                SectionList.is_archived.is_(False),
            )
        )

    @staticmethod
    def _accessible_section_condition(
        *,
        actor: User,
    ):
        if actor.is_administrator:
            return Section.id.is_not(None)

        return or_(
            Section.created_by_user_id
            == actor.id,
            exists(
                select(
                    SectionMembership.id,
                ).where(
                    SectionMembership.section_id
                    == Section.id,
                    SectionMembership.user_id
                    == actor.id,
                ),
            ),
        )