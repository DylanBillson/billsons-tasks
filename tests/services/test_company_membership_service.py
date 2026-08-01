import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import PermissionDeniedError
from app.core.constants import AuditAction, CompanyRole
from app.models.audit_log import AuditLog
from app.models.company_membership import CompanyMembership
from app.schemas.company import (
    CompanyMembershipCreateRequest,
    CompanyMembershipUpdateRequest,
)
from app.services.company_membership_service import (
    CompanyMembershipAlreadyExistsError,
    CompanyMembershipNotFoundError,
    CompanyMembershipService,
    CompanyMembershipUserNotFoundError,
    CompanyMembershipUserUnavailableError,
)
from tests.factories import (
    create_administrator,
    create_company,
    create_company_membership,
    create_user,
)


def test_require_membership_returns_existing_membership(db: Session) -> None:
    company = create_company(db)
    user = create_user(db)
    membership = create_company_membership(
        db,
        company=company,
        user=user,
    )

    assert CompanyMembershipService.require_membership(
        db,
        company_id=company.id,
        user_id=user.id,
    ) is membership


def test_require_membership_raises_for_missing_membership(db: Session) -> None:
    company = create_company(db)
    user = create_user(db)

    with pytest.raises(
        CompanyMembershipNotFoundError,
        match="not found",
    ):
        CompanyMembershipService.require_membership(
            db,
            company_id=company.id,
            user_id=user.id,
        )


def test_administrator_adds_company_member(db: Session) -> None:
    administrator = create_administrator(db)
    company = create_company(db)
    target = create_user(db)

    membership = CompanyMembershipService.add_member(
        db,
        actor=administrator,
        company=company,
        membership_create=CompanyMembershipCreateRequest(
            user_id=target.id,
            role=CompanyRole.EMPLOYEE,
        ),
    )

    assert membership.company_id == company.id
    assert membership.user_id == target.id
    assert membership.role == CompanyRole.EMPLOYEE.value


def test_company_manager_adds_company_member(db: Session) -> None:
    company = create_company(db)
    manager = create_user(db)
    target = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    membership = CompanyMembershipService.add_member(
        db,
        actor=manager,
        company=company,
        membership_create=CompanyMembershipCreateRequest(
            user_id=target.id,
        ),
    )

    assert membership.user_id == target.id


def test_employee_cannot_add_company_member(db: Session) -> None:
    company = create_company(db)
    employee = create_user(db)
    target = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=employee,
        role=CompanyRole.EMPLOYEE,
    )

    with pytest.raises(PermissionDeniedError):
        CompanyMembershipService.add_member(
            db,
            actor=employee,
            company=company,
            membership_create=CompanyMembershipCreateRequest(
                user_id=target.id,
            ),
        )


def test_add_member_rejects_unknown_user(db: Session) -> None:
    administrator = create_administrator(db)
    company = create_company(db)

    with pytest.raises(
        CompanyMembershipUserNotFoundError,
        match="could not be found",
    ):
        CompanyMembershipService.add_member(
            db,
            actor=administrator,
            company=company,
            membership_create=CompanyMembershipCreateRequest(
                user_id=999_999,
            ),
        )


def test_add_member_rejects_inactive_user(db: Session) -> None:
    administrator = create_administrator(db)
    company = create_company(db)
    inactive_user = create_user(db, is_active=False)

    with pytest.raises(
        CompanyMembershipUserUnavailableError,
        match="not available",
    ):
        CompanyMembershipService.add_member(
            db,
            actor=administrator,
            company=company,
            membership_create=CompanyMembershipCreateRequest(
                user_id=inactive_user.id,
            ),
        )


def test_add_member_rejects_duplicate_membership(db: Session) -> None:
    administrator = create_administrator(db)
    company = create_company(db)
    target = create_user(db)
    create_company_membership(db, company=company, user=target)

    with pytest.raises(
        CompanyMembershipAlreadyExistsError,
        match="already belongs",
    ):
        CompanyMembershipService.add_member(
            db,
            actor=administrator,
            company=company,
            membership_create=CompanyMembershipCreateRequest(
                user_id=target.id,
            ),
        )


def test_update_role_changes_membership_role(db: Session) -> None:
    administrator = create_administrator(db)
    company = create_company(db)
    target = create_user(db)
    membership = create_company_membership(
        db,
        company=company,
        user=target,
        role=CompanyRole.EMPLOYEE,
    )

    updated = CompanyMembershipService.update_role(
        db,
        actor=administrator,
        membership=membership,
        membership_update=CompanyMembershipUpdateRequest(
            role=CompanyRole.MANAGER,
        ),
    )

    assert updated.role == CompanyRole.MANAGER.value


def test_remove_member_deletes_membership(db: Session) -> None:
    administrator = create_administrator(db)
    company = create_company(db)
    target = create_user(db)
    membership = create_company_membership(
        db,
        company=company,
        user=target,
    )
    membership_id = membership.id

    CompanyMembershipService.remove_member(
        db,
        actor=administrator,
        membership=membership,
    )

    assert db.scalar(
        select(CompanyMembership).where(
            CompanyMembership.id == membership_id,
        )
    ) is None


def test_add_member_records_audit_log(db: Session) -> None:
    administrator = create_administrator(db)
    company = create_company(db)
    target = create_user(db)

    membership = CompanyMembershipService.add_member(
        db,
        actor=administrator,
        company=company,
        membership_create=CompanyMembershipCreateRequest(
            user_id=target.id,
        ),
    )

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action == AuditAction.COMPANY_MEMBER_ADDED.value,
            AuditLog.entity_id == membership.id,
        )
    )

    assert audit_log is not None
