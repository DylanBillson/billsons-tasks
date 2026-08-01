import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.factories import (
    create_company,
    create_section,
    create_section_membership,
    create_user,
)


def test_section_defaults(db: Session) -> None:
    company = create_company(db)
    creator = create_user(db)

    section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Front of House",
    )

    assert section.company_id == company.id
    assert section.created_by_user_id == creator.id
    assert section.name == "Front of House"
    assert section.description is None
    assert section.is_archived is False


def test_section_relationships(db: Session) -> None:
    company = create_company(db)
    creator = create_user(db)
    assigned_user = create_user(db)
    section = create_section(
        db,
        company=company,
        created_by=creator,
    )
    membership = create_section_membership(
        db,
        section=section,
        user=assigned_user,
    )

    assert section.company is company
    assert section.created_by is creator
    assert section in company.sections
    assert section in creator.created_sections
    assert membership in section.memberships


def test_same_name_allowed_in_different_companies(db: Session) -> None:
    creator = create_user(db)
    first = create_section(
        db,
        company=create_company(db),
        created_by=creator,
        name="Operations",
    )
    second = create_section(
        db,
        company=create_company(db),
        created_by=creator,
        name="Operations",
    )

    assert first.id != second.id


def test_duplicate_name_in_same_company_is_rejected(db: Session) -> None:
    company = create_company(db)
    creator = create_user(db)

    create_section(
        db,
        company=company,
        created_by=creator,
        name="Operations",
    )

    with pytest.raises(IntegrityError):
        create_section(
            db,
            company=company,
            created_by=creator,
            name="Operations",
        )


def test_creator_is_not_automatically_a_section_member(db: Session) -> None:
    company = create_company(db)
    creator = create_user(db)
    section = create_section(
        db,
        company=company,
        created_by=creator,
    )

    assert section.created_by is creator
    assert section.memberships == []
    assert creator.section_memberships == []


def test_section_repr(db: Session) -> None:
    company = create_company(db)
    creator = create_user(db)
    section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Represented Section",
        is_archived=True,
    )

    representation = repr(section)

    assert f"company_id={company.id!r}" in representation
    assert f"created_by_user_id={creator.id!r}" in representation
    assert "Represented Section" in representation
    assert "is_archived=True" in representation
