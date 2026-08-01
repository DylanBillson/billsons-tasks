from sqlalchemy.orm import Session

from app.core.constants import AuditAction, CompanyRole
from app.models.company import Company
from app.models.company_membership import CompanyMembership
from app.models.user import User
from app.repositories.company_membership_repository import (
    CompanyMembershipRepository,
)
from app.repositories.company_repository import CompanyRepository
from app.repositories.user_repository import UserRepository
from app.schemas.company import (
    CompanyMembershipCreateRequest,
    CompanyMembershipUpdateRequest,
)
from app.services.audit_service import AuditService
from app.auth.permissions import PermissionService


class CompanyMembershipServiceError(ValueError):
    """Base exception for company-membership service failures."""


class CompanyMembershipNotFoundError(
    CompanyMembershipServiceError,
):
    """Raised when a company membership cannot be found."""


class CompanyMembershipAlreadyExistsError(
    CompanyMembershipServiceError,
):
    """Raised when a user already belongs to a company."""


class CompanyMembershipUserNotFoundError(
    CompanyMembershipServiceError,
):
    """Raised when the target user cannot be found."""


class CompanyMembershipUserUnavailableError(
    CompanyMembershipServiceError,
):
    """Raised when the target user cannot receive memberships."""


class CompanyMembershipService:
    @staticmethod
    def get_membership(
        db: Session,
        *,
        company_id: int,
        user_id: int,
    ) -> CompanyMembership | None:
        return (
            CompanyMembershipRepository.get_by_company_and_user(
                db,
                company_id=company_id,
                user_id=user_id,
            )
        )

    @staticmethod
    def require_membership(
        db: Session,
        *,
        company_id: int,
        user_id: int,
    ) -> CompanyMembership:
        membership = CompanyMembershipService.get_membership(
            db,
            company_id=company_id,
            user_id=user_id,
        )

        if membership is None:
            raise CompanyMembershipNotFoundError(
                "Company membership was not found.",
            )

        return membership

    @staticmethod
    def list_memberships(
        db: Session,
        *,
        actor: User,
        company: Company,
    ) -> list[CompanyMembership]:
        PermissionService.require_company_membership_management(
            db,
            actor=actor,
            company=company,
        )

        return CompanyMembershipRepository.list_for_company(
            db,
            company_id=company.id,
        )

    @staticmethod
    def list_memberships_by_company_id(
        db: Session,
        *,
        actor: User,
        company_id: int,
    ) -> list[CompanyMembership]:
        company = CompanyRepository.get_by_id(
            db,
            company_id,
        )

        if company is None:
            raise CompanyMembershipServiceError(
                "Company was not found.",
            )

        return CompanyMembershipService.list_memberships(
            db,
            actor=actor,
            company=company,
        )

    @staticmethod
    def add_member(
        db: Session,
        *,
        actor: User,
        company: Company,
        membership_create: CompanyMembershipCreateRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> CompanyMembership:
        PermissionService.require_company_membership_management(
            db,
            actor=actor,
            company=company,
        )

        if company.is_archived:
            raise CompanyMembershipServiceError(
                "Members cannot be added to an archived company.",
            )

        target_user = UserRepository.get_by_id(
            db,
            user_id=membership_create.user_id,
        )

        if target_user is None:
            raise CompanyMembershipUserNotFoundError(
                "The selected user could not be found.",
            )

        if not target_user.can_authenticate:
            raise CompanyMembershipUserUnavailableError(
                "The selected user account is not available.",
            )

        existing_membership = (
            CompanyMembershipRepository.get_by_company_and_user(
                db,
                company_id=company.id,
                user_id=target_user.id,
            )
        )

        if existing_membership is not None:
            raise CompanyMembershipAlreadyExistsError(
                "The selected user already belongs to this company.",
            )

        membership = CompanyMembershipRepository.create(
            db,
            company_id=company.id,
            user_id=target_user.id,
            role=membership_create.role.value,
        )

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.COMPANY_MEMBER_ADDED,
            summary=(
                f"{actor.display_name} added "
                f"{target_user.display_name} to {company.name}."
            ),
            entity_type="company_membership",
            entity_id=membership.id,
            metadata_json={
                "company_id": company.id,
                "company_name": company.name,
                "user_id": target_user.id,
                "username": target_user.username,
                "role": membership.role,
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
    def add_member_by_company_id(
        db: Session,
        *,
        actor: User,
        company_id: int,
        membership_create: CompanyMembershipCreateRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> CompanyMembership:
        company = CompanyRepository.get_by_id(
            db,
            company_id,
        )

        if company is None:
            raise CompanyMembershipServiceError(
                "Company was not found.",
            )

        return CompanyMembershipService.add_member(
            db,
            actor=actor,
            company=company,
            membership_create=membership_create,
            ip_address=ip_address,
            user_agent=user_agent,
            commit=commit,
        )

    @staticmethod
    def update_role(
        db: Session,
        *,
        actor: User,
        membership: CompanyMembership,
        membership_update: CompanyMembershipUpdateRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> CompanyMembership:
        PermissionService.require_company_membership_management(
            db,
            actor=actor,
            company=membership.company,
        )

        new_role = membership_update.role.value

        if membership.role == new_role:
            return membership

        previous_role = membership.role

        CompanyMembershipRepository.update_role(
            db,
            membership=membership,
            role=new_role,
        )

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.COMPANY_MEMBER_UPDATED,
            summary=(
                f"{actor.display_name} changed "
                f"{membership.user.display_name}'s role in "
                f"{membership.company.name} from "
                f"{previous_role} to {new_role}."
            ),
            entity_type="company_membership",
            entity_id=membership.id,
            metadata_json={
                "company_id": membership.company_id,
                "company_name": membership.company.name,
                "user_id": membership.user_id,
                "username": membership.user.username,
                "previous_role": previous_role,
                "new_role": new_role,
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
    def update_role_by_company_and_user(
        db: Session,
        *,
        actor: User,
        company_id: int,
        user_id: int,
        membership_update: CompanyMembershipUpdateRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> CompanyMembership:
        membership = CompanyMembershipService.require_membership(
            db,
            company_id=company_id,
            user_id=user_id,
        )

        return CompanyMembershipService.update_role(
            db,
            actor=actor,
            membership=membership,
            membership_update=membership_update,
            ip_address=ip_address,
            user_agent=user_agent,
            commit=commit,
        )

    @staticmethod
    def remove_member(
        db: Session,
        *,
        actor: User,
        membership: CompanyMembership,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> None:
        company = membership.company
        target_user = membership.user

        PermissionService.require_company_membership_management(
            db,
            actor=actor,
            company=company,
        )

        CompanyMembershipRepository.delete(
            db,
            membership=membership,
        )

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.COMPANY_MEMBER_REMOVED,
            summary=(
                f"{actor.display_name} removed "
                f"{target_user.display_name} from {company.name}."
            ),
            entity_type="company",
            entity_id=company.id,
            metadata_json={
                "company_id": company.id,
                "company_name": company.name,
                "user_id": target_user.id,
                "username": target_user.username,
                "removed_role": membership.role,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()

    @staticmethod
    def remove_member_by_company_and_user(
        db: Session,
        *,
        actor: User,
        company_id: int,
        user_id: int,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> None:
        membership = CompanyMembershipService.require_membership(
            db,
            company_id=company_id,
            user_id=user_id,
        )

        CompanyMembershipService.remove_member(
            db,
            actor=actor,
            membership=membership,
            ip_address=ip_address,
            user_agent=user_agent,
            commit=commit,
        )

    @staticmethod
    def is_company_manager(
        db: Session,
        *,
        company_id: int,
        user_id: int,
    ) -> bool:
        membership = CompanyMembershipService.get_membership(
            db,
            company_id=company_id,
            user_id=user_id,
        )

        return (
            membership is not None
            and membership.role == CompanyRole.MANAGER.value
        )