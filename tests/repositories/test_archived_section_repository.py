from sqlalchemy.orm import Session

from app.repositories.section_repository import SectionRepository
from tests.factories import (
    create_company,
    create_section,
    create_section_membership,
    create_user,
)


def test_list_archived_returns_only_archived_sections(
    db: Session,
) -> None:
    creator = create_user(
        db,
    )

    company = create_company(
        db,
    )

    archived = create_section(
        db,
        company=company,
        created_by=creator,
        name="Archived Section",
        is_archived=True,
    )

    create_section(
        db,
        company=company,
        created_by=creator,
        name="Active Section",
    )

    result = SectionRepository.list_archived(
        db,
    )

    assert result == [
        archived,
    ]


def test_list_archived_filters_by_company(
    db: Session,
) -> None:
    creator = create_user(
        db,
    )

    first_company = create_company(
        db,
        name="First Company",
    )

    second_company = create_company(
        db,
        name="Second Company",
    )

    visible = create_section(
        db,
        company=first_company,
        created_by=creator,
        is_archived=True,
    )

    create_section(
        db,
        company=second_company,
        created_by=creator,
        is_archived=True,
    )

    result = SectionRepository.list_archived(
        db,
        company_id=first_company.id,
    )

    assert result == [
        visible,
    ]


def test_list_archived_searches_section_and_company(
    db: Session,
) -> None:
    creator = create_user(
        db,
    )

    lighthouse_company = create_company(
        db,
        name="Lighthouse Company",
    )

    other_company = create_company(
        db,
        name="Other Company",
    )

    company_match = create_section(
        db,
        company=lighthouse_company,
        created_by=creator,
        name="Operations",
        is_archived=True,
    )

    section_match = create_section(
        db,
        company=other_company,
        created_by=creator,
        name="Lighthouse Maintenance",
        is_archived=True,
    )

    create_section(
        db,
        company=other_company,
        created_by=creator,
        name="Kitchen",
        is_archived=True,
    )

    result = SectionRepository.list_archived(
        db,
        search="lighthouse",
    )

    assert result == [
        company_match,
        section_match,
    ]


def test_list_archived_loads_related_records(
    db: Session,
) -> None:
    creator = create_user(
        db,
    )

    member = create_user(
        db,
    )

    company = create_company(
        db,
    )

    section = create_section(
        db,
        company=company,
        created_by=creator,
        is_archived=True,
    )

    membership = create_section_membership(
        db,
        section=section,
        user=member,
    )

    result = SectionRepository.list_archived(
        db,
    )

    assert result == [
        section,
    ]

    assert section.company is company
    assert section.created_by is creator
    assert membership in section.memberships


def test_list_and_count_archived_support_pagination(
    db: Session,
) -> None:
    creator = create_user(
        db,
    )

    company = create_company(
        db,
    )

    first = create_section(
        db,
        company=company,
        created_by=creator,
        name="A Section",
        is_archived=True,
    )

    second = create_section(
        db,
        company=company,
        created_by=creator,
        name="B Section",
        is_archived=True,
    )

    page = SectionRepository.list_archived(
        db,
        offset=1,
        limit=1,
    )

    count = SectionRepository.count_archived(
        db,
    )

    assert page == [
        second,
    ]

    assert count == 2
    assert first not in page