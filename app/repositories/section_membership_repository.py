from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.section_membership import SectionMembership


class SectionMembershipRepository:
    @staticmethod
    def get_by_id(
        db: Session,
        membership_id: int,
    ) -> SectionMembership | None:
        query = (
            select(SectionMembership)
            .options(
                joinedload(SectionMembership.section),
                joinedload(SectionMembership.user),
            )
            .where(
                SectionMembership.id == membership_id,
            )
        )

        return db.scalar(
            query,
        )

    @staticmethod
    def get_by_section_and_user(
        db: Session,
        *,
        section_id: int,
        user_id: int,
    ) -> SectionMembership | None:
        query = (
            select(SectionMembership)
            .options(
                joinedload(SectionMembership.section),
                joinedload(SectionMembership.user),
            )
            .where(
                SectionMembership.section_id == section_id,
                SectionMembership.user_id == user_id,
            )
        )

        return db.scalar(
            query,
        )

    @staticmethod
    def list_for_section(
        db: Session,
        *,
        section_id: int,
    ) -> list[SectionMembership]:
        query = (
            select(SectionMembership)
            .options(
                joinedload(SectionMembership.user),
            )
            .where(
                SectionMembership.section_id == section_id,
            )
            .order_by(
                SectionMembership.user_id.asc(),
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
    ) -> list[SectionMembership]:
        query = (
            select(SectionMembership)
            .options(
                joinedload(SectionMembership.section),
            )
            .where(
                SectionMembership.user_id == user_id,
            )
            .order_by(
                SectionMembership.section_id.asc(),
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
        section_id: int,
        user_id: int,
    ) -> SectionMembership:
        membership = SectionMembership(
            section_id=section_id,
            user_id=user_id,
        )

        db.add(
            membership,
        )
        db.flush()

        return membership

    @staticmethod
    def delete(
        db: Session,
        *,
        membership: SectionMembership,
    ) -> None:
        db.delete(
            membership,
        )
        db.flush()

    @staticmethod
    def exists(
        db: Session,
        *,
        section_id: int,
        user_id: int,
    ) -> bool:
        query = (
            select(SectionMembership.id)
            .where(
                SectionMembership.section_id == section_id,
                SectionMembership.user_id == user_id,
            )
            .limit(1)
        )

        return db.scalar(
            query,
        ) is not None