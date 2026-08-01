from sqlalchemy.orm import Session

from app.core.constants import AuditAction
from app.models.company import Company
from app.models.section import Section
from app.models.user import User
from app.repositories.company_repository import CompanyRepository
from app.repositories.section_repository import SectionRepository
from app.schemas.section import (
    SectionCreateRequest,
    SectionUpdateRequest,
)
from app.services.audit_service import AuditService
from app.auth.permissions import PermissionService


class SectionServiceError(ValueError):
    """Base exception for section-service failures."""


class SectionNotFoundError(SectionServiceError):
    """Raised when a section cannot be found."""


class SectionNameAlreadyExistsError(SectionServiceError):
    """Raised when a company already has a section with the same name."""


class SectionCompanyNotFoundError(SectionServiceError):
    """Raised when the requested parent company cannot be found."""


class SectionService:
    @staticmethod
    def get_section(
        db: Session,
        *,
        section_id: int,
    ) -> Section | None:
        return SectionRepository.get_by_id(
            db,
            section_id,
        )

    @staticmethod
    def require_section(
        db: Session,
        *,
        section_id: int,
    ) -> Section:
        section = SectionService.get_section(
            db,
            section_id=section_id,
        )

        if section is None:
            raise SectionNotFoundError(
                "Section was not found.",
            )

        return section

    @staticmethod
    def get_accessible_section(
        db: Session,
        *,
        actor: User,
        section_id: int,
    ) -> Section:
        section = SectionService.require_section(
            db,
            section_id=section_id,
        )

        PermissionService.require_section_access(
            db,
            actor=actor,
            section=section,
        )

        return section

    @staticmethod
    def list_accessible_sections(
        db: Session,
        *,
        actor: User,
        company_id: int | None = None,
        include_archived: bool = False,
    ) -> list[Section]:
        if actor.is_administrator:
            if company_id is not None:
                return SectionRepository.list_for_company(
                    db,
                    company_id=company_id,
                    include_archived=include_archived,
                )

            companies = CompanyRepository.list_all(
                db,
                include_archived=True,
            )

            sections: list[Section] = []

            for company in companies:
                sections.extend(
                    SectionRepository.list_for_company(
                        db,
                        company_id=company.id,
                        include_archived=include_archived,
                    ),
                )

            return sections

        return SectionRepository.list_accessible_to_user(
            db,
            user_id=actor.id,
            company_id=company_id,
            include_archived=include_archived,
        )

    @staticmethod
    def create_section(
        db: Session,
        *,
        actor: User,
        company: Company,
        section_create: SectionCreateRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> Section:
        PermissionService.require_section_creation(
            db,
            actor=actor,
            company=company,
        )

        if company.is_archived:
            raise SectionServiceError(
                "Sections cannot be created in an archived company.",
            )

        existing_section = (
            SectionRepository.get_by_company_and_name(
                db,
                company_id=company.id,
                name=section_create.name,
            )
        )

        if existing_section is not None:
            raise SectionNameAlreadyExistsError(
                "A section with this name already exists in the company.",
            )

        section = SectionRepository.create(
            db,
            company_id=company.id,
            created_by_user_id=actor.id,
            name=section_create.name,
            description=section_create.description,
        )

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.SECTION_CREATED,
            summary=(
                f"{actor.display_name} created "
                f"{section.name} in {company.name}."
            ),
            entity_type="section",
            entity_id=section.id,
            metadata_json={
                "company_id": company.id,
                "company_name": company.name,
                "name": section.name,
                "description": section.description,
                "created_by_user_id": actor.id,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()
            db.refresh(
                section,
            )

        return section

    @staticmethod
    def create_section_by_company_id(
        db: Session,
        *,
        actor: User,
        company_id: int,
        section_create: SectionCreateRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> Section:
        company = CompanyRepository.get_by_id(
            db,
            company_id,
        )

        if company is None:
            raise SectionCompanyNotFoundError(
                "Company was not found.",
            )

        return SectionService.create_section(
            db,
            actor=actor,
            company=company,
            section_create=section_create,
            ip_address=ip_address,
            user_agent=user_agent,
            commit=commit,
        )

    @staticmethod
    def update_section(
        db: Session,
        *,
        actor: User,
        section: Section,
        section_update: SectionUpdateRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> Section:
        PermissionService.require_section_management(
            db,
            actor=actor,
            section=section,
        )

        existing_section = (
            SectionRepository.get_by_company_and_name(
                db,
                company_id=section.company_id,
                name=section_update.name,
            )
        )

        if (
            existing_section is not None
            and existing_section.id != section.id
        ):
            raise SectionNameAlreadyExistsError(
                "A section with this name already exists in the company.",
            )

        previous_name = section.name
        previous_description = section.description

        SectionRepository.update(
            db,
            section=section,
            name=section_update.name,
            description=section_update.description,
        )

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.SECTION_UPDATED,
            summary=(
                f"{actor.display_name} updated {section.name}."
            ),
            entity_type="section",
            entity_id=section.id,
            metadata_json={
                "company_id": section.company_id,
                "previous_name": previous_name,
                "name": section.name,
                "previous_description": previous_description,
                "description": section.description,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()
            db.refresh(
                section,
            )

        return section

    @staticmethod
    def update_section_by_id(
        db: Session,
        *,
        actor: User,
        section_id: int,
        section_update: SectionUpdateRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> Section:
        section = SectionService.require_section(
            db,
            section_id=section_id,
        )

        return SectionService.update_section(
            db,
            actor=actor,
            section=section,
            section_update=section_update,
            ip_address=ip_address,
            user_agent=user_agent,
            commit=commit,
        )

    @staticmethod
    def set_archived_status(
        db: Session,
        *,
        actor: User,
        section: Section,
        is_archived: bool,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> Section:
        PermissionService.require_section_management(
            db,
            actor=actor,
            section=section,
        )

        if section.is_archived == is_archived:
            return section

        SectionRepository.set_archived(
            db,
            section=section,
            is_archived=is_archived,
        )

        action = (
            AuditAction.SECTION_ARCHIVED
            if is_archived
            else AuditAction.SECTION_RESTORED
        )

        verb = (
            "archived"
            if is_archived
            else "restored"
        )

        AuditService.record(
            db,
            user=actor,
            action=action,
            summary=(
                f"{actor.display_name} {verb} {section.name}."
            ),
            entity_type="section",
            entity_id=section.id,
            metadata_json={
                "company_id": section.company_id,
                "name": section.name,
                "is_archived": is_archived,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()
            db.refresh(
                section,
            )

        return section

    @staticmethod
    def set_archived_status_by_id(
        db: Session,
        *,
        actor: User,
        section_id: int,
        is_archived: bool,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> Section:
        section = SectionService.require_section(
            db,
            section_id=section_id,
        )

        return SectionService.set_archived_status(
            db,
            actor=actor,
            section=section,
            is_archived=is_archived,
            ip_address=ip_address,
            user_agent=user_agent,
            commit=commit,
        )

    @staticmethod
    def delete_section(
        db: Session,
        *,
        actor: User,
        section: Section,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> None:
        PermissionService.require_section_management(
            db,
            actor=actor,
            section=section,
        )

        section_id = section.id
        section_name = section.name
        company_id = section.company_id

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.SECTION_DELETED,
            summary=(
                f"{actor.display_name} deleted {section_name}."
            ),
            entity_type="section",
            entity_id=section_id,
            metadata_json={
                "company_id": company_id,
                "name": section_name,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        SectionRepository.delete(
            db,
            section=section,
        )

        if commit:
            db.commit()