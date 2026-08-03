from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.company import Company
from app.models.section import Section
from app.models.section_membership import SectionMembership


class SectionRepository:
    @staticmethod
    def get_by_id(
        db: Session,
        section_id: int,
    ) -> Section | None:
        query = (
            select(Section)
            .options(
                joinedload(
                    Section.company,
                ),
                joinedload(
                    Section.created_by,
                ),
                selectinload(
                    Section.memberships,
                ),
            )
            .where(
                Section.id == section_id,
            )
        )

        return db.scalar(
            query,
        )

    @staticmethod
    def get_by_company_and_name(
        db: Session,
        *,
        company_id: int,
        name: str,
    ) -> Section | None:
        query = (
            select(Section)
            .where(
                Section.company_id == company_id,
                Section.name == name,
            )
        )

        return db.scalar(
            query,
        )

    @staticmethod
    def list_for_company(
        db: Session,
        *,
        company_id: int,
        include_archived: bool = False,
    ) -> list[Section]:
        query = (
            select(Section)
            .options(
                joinedload(
                    Section.created_by,
                ),
                selectinload(
                    Section.memberships,
                ),
            )
            .where(
                Section.company_id == company_id,
            )
        )

        if not include_archived:
            query = query.where(
                Section.is_archived.is_(False),
            )

        query = query.order_by(
            Section.name.asc(),
            Section.id.asc(),
        )

        return list(
            db.scalars(
                query,
            ).unique().all(),
        )

    @staticmethod
    def list_created_by_user(
        db: Session,
        *,
        user_id: int,
        company_id: int | None = None,
        include_archived: bool = False,
    ) -> list[Section]:
        query = (
            select(Section)
            .options(
                joinedload(
                    Section.company,
                ),
                selectinload(
                    Section.memberships,
                ),
            )
            .where(
                Section.created_by_user_id == user_id,
            )
        )

        if company_id is not None:
            query = query.where(
                Section.company_id == company_id,
            )

        if not include_archived:
            query = query.where(
                Section.is_archived.is_(False),
            )

        query = query.order_by(
            Section.name.asc(),
            Section.id.asc(),
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
        company_id: int | None = None,
        include_archived: bool = False,
    ) -> list[Section]:
        query = (
            select(Section)
            .join(
                SectionMembership,
                SectionMembership.section_id
                == Section.id,
            )
            .options(
                joinedload(
                    Section.company,
                ),
                joinedload(
                    Section.created_by,
                ),
            )
            .where(
                SectionMembership.user_id == user_id,
            )
        )

        if company_id is not None:
            query = query.where(
                Section.company_id == company_id,
            )

        if not include_archived:
            query = query.where(
                Section.is_archived.is_(False),
            )

        query = (
            query
            .order_by(
                Section.name.asc(),
                Section.id.asc(),
            )
            .distinct()
        )

        return list(
            db.scalars(
                query,
            ).unique().all(),
        )

    @staticmethod
    def list_accessible_to_user(
        db: Session,
        *,
        user_id: int,
        company_id: int | None = None,
        include_archived: bool = False,
    ) -> list[Section]:
        assigned_section_ids = (
            select(
                SectionMembership.section_id,
            )
            .where(
                SectionMembership.user_id == user_id,
            )
        )

        query = (
            select(Section)
            .options(
                joinedload(
                    Section.company,
                ),
                joinedload(
                    Section.created_by,
                ),
                selectinload(
                    Section.memberships,
                ),
            )
            .where(
                or_(
                    Section.created_by_user_id == user_id,
                    Section.id.in_(
                        assigned_section_ids,
                    ),
                ),
            )
        )

        if company_id is not None:
            query = query.where(
                Section.company_id == company_id,
            )

        if not include_archived:
            query = query.where(
                Section.is_archived.is_(False),
            )

        query = query.order_by(
            Section.name.asc(),
            Section.id.asc(),
        )

        return list(
            db.scalars(
                query,
            ).unique().all(),
        )

    @staticmethod
    def list_archived(
        db: Session,
        *,
        company_id: int | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> list[Section]:
        query = (
            select(
                Section,
            )
            .join(
                Company,
                Company.id == Section.company_id,
            )
            .options(
                joinedload(
                    Section.company,
                ),
                joinedload(
                    Section.created_by,
                ),
                selectinload(
                    Section.memberships,
                ),
            )
            .where(
                Section.is_archived.is_(True),
            )
        )

        query = SectionRepository._apply_archived_filters(
            query,
            company_id=company_id,
            search=search,
        )

        query = (
            query
            .order_by(
                Company.name.asc(),
                Section.name.asc(),
                Section.id.asc(),
            )
            .offset(
                offset,
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
    def count_archived(
        db: Session,
        *,
        company_id: int | None = None,
        search: str | None = None,
    ) -> int:
        query = (
            select(
                func.count(
                    Section.id,
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
                Section.is_archived.is_(True),
            )
        )

        query = SectionRepository._apply_archived_filters(
            query,
            company_id=company_id,
            search=search,
        )

        return int(
            db.scalar(
                query,
            )
            or 0
        )

    @staticmethod
    def create(
        db: Session,
        *,
        company_id: int,
        created_by_user_id: int,
        name: str,
        description: str | None = None,
    ) -> Section:
        section = Section(
            company_id=company_id,
            created_by_user_id=created_by_user_id,
            name=name,
            description=description,
        )

        db.add(
            section,
        )
        db.flush()

        return section

    @staticmethod
    def update(
        db: Session,
        *,
        section: Section,
        name: str,
        description: str | None,
    ) -> Section:
        section.name = name
        section.description = description

        db.flush()

        return section

    @staticmethod
    def set_archived(
        db: Session,
        *,
        section: Section,
        is_archived: bool,
    ) -> Section:
        section.is_archived = is_archived

        db.flush()

        return section

    @staticmethod
    def delete(
        db: Session,
        *,
        section: Section,
    ) -> None:
        db.delete(
            section,
        )
        db.flush()

    @staticmethod
    def _apply_archived_filters(
        query,
        *,
        company_id: int | None,
        search: str | None,
    ):
        if company_id is not None:
            query = query.where(
                Section.company_id == company_id,
            )

        if search:
            pattern = (
                f"%{search.strip()}%"
            )

            query = query.where(
                or_(
                    Section.name.ilike(
                        pattern,
                    ),
                    Section.description.ilike(
                        pattern,
                    ),
                    Company.name.ilike(
                        pattern,
                    ),
                ),
            )

        return query