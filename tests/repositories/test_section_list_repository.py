from sqlalchemy.orm import Session

from app.repositories.section_list_repository import (
    SectionListRepository,
)
from tests.factories import (
    create_company,
    create_section,
    create_section_list,
    create_task,
    create_user,
)


def _create_section(
    db: Session,
):
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

    return creator, section


def test_get_by_id_returns_section_list(
    db: Session,
) -> None:
    _, section = _create_section(
        db,
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    result = SectionListRepository.get_by_id(
        db,
        section_list_id=section_list.id,
    )

    assert result is section_list
    assert result.section is section


def test_get_by_id_returns_none_for_unknown_list(
    db: Session,
) -> None:
    result = SectionListRepository.get_by_id(
        db,
        section_list_id=999999,
    )

    assert result is None


def test_get_by_section_and_name(
    db: Session,
) -> None:
    _, section = _create_section(
        db,
    )

    section_list = create_section_list(
        db,
        section=section,
        name="In Progress",
    )

    result = (
        SectionListRepository.get_by_section_and_name(
            db,
            section_id=section.id,
            name="In Progress",
        )
    )

    assert result is section_list


def test_get_by_section_and_name_is_section_scoped(
    db: Session,
) -> None:
    creator = create_user(
        db,
    )

    company = create_company(
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

    first_list = create_section_list(
        db,
        section=first_section,
        name="To Do",
    )

    second_list = create_section_list(
        db,
        section=second_section,
        name="To Do",
    )

    assert (
        SectionListRepository.get_by_section_and_name(
            db,
            section_id=first_section.id,
            name="To Do",
        )
        is first_list
    )

    assert (
        SectionListRepository.get_by_section_and_name(
            db,
            section_id=second_section.id,
            name="To Do",
        )
        is second_list
    )


def test_list_for_section_orders_by_position(
    db: Session,
) -> None:
    _, section = _create_section(
        db,
    )

    later = create_section_list(
        db,
        section=section,
        sort_position=3000,
    )

    first = create_section_list(
        db,
        section=section,
        sort_position=1000,
    )

    middle = create_section_list(
        db,
        section=section,
        sort_position=2000,
    )

    result = SectionListRepository.list_for_section(
        db,
        section_id=section.id,
    )

    assert result == [
        first,
        middle,
        later,
    ]


def test_list_for_section_excludes_archived_by_default(
    db: Session,
) -> None:
    _, section = _create_section(
        db,
    )

    active = create_section_list(
        db,
        section=section,
    )

    create_section_list(
        db,
        section=section,
        is_archived=True,
    )

    result = SectionListRepository.list_for_section(
        db,
        section_id=section.id,
    )

    assert result == [
        active,
    ]


def test_list_for_section_can_include_archived(
    db: Session,
) -> None:
    _, section = _create_section(
        db,
    )

    active = create_section_list(
        db,
        section=section,
        sort_position=1000,
    )

    archived = create_section_list(
        db,
        section=section,
        sort_position=2000,
        is_archived=True,
    )

    result = SectionListRepository.list_for_section(
        db,
        section_id=section.id,
        include_archived=True,
    )

    assert result == [
        active,
        archived,
    ]


def test_list_for_section_can_eager_load_tasks(
    db: Session,
) -> None:
    creator, section = _create_section(
        db,
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

    db.expire_all()

    result = SectionListRepository.list_for_section(
        db,
        section_id=section.id,
        include_tasks=True,
    )

    assert len(result) == 1
    assert result[0].tasks == [
        task,
    ]


def test_get_max_sort_position(
    db: Session,
) -> None:
    _, section = _create_section(
        db,
    )

    create_section_list(
        db,
        section=section,
        sort_position=1000,
    )

    create_section_list(
        db,
        section=section,
        sort_position=4000,
    )

    maximum = SectionListRepository.get_max_sort_position(
        db,
        section_id=section.id,
    )

    assert maximum == 4000


def test_get_max_sort_position_returns_none_for_empty_section(
    db: Session,
) -> None:
    _, section = _create_section(
        db,
    )

    maximum = SectionListRepository.get_max_sort_position(
        db,
        section_id=section.id,
    )

    assert maximum is None


def test_get_next_sort_position(
    db: Session,
) -> None:
    _, section = _create_section(
        db,
    )

    create_section_list(
        db,
        section=section,
        sort_position=2000,
    )

    position = SectionListRepository.get_next_sort_position(
        db,
        section_id=section.id,
    )

    assert position == 3000


def test_get_next_sort_position_for_empty_section(
    db: Session,
) -> None:
    _, section = _create_section(
        db,
    )

    position = SectionListRepository.get_next_sort_position(
        db,
        section_id=section.id,
    )

    assert position == 1000


def test_create_uses_next_sort_position(
    db: Session,
) -> None:
    _, section = _create_section(
        db,
    )

    create_section_list(
        db,
        section=section,
        sort_position=2000,
    )

    section_list = SectionListRepository.create(
        db,
        section_id=section.id,
        name="Completed",
        description="Completed work.",
    )

    assert section_list.section_id == section.id
    assert section_list.name == "Completed"
    assert section_list.description == "Completed work."
    assert section_list.sort_position == 3000


def test_create_accepts_explicit_sort_position(
    db: Session,
) -> None:
    _, section = _create_section(
        db,
    )

    section_list = SectionListRepository.create(
        db,
        section_id=section.id,
        name="Urgent",
        sort_position=50,
    )

    assert section_list.sort_position == 50


def test_update_section_list(
    db: Session,
) -> None:
    _, section = _create_section(
        db,
    )

    section_list = create_section_list(
        db,
        section=section,
        name="Old Name",
    )

    result = SectionListRepository.update(
        db,
        section_list=section_list,
        name="New Name",
        description="New description.",
    )

    assert result is section_list
    assert section_list.name == "New Name"
    assert section_list.description == "New description."


def test_set_archived(
    db: Session,
) -> None:
    _, section = _create_section(
        db,
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    SectionListRepository.set_archived(
        db,
        section_list=section_list,
        is_archived=True,
    )

    assert section_list.is_archived is True


def test_update_sort_position(
    db: Session,
) -> None:
    _, section = _create_section(
        db,
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    SectionListRepository.update_sort_position(
        db,
        section_list=section_list,
        sort_position=2500,
    )

    assert section_list.sort_position == 2500


def test_update_sort_positions(
    db: Session,
) -> None:
    _, section = _create_section(
        db,
    )

    first = create_section_list(
        db,
        section=section,
        sort_position=1000,
    )

    second = create_section_list(
        db,
        section=section,
        sort_position=2000,
    )

    SectionListRepository.update_sort_positions(
        db,
        positions={
            first.id: 4000,
            second.id: 1000,
        },
    )

    assert first.sort_position == 4000
    assert second.sort_position == 1000


def test_delete_section_list(
    db: Session,
) -> None:
    _, section = _create_section(
        db,
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    section_list_id = section_list.id

    SectionListRepository.delete(
        db,
        section_list=section_list,
    )

    assert (
        SectionListRepository.get_by_id(
            db,
            section_list_id=section_list_id,
        )
        is None
    )