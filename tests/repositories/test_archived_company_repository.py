from sqlalchemy.orm import Session

from app.repositories.company_repository import (
    CompanyRepository,
)
from tests.factories import (
    create_company,
    create_company_membership,
    create_user,
)


def test_list_all_excludes_archived_companies_by_default(
    db: Session,
) -> None:
    active = create_company(
        db,
        name="Active Company",
    )

    create_company(
        db,
        name="Archived Company",
        is_archived=True,
    )

    result = CompanyRepository.list_all(
        db,
    )

    assert result == [
        active,
    ]


def test_list_all_can_include_archived_companies(
    db: Session,
) -> None:
    active = create_company(
        db,
        name="Active Company",
    )

    archived = create_company(
        db,
        name="Archived Company",
        is_archived=True,
    )

    result = CompanyRepository.list_all(
        db,
        include_archived=True,
    )

    assert result == [
        active,
        archived,
    ]


def test_list_all_returns_archived_company_memberships(
    db: Session,
) -> None:
    archived = create_company(
        db,
        name="Archived Company",
        is_archived=True,
    )

    member = create_user(
        db,
    )

    membership = create_company_membership(
        db,
        company=archived,
        user=member,
    )

    result = CompanyRepository.list_all(
        db,
        include_archived=True,
    )

    assert result == [
        archived,
    ]

    assert membership in archived.memberships


def test_list_for_user_excludes_archived_by_default(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    active = create_company(
        db,
        name="Active Company",
    )

    archived = create_company(
        db,
        name="Archived Company",
        is_archived=True,
    )

    create_company_membership(
        db,
        company=active,
        user=user,
    )

    create_company_membership(
        db,
        company=archived,
        user=user,
    )

    result = CompanyRepository.list_for_user(
        db,
        user_id=user.id,
    )

    assert result == [
        active,
    ]


def test_list_for_user_can_include_archived_companies(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    active = create_company(
        db,
        name="Active Company",
    )

    archived = create_company(
        db,
        name="Archived Company",
        is_archived=True,
    )

    create_company_membership(
        db,
        company=active,
        user=user,
    )

    create_company_membership(
        db,
        company=archived,
        user=user,
    )

    result = CompanyRepository.list_for_user(
        db,
        user_id=user.id,
        include_archived=True,
    )

    assert result == [
        active,
        archived,
    ]