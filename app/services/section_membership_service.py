from sqlalchemy.orm import Session

from app.core.constants import AuditAction
from app.models.section import Section
from app.models.section_membership import SectionMembership
from app.models.user import User
from app.repositories.company_membership_repository import (
    CompanyMembershipRepository,
)
from app.repositories.section_membership_repository import (
    SectionMembershipRepository,
)
from app.repositories.section_repository import SectionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.section import SectionMembershipCreateRequest
from app.services.audit_service import AuditService
from app.auth.permissions import PermissionService


class SectionMembershipServiceError(ValueError):
    """Base exception for section-membership failures."""


class SectionMembershipNotFoundError(
    SectionMembershipServiceError,
):
    """Raised when a section membership cannot be found."""


class SectionMembershipAlreadyExistsError(
    SectionMembershipServiceError,
):
    """Raised when a user is already assigned to a section."""


class SectionMembershipUserNotFoundError(
    SectionMembershipServiceError,
):
    """Raised when the selected user cannot be found."""


class SectionMembershipUserUnavailableError(
    SectionMembershipServiceError,
):
    """Raised when the selected user cannot receive an assignment."""


class SectionCompanyMembershipRequiredError(
    SectionMembershipServiceError,
):
    """Raised when the user is not a member of the parent company."""


class SectionMembershipService:
    @staticmethod
    def get_membership(
        db: Session,
        *,
        section_id: int,
        user_id: int,
    ) -> SectionMembership | None:
        return (
            SectionMembershipRepository.get_by_section_and_user(
                db,
                section_id=section_id,
                user_id=user_id,
            )
        )

    @staticmethod
    def require_membership(
        db: Session,
        *,
        section_id: int,
        user_id: int,
    ) -> SectionMembership:
        membership = SectionMembershipService.get_membership(
            db,
            section_id=section_id,
            user_id=user_id,
        )

        if membership is None:
            raise SectionMembershipNotFoundError(
                "Section membership was not found.",
            )

        return membership

    @staticmethod
    def list_memberships(
        db: Session,
        *,
        actor: User,
        section: Section,
    ) -> list[SectionMembership]:
        PermissionService.require_section_membership_management(
            db,
            actor=actor,
            section=section,
        )

        return SectionMembershipRepository.list_for_section(
            db,
            section_id=section.id,
        )

    @staticmethod
    def assign_user(
        db: Session,
        *,
        actor: User,
        section: Section,
        membership_create: SectionMembershipCreateRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> SectionMembership:
        PermissionService.require_section_membership_management(
            db,
            actor=actor,
            section=section,
        )

        if section.is_archived:
            raise SectionMembershipServiceError(
                "Users cannot be assigned to an archived section.",
            )

        target_user = UserRepository.get_by_id(
            db,
            user_id=membership_create.user_id,
        )

        if target_user is None:
            raise SectionMembershipUserNotFoundError(
                "The selected user could not be found.",
            )

        if not target_user.can_authenticate:
            raise SectionMembershipUserUnavailableError(
                "The selected user account is not available.",
            )

        company_membership = (
            CompanyMembershipRepository.get_by_company_and_user(
                db,
                company_id=section.company_id,
                user_id=target_user.id,
            )
        )

        if company_membership is None:
            raise SectionCompanyMembershipRequiredError(
                "The selected user must belong to the section's company.",
            )

        existing_membership = (
            SectionMembershipRepository.get_by_section_and_user(
                db,
                section_id=section.id,
                user_id=target_user.id,
            )
        )

        if existing_membership is not None:
            raise SectionMembershipAlreadyExistsError(
                "The selected user is already assigned to this section.",
            )

        membership = SectionMembershipRepository.create(
            db,
            section_id=section.id,
            user_id=target_user.id,
        )

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.SECTION_MEMBER_ADDED,
            summary=(
                f"{actor.display_name} assigned "
                f"{target_user.display_name} to {section.name}."
            ),
            entity_type="section_membership",
            entity_id=membership.id,
            metadata_json={
                "section_id": section.id,
                "section_name": section.name,
                "company_id": section.company_id,
                "user_id": target_user.id,
                "username": target_user.username,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()
            db.refresh(
                membership,
            )

        return membership

    @staticmethod
    def assign_user_by_section_id(
        db: Session,
        *,
        actor: User,
        section_id: int,
        membership_create: SectionMembershipCreateRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> SectionMembership:
        section = SectionRepository.get_by_id(
            db,
            section_id,
        )

        if section is None:
            raise SectionMembershipServiceError(
                "Section was not found.",
            )

        return SectionMembershipService.assign_user(
            db,
            actor=actor,
            section=section,
            membership_create=membership_create,
            ip_address=ip_address,
            user_agent=user_agent,
            commit=commit,
        )

    @staticmethod
    def remove_user(
        db: Session,
        *,
        actor: User,
        membership: SectionMembership,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> None:
        section = membership.section
        target_user = membership.user

        PermissionService.require_section_membership_management(
            db,
            actor=actor,
            section=section,
        )

        SectionMembershipRepository.delete(
            db,
            membership=membership,
        )

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.SECTION_MEMBER_REMOVED,
            summary=(
                f"{actor.display_name} removed "
                f"{target_user.display_name} from {section.name}."
            ),
            entity_type="section",
            entity_id=section.id,
            metadata_json={
                "section_id": section.id,
                "section_name": section.name,
                "company_id": section.company_id,
                "user_id": target_user.id,
                "username": target_user.username,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()

    @staticmethod
    def remove_user_by_section_and_user(
        db: Session,
        *,
        actor: User,
        section_id: int,
        user_id: int,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> None:
        membership = SectionMembershipService.require_membership(
            db,
            section_id=section_id,
            user_id=user_id,
        )

        SectionMembershipService.remove_user(
            db,
            actor=actor,
            membership=membership,
            ip_address=ip_address,
            user_agent=user_agent,
            commit=commit,
        )