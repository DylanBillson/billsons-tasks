import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import PermissionDeniedError
from app.core.constants import AuditAction, CompanyRole
from app.models.audit_log import AuditLog
from app.models.section import Section
from app.schemas.section import SectionCreateRequest, SectionUpdateRequest
from app.services.section_service import (
    SectionNameAlreadyExistsError,
    SectionNotFoundError,
    SectionService,
)
from tests.factories import (
    create_administrator,
    create_company,
    create_company_membership,
    create_section,
    create_section_membership,
    create_user,
)


def test_require_section_returns_existing_section(db: Session) -> None:
    company = create_company(db)
    creator = create_user(db)
    section = create_section(db, company=company, created_by=creator)

    assert SectionService.require_section(
        db,
        section_id=section.id,
    ) is section


def test_require_section_raises_for_missing_section(db: Session) -> None:
    with pytest.raises(
        SectionNotFoundError,
        match="Section was not found",
    ):
        SectionService.require_section(db, section_id=999_999)


def test_company_manager_creates_section_in_own_company(
    db: Session,
) -> None:
    company = create_company(db)
    manager = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    section = SectionService.create_section(
        db,
        actor=manager,
        company=company,
        section_create=SectionCreateRequest(name="Front of House"),
    )

    assert section.company_id == company.id
    assert section.created_by_user_id == manager.id


def test_employee_cannot_create_section(db: Session) -> None:
    company = create_company(db)
    employee = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=employee,
        role=CompanyRole.EMPLOYEE,
    )

    with pytest.raises(PermissionDeniedError):
        SectionService.create_section(
            db,
            actor=employee,
            company=company,
            section_create=SectionCreateRequest(name="Denied Section"),
        )


def test_manager_cannot_create_section_in_other_company(db: Session) -> None:
    own_company = create_company(db)
    other_company = create_company(db)
    manager = create_user(db)
    create_company_membership(
        db,
        company=own_company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    with pytest.raises(PermissionDeniedError):
        SectionService.create_section(
            db,
            actor=manager,
            company=other_company,
            section_create=SectionCreateRequest(name="Denied Section"),
        )


def test_create_section_rejects_duplicate_name_in_company(
    db: Session,
) -> None:
    company = create_company(db)
    manager = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )
    create_section(
        db,
        company=company,
        created_by=manager,
        name="Operations",
    )

    with pytest.raises(
        SectionNameAlreadyExistsError,
        match="already exists",
    ):
        SectionService.create_section(
            db,
            actor=manager,
            company=company,
            section_create=SectionCreateRequest(name="Operations"),
        )


def test_list_accessible_sections_excludes_unassigned_sections(
    db: Session,
) -> None:
    company = create_company(db)
    manager = create_user(db)
    other_manager = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )
    create_company_membership(
        db,
        company=company,
        user=other_manager,
        role=CompanyRole.MANAGER,
    )

    own_section = create_section(
        db,
        company=company,
        created_by=manager,
    )
    hidden_section = create_section(
        db,
        company=company,
        created_by=other_manager,
    )

    sections = SectionService.list_accessible_sections(
        db,
        actor=manager,
        company_id=company.id,
    )

    assert own_section in sections
    assert hidden_section not in sections


def test_assigned_section_is_listed(db: Session) -> None:
    company = create_company(db)
    creator = create_user(db)
    assigned = create_user(db)
    section = create_section(db, company=company, created_by=creator)
    create_section_membership(db, section=section, user=assigned)

    sections = SectionService.list_accessible_sections(
        db,
        actor=assigned,
        company_id=company.id,
    )

    assert section in sections


def test_creator_updates_section(db: Session) -> None:
    company = create_company(db)
    creator = create_user(db)
    section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Old Name",
    )

    updated = SectionService.update_section(
        db,
        actor=creator,
        section=section,
        section_update=SectionUpdateRequest(
            name="New Name",
            description="Updated.",
        ),
    )

    assert updated.name == "New Name"
    assert updated.description == "Updated."


def test_assigned_manager_cannot_update_section(db: Session) -> None:
    company = create_company(db)
    creator = create_user(db)
    manager = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )
    section = create_section(db, company=company, created_by=creator)
    create_section_membership(db, section=section, user=manager)

    with pytest.raises(PermissionDeniedError):
        SectionService.update_section(
            db,
            actor=manager,
            section=section,
            section_update=SectionUpdateRequest(name="Denied Update"),
        )


def test_creator_archives_section(db: Session) -> None:
    company = create_company(db)
    creator = create_user(db)
    section = create_section(db, company=company, created_by=creator)

    SectionService.set_archived_status(
        db,
        actor=creator,
        section=section,
        is_archived=True,
    )

    assert section.is_archived is True


def test_delete_section_removes_record(db: Session) -> None:
    administrator = create_administrator(db)
    company = create_company(db)
    creator = create_user(db)
    section = create_section(db, company=company, created_by=creator)
    section_id = section.id

    SectionService.delete_section(
        db,
        actor=administrator,
        section=section,
    )

    assert db.scalar(
        select(Section).where(Section.id == section_id)
    ) is None


def test_create_section_records_audit_log(db: Session) -> None:
    administrator = create_administrator(db)
    company = create_company(db)

    section = SectionService.create_section(
        db,
        actor=administrator,
        company=company,
        section_create=SectionCreateRequest(name="Audited Section"),
    )

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action == AuditAction.SECTION_CREATED.value,
            AuditLog.entity_id == section.id,
        )
    )

    assert audit_log is not None
