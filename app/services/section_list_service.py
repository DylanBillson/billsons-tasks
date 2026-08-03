from sqlalchemy.orm import Session

from app.auth.permissions import PermissionService
from app.core.constants import AuditAction
from app.models.section import Section
from app.models.section_list import SectionList
from app.models.user import User
from app.repositories.section_list_repository import (
    SectionListRepository,
)
from app.schemas.section_list import (
    SectionListCreateRequest,
    SectionListReorderRequest,
    SectionListUpdateRequest,
)
from app.services.audit_service import AuditService
from app.services.section_service import SectionService


class SectionListServiceError(ValueError):
    """Base exception for section-list failures."""


class SectionListNotFoundError(SectionListServiceError):
    """Raised when a section list cannot be found."""


class SectionListNameAlreadyExistsError(
    SectionListServiceError,
):
    """Raised when a section already contains a list with the same name."""


class SectionListReorderError(SectionListServiceError):
    """Raised when a list reorder request is invalid."""


class SectionListNotEmptyError(SectionListServiceError):
    """Raised when a non-empty list cannot be permanently deleted."""


class SectionListService:
    SORT_INCREMENT = 1000

    @staticmethod
    def get_list(
        db: Session,
        *,
        section_list_id: int,
    ) -> SectionList | None:
        return SectionListRepository.get_by_id(
            db,
            section_list_id=section_list_id,
        )

    @staticmethod
    def require_list(
        db: Session,
        *,
        section_list_id: int,
    ) -> SectionList:
        section_list = SectionListService.get_list(
            db,
            section_list_id=section_list_id,
        )

        if section_list is None:
            raise SectionListNotFoundError(
                "List was not found.",
            )

        return section_list

    @staticmethod
    def get_accessible_list(
        db: Session,
        *,
        actor: User,
        section_list_id: int,
    ) -> SectionList:
        section_list = SectionListService.require_list(
            db,
            section_list_id=section_list_id,
        )

        PermissionService.require_section_list_access(
            db,
            actor=actor,
            section_list=section_list,
        )

        return section_list

    @staticmethod
    def list_for_section(
        db: Session,
        *,
        actor: User,
        section: Section,
        include_archived: bool = False,
        include_tasks: bool = False,
    ) -> list[SectionList]:
        PermissionService.require_section_access(
            db,
            actor=actor,
            section=section,
        )

        return SectionListRepository.list_for_section(
            db,
            section_id=section.id,
            include_archived=include_archived,
            include_tasks=include_tasks,
        )

    @staticmethod
    def list_for_section_id(
        db: Session,
        *,
        actor: User,
        section_id: int,
        include_archived: bool = False,
        include_tasks: bool = False,
    ) -> list[SectionList]:
        section = SectionService.require_section(
            db,
            section_id=section_id,
        )

        return SectionListService.list_for_section(
            db,
            actor=actor,
            section=section,
            include_archived=include_archived,
            include_tasks=include_tasks,
        )

    @staticmethod
    def create_list(
        db: Session,
        *,
        actor: User,
        section: Section,
        section_list_create: SectionListCreateRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> SectionList:
        PermissionService.require_section_list_creation(
            db,
            actor=actor,
            section=section,
        )

        existing = (
            SectionListRepository.get_by_section_and_name(
                db,
                section_id=section.id,
                name=section_list_create.name,
            )
        )

        if existing is not None:
            raise SectionListNameAlreadyExistsError(
                "A list with this name already exists in the section.",
            )

        section_list = SectionListRepository.create(
            db,
            section_id=section.id,
            name=section_list_create.name,
            description=section_list_create.description,
        )

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.LIST_CREATED,
            summary=(
                f"{actor.display_name} created "
                f"{section_list.name} in {section.name}."
            ),
            entity_type="section_list",
            entity_id=section_list.id,
            metadata_json={
                "company_id": section.company_id,
                "section_id": section.id,
                "name": section_list.name,
                "description": section_list.description,
                "sort_position": section_list.sort_position,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()
            db.refresh(
                section_list,
            )

        return section_list

    @staticmethod
    def create_list_by_section_id(
        db: Session,
        *,
        actor: User,
        section_id: int,
        section_list_create: SectionListCreateRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> SectionList:
        section = SectionService.require_section(
            db,
            section_id=section_id,
        )

        return SectionListService.create_list(
            db,
            actor=actor,
            section=section,
            section_list_create=section_list_create,
            ip_address=ip_address,
            user_agent=user_agent,
            commit=commit,
        )

    @staticmethod
    def update_list(
        db: Session,
        *,
        actor: User,
        section_list: SectionList,
        section_list_update: SectionListUpdateRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> SectionList:
        PermissionService.require_section_list_management(
            db,
            actor=actor,
            section_list=section_list,
        )

        existing = (
            SectionListRepository.get_by_section_and_name(
                db,
                section_id=section_list.section_id,
                name=section_list_update.name,
            )
        )

        if (
            existing is not None
            and existing.id != section_list.id
        ):
            raise SectionListNameAlreadyExistsError(
                "A list with this name already exists in the section.",
            )

        previous_name = section_list.name
        previous_description = section_list.description

        SectionListRepository.update(
            db,
            section_list=section_list,
            name=section_list_update.name,
            description=section_list_update.description,
        )

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.LIST_UPDATED,
            summary=(
                f"{actor.display_name} updated "
                f"{section_list.name}."
            ),
            entity_type="section_list",
            entity_id=section_list.id,
            metadata_json={
                "section_id": section_list.section_id,
                "previous_name": previous_name,
                "name": section_list.name,
                "previous_description": previous_description,
                "description": section_list.description,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()
            db.refresh(
                section_list,
            )

        return section_list

    @staticmethod
    def set_archived_status(
        db: Session,
        *,
        actor: User,
        section_list: SectionList,
        is_archived: bool,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> SectionList:
        PermissionService.require_section_list_management(
            db,
            actor=actor,
            section_list=section_list,
        )

        if section_list.is_archived == is_archived:
            return section_list

        SectionListRepository.set_archived(
            db,
            section_list=section_list,
            is_archived=is_archived,
        )

        action = (
            AuditAction.LIST_ARCHIVED
            if is_archived
            else AuditAction.LIST_RESTORED
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
                f"{actor.display_name} {verb} "
                f"{section_list.name}."
            ),
            entity_type="section_list",
            entity_id=section_list.id,
            metadata_json={
                "section_id": section_list.section_id,
                "name": section_list.name,
                "is_archived": is_archived,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()
            db.refresh(
                section_list,
            )

        return section_list

    @staticmethod
    def reorder_lists(
        db: Session,
        *,
        actor: User,
        section: Section,
        reorder_request: SectionListReorderRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> list[SectionList]:
        PermissionService.require_section_list_reordering(
            db,
            actor=actor,
            section=section,
        )

        submitted_ids = {
            item.list_id
            for item in reorder_request.items
        }

        section_lists = (
            SectionListRepository.list_for_section(
                db,
                section_id=section.id,
                include_archived=True,
            )
        )

        list_by_id = {
            section_list.id: section_list
            for section_list in section_lists
        }

        missing_ids = submitted_ids - set(
            list_by_id,
        )

        if missing_ids:
            raise SectionListReorderError(
                "The reorder request contains a list "
                "that does not belong to this section.",
            )

        positions = {
            item.list_id: item.sort_position
            for item in reorder_request.items
        }

        SectionListRepository.update_sort_positions(
            db,
            positions=positions,
        )

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.LIST_UPDATED,
            summary=(
                f"{actor.display_name} reordered lists "
                f"in {section.name}."
            ),
            entity_type="section",
            entity_id=section.id,
            metadata_json={
                "list_positions": positions,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()

        return SectionListRepository.list_for_section(
            db,
            section_id=section.id,
            include_archived=True,
        )

    @staticmethod
    def delete_list(
        db: Session,
        *,
        actor: User,
        section_list: SectionList,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> None:
        PermissionService.require_section_list_management(
            db,
            actor=actor,
            section_list=section_list,
        )

        if section_list.tasks:
            raise SectionListNotEmptyError(
                "A list containing tasks cannot be permanently deleted.",
            )

        list_id = section_list.id
        list_name = section_list.name
        section_id = section_list.section_id

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.LIST_DELETED,
            summary=(
                f"{actor.display_name} deleted {list_name}."
            ),
            entity_type="section_list",
            entity_id=list_id,
            metadata_json={
                "section_id": section_id,
                "name": list_name,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        SectionListRepository.delete(
            db,
            section_list=section_list,
        )

        if commit:
            db.commit()