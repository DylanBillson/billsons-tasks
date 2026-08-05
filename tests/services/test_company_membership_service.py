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
    CompanyMembershipServiceError,
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

from unittest.mock import patch


def test_list_memberships_allows_company_manager(
    db: Session,
) -> None:
    company = create_company(
        db,
    )

    manager = create_user(
        db,
    )

    employee = create_user(
        db,
    )

    manager_membership = create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    employee_membership = create_company_membership(
        db,
        company=company,
        user=employee,
        role=CompanyRole.EMPLOYEE,
    )

    result = CompanyMembershipService.list_memberships(
        db,
        actor=manager,
        company=company,
    )

    assert manager_membership in result
    assert employee_membership in result


def test_list_memberships_rejects_company_employee(
    db: Session,
) -> None:
    company = create_company(
        db,
    )

    employee = create_user(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=employee,
        role=CompanyRole.EMPLOYEE,
    )

    with pytest.raises(
        PermissionDeniedError,
    ):
        CompanyMembershipService.list_memberships(
            db,
            actor=employee,
            company=company,
        )


def test_company_manager_cannot_manage_other_company_membership(
    db: Session,
) -> None:
    managed_company = create_company(
        db,
    )

    other_company = create_company(
        db,
    )

    manager = create_user(
        db,
    )

    target = create_user(
        db,
    )

    create_company_membership(
        db,
        company=managed_company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    with pytest.raises(
        PermissionDeniedError,
    ):
        CompanyMembershipService.add_member(
            db,
            actor=manager,
            company=other_company,
            membership_create=(
                CompanyMembershipCreateRequest(
                    user_id=target.id,
                )
            ),
        )


def test_add_member_rejects_anonymised_user(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    company = create_company(
        db,
    )

    anonymised_user = create_user(
        db,
        is_active=False,
        is_anonymised=True,
    )

    with pytest.raises(
        CompanyMembershipUserUnavailableError,
        match="not available",
    ):
        CompanyMembershipService.add_member(
            db,
            actor=administrator,
            company=company,
            membership_create=(
                CompanyMembershipCreateRequest(
                    user_id=anonymised_user.id,
                )
            ),
        )


def test_add_member_rejects_archived_company(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    company = create_company(
        db,
        is_archived=True,
    )

    target = create_user(
        db,
    )

    with pytest.raises(
        CompanyMembershipServiceError,
        match="archived company",
    ):
        CompanyMembershipService.add_member(
            db,
            actor=administrator,
            company=company,
            membership_create=(
                CompanyMembershipCreateRequest(
                    user_id=target.id,
                )
            ),
        )


def test_update_role_returns_without_audit_when_unchanged(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    company = create_company(
        db,
    )

    target = create_user(
        db,
    )

    membership = create_company_membership(
        db,
        company=company,
        user=target,
        role=CompanyRole.EMPLOYEE,
    )

    audit_count_before = len(
        db.scalars(
            select(AuditLog).where(
                AuditLog.action
                == AuditAction.COMPANY_MEMBER_UPDATED.value,
                AuditLog.entity_type
                == "company_membership",
                AuditLog.entity_id
                == membership.id,
            )
        ).all()
    )

    result = CompanyMembershipService.update_role(
        db,
        actor=administrator,
        membership=membership,
        membership_update=(
            CompanyMembershipUpdateRequest(
                role=CompanyRole.EMPLOYEE,
            )
        ),
    )

    audit_count_after = len(
        db.scalars(
            select(AuditLog).where(
                AuditLog.action
                == AuditAction.COMPANY_MEMBER_UPDATED.value,
                AuditLog.entity_type
                == "company_membership",
                AuditLog.entity_id
                == membership.id,
            )
        ).all()
    )

    assert result is membership
    assert audit_count_after == audit_count_before


def test_update_role_records_complete_audit_log(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        display_name="Membership Administrator",
    )

    company = create_company(
        db,
        name="Audited Membership Company",
    )

    target = create_user(
        db,
        username="audited-membership-user",
        display_name="Audited Membership User",
    )

    membership = create_company_membership(
        db,
        company=company,
        user=target,
        role=CompanyRole.EMPLOYEE,
    )

    CompanyMembershipService.update_role(
        db,
        actor=administrator,
        membership=membership,
        membership_update=(
            CompanyMembershipUpdateRequest(
                role=CompanyRole.MANAGER,
            )
        ),
        ip_address="192.0.2.80",
        user_agent="Membership role test",
    )

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action
            == AuditAction.COMPANY_MEMBER_UPDATED.value,
            AuditLog.entity_type
            == "company_membership",
            AuditLog.entity_id
            == membership.id,
        )
    )

    assert audit_log is not None
    assert audit_log.user_id == administrator.id

    assert audit_log.metadata_json == {
        "company_id": company.id,
        "company_name": company.name,
        "user_id": target.id,
        "username": target.username,
        "previous_role": CompanyRole.EMPLOYEE.value,
        "new_role": CompanyRole.MANAGER.value,
    }

    assert audit_log.ip_address == "192.0.2.80"
    assert audit_log.user_agent == "Membership role test"


def test_remove_member_records_audit_log(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        display_name="Removing Administrator",
    )

    company = create_company(
        db,
        name="Removal Company",
    )

    target = create_user(
        db,
        username="removed-membership-user",
        display_name="Removed Membership User",
    )

    membership = create_company_membership(
        db,
        company=company,
        user=target,
        role=CompanyRole.MANAGER,
    )

    CompanyMembershipService.remove_member(
        db,
        actor=administrator,
        membership=membership,
        ip_address="198.51.100.81",
        user_agent="Membership removal test",
    )

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action
            == AuditAction.COMPANY_MEMBER_REMOVED.value,
            AuditLog.entity_type == "company",
            AuditLog.entity_id == company.id,
        )
    )

    assert audit_log is not None
    assert audit_log.user_id == administrator.id

    assert audit_log.metadata_json == {
        "company_id": company.id,
        "company_name": company.name,
        "user_id": target.id,
        "username": target.username,
        "removed_role": CompanyRole.MANAGER.value,
    }


def test_add_member_does_not_commit_when_commit_is_false(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    company = create_company(
        db,
    )

    target = create_user(
        db,
    )

    with patch.object(
        db,
        "commit",
        wraps=db.commit,
    ) as commit_mock:
        membership = CompanyMembershipService.add_member(
            db,
            actor=administrator,
            company=company,
            membership_create=(
                CompanyMembershipCreateRequest(
                    user_id=target.id,
                )
            ),
            commit=False,
        )

    commit_mock.assert_not_called()

    assert membership.id is not None
    assert membership.company_id == company.id
    assert membership.user_id == target.id


def test_update_role_does_not_commit_when_commit_is_false(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    company = create_company(
        db,
    )

    target = create_user(
        db,
    )

    membership = create_company_membership(
        db,
        company=company,
        user=target,
        role=CompanyRole.EMPLOYEE,
    )

    with patch.object(
        db,
        "commit",
        wraps=db.commit,
    ) as commit_mock:
        result = CompanyMembershipService.update_role(
            db,
            actor=administrator,
            membership=membership,
            membership_update=(
                CompanyMembershipUpdateRequest(
                    role=CompanyRole.MANAGER,
                )
            ),
            commit=False,
        )

    commit_mock.assert_not_called()

    assert result.role == CompanyRole.MANAGER.value


def test_remove_member_does_not_commit_when_commit_is_false(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    company = create_company(
        db,
    )

    target = create_user(
        db,
    )

    membership = create_company_membership(
        db,
        company=company,
        user=target,
    )

    with patch.object(
        db,
        "commit",
        wraps=db.commit,
    ) as commit_mock:
        CompanyMembershipService.remove_member(
            db,
            actor=administrator,
            membership=membership,
            commit=False,
        )

    commit_mock.assert_not_called()

    assert membership not in db