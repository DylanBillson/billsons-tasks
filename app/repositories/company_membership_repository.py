from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.company_membership import CompanyMembership


class CompanyMembershipRepository:
    @staticmethod
    def get_by_id(
        db: Session,
        membership_id: int,
    ) -> CompanyMembership | None:
        query = (
            select(CompanyMembership)
            .options(
                joinedload(CompanyMembership.company),
                joinedload(CompanyMembership.user),
            )
            .where(
                CompanyMembership.id == membership_id,
            )
        )

        return db.scalar(
            query,
        )

    @staticmethod
    def get_by_company_and_user(
        db: Session,
        *,
        company_id: int,
        user_id: int,
    ) -> CompanyMembership | None:
        query = (
            select(CompanyMembership)
            .options(
                joinedload(CompanyMembership.company),
                joinedload(CompanyMembership.user),
            )
            .where(
                CompanyMembership.company_id == company_id,
                CompanyMembership.user_id == user_id,
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
    ) -> list[CompanyMembership]:
        query = (
            select(CompanyMembership)
            .options(
                joinedload(CompanyMembership.user),
            )
            .where(
                CompanyMembership.company_id == company_id,
            )
            .order_by(
                CompanyMembership.role.asc(),
                CompanyMembership.user_id.asc(),
            )
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
    ) -> list[CompanyMembership]:
        query = (
            select(CompanyMembership)
            .options(
                joinedload(CompanyMembership.company),
            )
            .where(
                CompanyMembership.user_id == user_id,
            )
            .order_by(
                CompanyMembership.company_id.asc(),
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
        company_id: int,
        user_id: int,
        role: str,
    ) -> CompanyMembership:
        membership = CompanyMembership(
            company_id=company_id,
            user_id=user_id,
            role=role,
        )

        db.add(
            membership,
        )
        db.flush()

        return membership

    @staticmethod
    def update_role(
        db: Session,
        *,
        membership: CompanyMembership,
        role: str,
    ) -> CompanyMembership:
        membership.role = role

        db.flush()

        return membership

    @staticmethod
    def delete(
        db: Session,
        *,
        membership: CompanyMembership,
    ) -> None:
        db.delete(
            membership,
        )
        db.flush()

    @staticmethod
    def exists(
        db: Session,
        *,
        company_id: int,
        user_id: int,
    ) -> bool:
        query = (
            select(CompanyMembership.id)
            .where(
                CompanyMembership.company_id == company_id,
                CompanyMembership.user_id == user_id,
            )
            .limit(1)
        )

        return db.scalar(
            query,
        ) is not None