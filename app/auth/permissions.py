from sqlalchemy.orm import Session

from app.core.constants import CompanyRole
from app.models.company import Company
from app.models.section import Section
from app.models.user import User
from app.repositories.company_membership_repository import (
    CompanyMembershipRepository,
)
from app.repositories.section_membership_repository import (
    SectionMembershipRepository,
)


class PermissionDeniedError(PermissionError):
    """Raised when an actor is not permitted to perform an operation."""


class PermissionService:
    @staticmethod
    def is_administrator(
        actor: User,
    ) -> bool:
        return (
            actor.can_authenticate
            and actor.is_administrator
        )

    @staticmethod
    def is_company_member(
        db: Session,
        *,
        actor: User,
        company: Company,
    ) -> bool:
        if not actor.can_authenticate:
            return False

        return CompanyMembershipRepository.exists(
            db,
            company_id=company.id,
            user_id=actor.id,
        )

    @staticmethod
    def is_company_manager(
        db: Session,
        *,
        actor: User,
        company: Company,
    ) -> bool:
        if not actor.can_authenticate:
            return False

        membership = (
            CompanyMembershipRepository.get_by_company_and_user(
                db,
                company_id=company.id,
                user_id=actor.id,
            )
        )

        return (
            membership is not None
            and membership.role == CompanyRole.MANAGER.value
        )

    @staticmethod
    def is_section_creator(
        *,
        actor: User,
        section: Section,
    ) -> bool:
        return (
            actor.can_authenticate
            and section.created_by_user_id == actor.id
        )

    @staticmethod
    def is_section_member(
        db: Session,
        *,
        actor: User,
        section: Section,
    ) -> bool:
        if not actor.can_authenticate:
            return False

        return SectionMembershipRepository.exists(
            db,
            section_id=section.id,
            user_id=actor.id,
        )

    @staticmethod
    def can_view_company(
        db: Session,
        *,
        actor: User,
        company: Company,
    ) -> bool:
        if PermissionService.is_administrator(
            actor,
        ):
            return True

        return PermissionService.is_company_member(
            db,
            actor=actor,
            company=company,
        )

    @staticmethod
    def can_create_company(
        *,
        actor: User,
    ) -> bool:
        return PermissionService.is_administrator(
            actor,
        )

    @staticmethod
    def can_manage_company(
        *,
        actor: User,
        company: Company,
    ) -> bool:
        del company

        return PermissionService.is_administrator(
            actor,
        )

    @staticmethod
    def can_manage_company_memberships(
        db: Session,
        *,
        actor: User,
        company: Company,
    ) -> bool:
        if PermissionService.is_administrator(
            actor,
        ):
            return True

        return PermissionService.is_company_manager(
            db,
            actor=actor,
            company=company,
        )

    @staticmethod
    def can_create_section(
        db: Session,
        *,
        actor: User,
        company: Company,
    ) -> bool:
        if not actor.can_authenticate:
            return False

        if company.is_archived:
            return False

        if PermissionService.is_administrator(
            actor,
        ):
            return True

        return PermissionService.is_company_manager(
            db,
            actor=actor,
            company=company,
        )

    @staticmethod
    def can_view_section(
        db: Session,
        *,
        actor: User,
        section: Section,
    ) -> bool:
        if not actor.can_authenticate:
            return False

        if PermissionService.is_administrator(
            actor,
        ):
            return True

        if PermissionService.is_section_creator(
            actor=actor,
            section=section,
        ):
            return True

        return PermissionService.is_section_member(
            db,
            actor=actor,
            section=section,
        )

    @staticmethod
    def can_manage_section(
        db: Session,
        *,
        actor: User,
        section: Section,
    ) -> bool:
        del db

        if PermissionService.is_administrator(
            actor,
        ):
            return True

        return PermissionService.is_section_creator(
            actor=actor,
            section=section,
        )

    @staticmethod
    def can_manage_section_memberships(
        db: Session,
        *,
        actor: User,
        section: Section,
    ) -> bool:
        return PermissionService.can_manage_section(
            db,
            actor=actor,
            section=section,
        )

    @staticmethod
    def require_company_access(
        db: Session,
        *,
        actor: User,
        company: Company,
    ) -> None:
        if not PermissionService.can_view_company(
            db,
            actor=actor,
            company=company,
        ):
            raise PermissionDeniedError(
                "You do not have access to this company.",
            )

    @staticmethod
    def require_company_creation(
        *,
        actor: User,
    ) -> None:
        if not PermissionService.can_create_company(
            actor=actor,
        ):
            raise PermissionDeniedError(
                "Only administrators can create companies.",
            )

    @staticmethod
    def require_company_management(
        *,
        actor: User,
        company: Company,
    ) -> None:
        if not PermissionService.can_manage_company(
            actor=actor,
            company=company,
        ):
            raise PermissionDeniedError(
                "Only administrators can manage companies.",
            )

    @staticmethod
    def require_company_membership_management(
        db: Session,
        *,
        actor: User,
        company: Company,
    ) -> None:
        if not PermissionService.can_manage_company_memberships(
            db,
            actor=actor,
            company=company,
        ):
            raise PermissionDeniedError(
                "You do not have permission to manage this company's members.",
            )

    @staticmethod
    def require_section_creation(
        db: Session,
        *,
        actor: User,
        company: Company,
    ) -> None:
        if not PermissionService.can_create_section(
            db,
            actor=actor,
            company=company,
        ):
            raise PermissionDeniedError(
                "You do not have permission to create sections in this company.",
            )

    @staticmethod
    def require_section_access(
        db: Session,
        *,
        actor: User,
        section: Section,
    ) -> None:
        if not PermissionService.can_view_section(
            db,
            actor=actor,
            section=section,
        ):
            raise PermissionDeniedError(
                "You do not have access to this section.",
            )

    @staticmethod
    def require_section_management(
        db: Session,
        *,
        actor: User,
        section: Section,
    ) -> None:
        if not PermissionService.can_manage_section(
            db,
            actor=actor,
            section=section,
        ):
            raise PermissionDeniedError(
                "You do not have permission to manage this section.",
            )

    @staticmethod
    def require_section_membership_management(
        db: Session,
        *,
        actor: User,
        section: Section,
    ) -> None:
        if not PermissionService.can_manage_section_memberships(
            db,
            actor=actor,
            section=section,
        ):
            raise PermissionDeniedError(
                "You do not have permission to manage this section's members.",
            )