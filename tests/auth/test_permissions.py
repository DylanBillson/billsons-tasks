import pytest
from sqlalchemy.orm import Session

from app.auth.permissions import PermissionDeniedError, PermissionService
from app.core.constants import CompanyRole
from tests.factories import (
    create_administrator,
    create_company,
    create_company_membership,
    create_section,
    create_section_membership,
    create_user,
)


def test_administrator_can_view_any_company(db: Session) -> None:
    administrator = create_administrator(db)
    company = create_company(db)

    assert PermissionService.can_view_company(
        db,
        actor=administrator,
        company=company,
    ) is True


def test_company_member_can_view_own_company(db: Session) -> None:
    company = create_company(db)
    user = create_user(db)
    create_company_membership(db, company=company, user=user)

    assert PermissionService.can_view_company(
        db,
        actor=user,
        company=company,
    ) is True


def test_non_member_cannot_view_company(db: Session) -> None:
    company = create_company(db)
    user = create_user(db)

    assert PermissionService.can_view_company(
        db,
        actor=user,
        company=company,
    ) is False


def test_only_administrator_can_create_company(db: Session) -> None:
    administrator = create_administrator(db)
    user = create_user(db)

    assert PermissionService.can_create_company(actor=administrator) is True
    assert PermissionService.can_create_company(actor=user) is False


def test_only_administrator_can_manage_company(db: Session) -> None:
    administrator = create_administrator(db)
    company = create_company(db)
    manager = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    assert PermissionService.can_manage_company(
        actor=administrator,
        company=company,
    ) is True
    assert PermissionService.can_manage_company(
        actor=manager,
        company=company,
    ) is False


def test_company_manager_can_manage_company_memberships(db: Session) -> None:
    company = create_company(db)
    manager = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    assert PermissionService.can_manage_company_memberships(
        db,
        actor=manager,
        company=company,
    ) is True


def test_company_employee_cannot_manage_company_memberships(db: Session) -> None:
    company = create_company(db)
    employee = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=employee,
        role=CompanyRole.EMPLOYEE,
    )

    assert PermissionService.can_manage_company_memberships(
        db,
        actor=employee,
        company=company,
    ) is False


def test_company_manager_can_create_section_in_own_company(db: Session) -> None:
    company = create_company(db)
    manager = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    assert PermissionService.can_create_section(
        db,
        actor=manager,
        company=company,
    ) is True


def test_company_manager_cannot_create_section_in_other_company(
    db: Session,
) -> None:
    own_company = create_company(db)
    other_company = create_company(db)
    manager = create_user(db)
    create_company_membership(
        db,
        company=own_company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    assert PermissionService.can_create_section(
        db,
        actor=manager,
        company=other_company,
    ) is False


def test_company_employee_cannot_create_section(db: Session) -> None:
    company = create_company(db)
    employee = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=employee,
        role=CompanyRole.EMPLOYEE,
    )

    assert PermissionService.can_create_section(
        db,
        actor=employee,
        company=company,
    ) is False


def test_section_creator_can_view_section(db: Session) -> None:
    company = create_company(db)
    creator = create_user(db)
    section = create_section(db, company=company, created_by=creator)

    assert PermissionService.can_view_section(
        db,
        actor=creator,
        section=section,
    ) is True


def test_explicit_section_member_can_view_section(db: Session) -> None:
    company = create_company(db)
    creator = create_user(db)
    assigned_user = create_user(db)
    section = create_section(db, company=company, created_by=creator)
    create_section_membership(db, section=section, user=assigned_user)

    assert PermissionService.can_view_section(
        db,
        actor=assigned_user,
        section=section,
    ) is True


def test_company_manager_does_not_automatically_view_all_sections(
    db: Session,
) -> None:
    company = create_company(db)
    manager = create_user(db)
    other_creator = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )
    section = create_section(
        db,
        company=company,
        created_by=other_creator,
    )

    assert PermissionService.can_view_section(
        db,
        actor=manager,
        section=section,
    ) is False


def test_company_manager_can_view_section_after_assignment(
    db: Session,
) -> None:
    company = create_company(db)
    manager = create_user(db)
    other_creator = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )
    section = create_section(
        db,
        company=company,
        created_by=other_creator,
    )
    create_section_membership(db, section=section, user=manager)

    assert PermissionService.can_view_section(
        db,
        actor=manager,
        section=section,
    ) is True


def test_only_administrator_or_creator_can_manage_section(db: Session) -> None:
    company = create_company(db)
    administrator = create_administrator(db)
    creator = create_user(db)
    assigned_manager = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=assigned_manager,
        role=CompanyRole.MANAGER,
    )
    section = create_section(db, company=company, created_by=creator)
    create_section_membership(db, section=section, user=assigned_manager)

    assert PermissionService.can_manage_section(
        db,
        actor=administrator,
        section=section,
    ) is True
    assert PermissionService.can_manage_section(
        db,
        actor=creator,
        section=section,
    ) is True
    assert PermissionService.can_manage_section(
        db,
        actor=assigned_manager,
        section=section,
    ) is False


def test_inactive_user_has_no_permissions(db: Session) -> None:
    company = create_company(db)
    user = create_user(db, is_active=False)
    create_company_membership(
        db,
        company=company,
        user=user,
        role=CompanyRole.MANAGER,
    )

    assert PermissionService.can_view_company(
        db,
        actor=user,
        company=company,
    ) is False
    assert PermissionService.can_create_section(
        db,
        actor=user,
        company=company,
    ) is False


def test_require_section_access_raises_for_denied_user(db: Session) -> None:
    company = create_company(db)
    creator = create_user(db)
    denied_user = create_user(db)
    section = create_section(db, company=company, created_by=creator)

    with pytest.raises(
        PermissionDeniedError,
        match="access to this section",
    ):
        PermissionService.require_section_access(
            db,
            actor=denied_user,
            section=section,
        )
