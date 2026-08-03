import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.factories import (
    create_company,
    create_section,
    create_section_list,
    create_task,
    create_user,
)


def test_section_list_defaults(
    db: Session,
) -> None:
    creator = create_user(
        db,
    )

    section = create_section(
        db,
        company=create_company(
            db,
        ),
        created_by=creator,
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    assert section_list.id is not None
    assert section_list.section_id == section.id
    assert section_list.name.startswith(
        "Test List ",
    )
    assert section_list.description is None
    assert section_list.sort_position == 1000
    assert section_list.is_archived is False
    assert section_list.created_at is not None
    assert section_list.updated_at is not None


def test_section_list_accepts_custom_values(
    db: Session,
) -> None:
    section = create_section(
        db,
        company=create_company(
            db,
        ),
        created_by=create_user(
            db,
        ),
    )

    section_list = create_section_list(
        db,
        section=section,
        name="In Progress",
        description="Tasks currently being worked on.",
        sort_position=3000,
        is_archived=True,
    )

    assert section_list.name == "In Progress"
    assert (
        section_list.description
        == "Tasks currently being worked on."
    )
    assert section_list.sort_position == 3000
    assert section_list.is_archived is True


def test_section_list_relationships(
    db: Session,
) -> None:
    creator = create_user(
        db,
    )

    section = create_section(
        db,
        company=create_company(
            db,
        ),
        created_by=creator,
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
    )

    assert section_list.section is section
    assert section_list in section.lists
    assert task.section_list is section_list
    assert task in section_list.tasks


def test_section_lists_are_ordered_by_position(
    db: Session,
) -> None:
    section = create_section(
        db,
        company=create_company(
            db,
        ),
        created_by=create_user(
            db,
        ),
    )

    later = create_section_list(
        db,
        section=section,
        name="Later",
        sort_position=3000,
    )

    first = create_section_list(
        db,
        section=section,
        name="First",
        sort_position=1000,
    )

    middle = create_section_list(
        db,
        section=section,
        name="Middle",
        sort_position=2000,
    )

    db.expire(
        section,
        [
            "lists",
        ],
    )

    assert section.lists == [
        first,
        middle,
        later,
    ]


def test_duplicate_list_name_in_same_section_is_rejected(
    db: Session,
) -> None:
    section = create_section(
        db,
        company=create_company(
            db,
        ),
        created_by=create_user(
            db,
        ),
    )

    create_section_list(
        db,
        section=section,
        name="To Do",
    )

    with pytest.raises(
        IntegrityError,
    ):
        create_section_list(
            db,
            section=section,
            name="To Do",
        )


def test_same_list_name_allowed_in_different_sections(
    db: Session,
) -> None:
    company = create_company(
        db,
    )

    creator = create_user(
        db,
    )

    first_section = create_section(
        db,
        company=company,
        created_by=creator,
    )

    second_section = create_section(
        db,
        company=company,
        created_by=creator,
    )

    first = create_section_list(
        db,
        section=first_section,
        name="To Do",
    )

    second = create_section_list(
        db,
        section=second_section,
        name="To Do",
    )

    assert first.id != second.id


def test_negative_list_position_is_rejected(
    db: Session,
) -> None:
    section = create_section(
        db,
        company=create_company(
            db,
        ),
        created_by=create_user(
            db,
        ),
    )

    with pytest.raises(
        IntegrityError,
    ):
        create_section_list(
            db,
            section=section,
            sort_position=-1,
        )


def test_section_list_repr(
    db: Session,
) -> None:
    section_list = create_section_list(
        db,
        section=create_section(
            db,
            company=create_company(
                db,
            ),
            created_by=create_user(
                db,
            ),
        ),
        name="Completed",
        sort_position=4000,
    )

    representation = repr(
        section_list,
    )

    assert "SectionList" in representation
    assert f"id={section_list.id!r}" in representation
    assert f"section_id={section_list.section_id!r}" in representation
    assert "name='Completed'" in representation
    assert "sort_position=4000" in representation
    assert "is_archived=False" in representation