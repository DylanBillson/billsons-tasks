import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.factories import (
    create_company,
    create_section,
    create_section_membership,
    create_user,
)


def test_section_membership(db: Session) -> None:
    creator = create_user(db)
    assigned_user = create_user(db)
    section = create_section(
        db,
        company=create_company(db),
        created_by=creator,
    )

    membership = create_section_membership(
        db,
        section=section,
        user=assigned_user,
    )

    assert membership.section_id == section.id
    assert membership.user_id == assigned_user.id
    assert membership.created_at is not None
    assert membership.updated_at is not None


def test_section_membership_relationships(db: Session) -> None:
    creator = create_user(db)
    assigned_user = create_user(db)
    section = create_section(
        db,
        company=create_company(db),
        created_by=creator,
    )
    membership = create_section_membership(
        db,
        section=section,
        user=assigned_user,
    )

    assert membership.section is section
    assert membership.user is assigned_user
    assert membership in section.memberships
    assert membership in assigned_user.section_memberships


def test_duplicate_section_membership_is_rejected(db: Session) -> None:
    creator = create_user(db)
    assigned_user = create_user(db)
    section = create_section(
        db,
        company=create_company(db),
        created_by=creator,
    )

    create_section_membership(
        db,
        section=section,
        user=assigned_user,
    )

    with pytest.raises(IntegrityError):
        create_section_membership(
            db,
            section=section,
            user=assigned_user,
        )


def test_user_can_join_multiple_sections(db: Session) -> None:
    company = create_company(db)
    creator = create_user(db)
    assigned_user = create_user(db)
    first = create_section(db, company=company, created_by=creator)
    second = create_section(db, company=company, created_by=creator)

    create_section_membership(db, section=first, user=assigned_user)
    create_section_membership(db, section=second, user=assigned_user)

    assert len(assigned_user.section_memberships) == 2


def test_section_membership_repr(db: Session) -> None:
    creator = create_user(db)
    assigned_user = create_user(db)
    section = create_section(
        db,
        company=create_company(db),
        created_by=creator,
    )
    membership = create_section_membership(
        db,
        section=section,
        user=assigned_user,
    )

    representation = repr(membership)

    assert f"section_id={section.id!r}" in representation
    assert f"user_id={assigned_user.id!r}" in representation
