import pytest
from sqlalchemy.orm import Session

from app.auth.permissions import PermissionDeniedError
from app.core.constants import CompanyRole
from app.schemas.section import SectionCreateRequest, SectionUpdateRequest
from app.services.company_service import CompanyService
from app.services.section_service import SectionService
from tests.factories import (
    create_company,
    create_company_membership,
    create_section,
    create_section_membership,
    create_user,
)


def test_manager_cannot_access_other_managers_unassigned_section(
    db: Session,
) -> None:
    company = create_company(db)
    manager_a = create_user(db)
    manager_b = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=manager_a,
        role=CompanyRole.MANAGER,
    )
    create_company_membership(
        db,
        company=company,
        user=manager_b,
        role=CompanyRole.MANAGER,
    )
    section_b = create_section(
        db,
        company=company,
        created_by=manager_b,
    )

    with pytest.raises(PermissionDeniedError):
        SectionService.get_accessible_section(
            db,
            actor=manager_a,
            section_id=section_b.id,
        )


def test_manager_can_access_other_managers_section_after_assignment(
    db: Session,
) -> None:
    company = create_company(db)
    manager_a = create_user(db)
    manager_b = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=manager_a,
        role=CompanyRole.MANAGER,
    )
    create_company_membership(
        db,
        company=company,
        user=manager_b,
        role=CompanyRole.MANAGER,
    )
    section_b = create_section(
        db,
        company=company,
        created_by=manager_b,
    )
    create_section_membership(
        db,
        section=section_b,
        user=manager_a,
    )

    assert SectionService.get_accessible_section(
        db,
        actor=manager_a,
        section_id=section_b.id,
    ) is section_b


def test_manager_cannot_access_section_in_other_company(db: Session) -> None:
    company_a = create_company(db)
    company_b = create_company(db)
    manager_a = create_user(db)
    manager_b = create_user(db)
    create_company_membership(
        db,
        company=company_a,
        user=manager_a,
        role=CompanyRole.MANAGER,
    )
    create_company_membership(
        db,
        company=company_b,
        user=manager_b,
        role=CompanyRole.MANAGER,
    )
    section_b = create_section(
        db,
        company=company_b,
        created_by=manager_b,
    )

    with pytest.raises(PermissionDeniedError):
        SectionService.get_accessible_section(
            db,
            actor=manager_a,
            section_id=section_b.id,
        )


def test_employee_cannot_access_unassigned_section(db: Session) -> None:
    company = create_company(db)
    manager = create_user(db)
    employee = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )
    create_company_membership(
        db,
        company=company,
        user=employee,
        role=CompanyRole.EMPLOYEE,
    )
    section = create_section(
        db,
        company=company,
        created_by=manager,
    )

    with pytest.raises(PermissionDeniedError):
        SectionService.get_accessible_section(
            db,
            actor=employee,
            section_id=section.id,
        )


def test_employee_can_access_assigned_section(db: Session) -> None:
    company = create_company(db)
    manager = create_user(db)
    employee = create_user(db)
    create_company_membership(db, company=company, user=employee)
    section = create_section(
        db,
        company=company,
        created_by=manager,
    )
    create_section_membership(
        db,
        section=section,
        user=employee,
    )

    assert SectionService.get_accessible_section(
        db,
        actor=employee,
        section_id=section.id,
    ) is section


def test_assigned_manager_cannot_edit_section_they_did_not_create(
    db: Session,
) -> None:
    company = create_company(db)
    creator = create_user(db)
    assigned_manager = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=assigned_manager,
        role=CompanyRole.MANAGER,
    )
    section = create_section(
        db,
        company=company,
        created_by=creator,
    )
    create_section_membership(
        db,
        section=section,
        user=assigned_manager,
    )

    with pytest.raises(PermissionDeniedError):
        SectionService.update_section(
            db,
            actor=assigned_manager,
            section=section,
            section_update=SectionUpdateRequest(
                name="Forbidden Update",
            ),
        )


def test_manager_cannot_create_section_in_company_they_do_not_manage(
    db: Session,
) -> None:
    company_a = create_company(db)
    company_b = create_company(db)
    manager = create_user(db)
    create_company_membership(
        db,
        company=company_a,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    with pytest.raises(PermissionDeniedError):
        SectionService.create_section(
            db,
            actor=manager,
            company=company_b,
            section_create=SectionCreateRequest(
                name="Forbidden Section",
            ),
        )


def test_non_member_cannot_retrieve_company_by_changing_id(
    db: Session,
) -> None:
    company = create_company(db)
    non_member = create_user(db)

    with pytest.raises(PermissionDeniedError):
        CompanyService.get_accessible_company(
            db,
            actor=non_member,
            company_id=company.id,
        )
