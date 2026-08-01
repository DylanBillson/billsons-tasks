from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.company import Company
from app.models.company_membership import CompanyMembership


class CompanyRepository:
    @staticmethod
    def get_by_id(
        db: Session,
        company_id: int,
    ) -> Company | None:
        query = (
            select(Company)
            .options(
                selectinload(Company.memberships),
                selectinload(Company.sections),
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
                selectinload(Company.memberships),
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
                CompanyMembership.company_id == Company.id,
            )
            .options(
                selectinload(Company.memberships),
            )
            .where(
                CompanyMembership.user_id == user_id,
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