from sqlalchemy.orm import Session

from tests.factories import (
    create_company,
    create_company_membership,
    create_section,
    create_user,
)


def test_company_defaults(db: Session) -> None:
    company = create_company(db, name="Anchor Hotel")

    assert company.id is not None
    assert company.name == "Anchor Hotel"
    assert company.description is None
    assert company.is_archived is False
    assert company.created_at is not None
    assert company.updated_at is not None


def test_company_accepts_custom_values(db: Session) -> None:
    company = create_company(
        db,
        name="Galassify",
        description="Technology and operations.",
        is_archived=True,
    )

    assert company.description == "Technology and operations."
    assert company.is_archived is True


def test_company_relationships(db: Session) -> None:
    company = create_company(db)
    user = create_user(db)
    membership = create_company_membership(
        db,
        company=company,
        user=user,
    )
    section = create_section(
        db,
        company=company,
        created_by=user,
    )

    db.refresh(company)

    assert membership in company.memberships
    assert section in company.sections
    assert membership.company is company
    assert section.company is company


def test_company_repr(db: Session) -> None:
    company = create_company(
        db,
        name="Represented Company",
        is_archived=True,
    )

    representation = repr(company)

    assert f"id={company.id!r}" in representation
    assert "Represented Company" in representation
    assert "is_archived=True" in representation
