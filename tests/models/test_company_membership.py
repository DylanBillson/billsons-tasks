import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.constants import CompanyRole
from tests.factories import (
    create_company,
    create_company_membership,
    create_user,
)


def test_company_membership_defaults_to_employee(db: Session) -> None:
    company = create_company(db)
    user = create_user(db)

    membership = create_company_membership(
        db,
        company=company,
        user=user,
    )

    assert membership.company_id == company.id
    assert membership.user_id == user.id
    assert membership.role == CompanyRole.EMPLOYEE.value
    assert membership.is_employee is True
    assert membership.is_manager is False


def test_company_manager_membership(db: Session) -> None:
    company = create_company(db)
    user = create_user(db)

    membership = create_company_membership(
        db,
        company=company,
        user=user,
        role=CompanyRole.MANAGER,
    )

    assert membership.is_manager is True
    assert membership.is_employee is False


def test_company_membership_relationships(db: Session) -> None:
    company = create_company(db)
    user = create_user(db)

    membership = create_company_membership(
        db,
        company=company,
        user=user,
    )

    assert membership.company is company
    assert membership.user is user
    assert membership in company.memberships
    assert membership in user.company_memberships


def test_duplicate_company_membership_is_rejected(db: Session) -> None:
    company = create_company(db)
    user = create_user(db)

    create_company_membership(db, company=company, user=user)

    with pytest.raises(IntegrityError):
        create_company_membership(db, company=company, user=user)


def test_invalid_company_role_is_rejected(db: Session) -> None:
    company = create_company(db)
    user = create_user(db)

    with pytest.raises(IntegrityError):
        create_company_membership(
            db,
            company=company,
            user=user,
            role="owner",
        )


def test_company_membership_repr(db: Session) -> None:
    company = create_company(db)
    user = create_user(db)
    membership = create_company_membership(
        db,
        company=company,
        user=user,
        role=CompanyRole.MANAGER,
    )

    representation = repr(membership)

    assert f"company_id={company.id!r}" in representation
    assert f"user_id={user.id!r}" in representation
    assert "manager" in representation
