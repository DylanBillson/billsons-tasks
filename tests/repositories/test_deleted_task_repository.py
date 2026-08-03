from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.timezone import utc_now
from app.repositories.task_repository import TaskRepository
from tests.factories import (
    create_company,
    create_section,
    create_section_list,
    create_task,
    create_user,
)


def _create_deleted_task(
    db: Session,
    *,
    company_name: str,
    section_name: str,
    list_name: str,
    title: str,
    description: str | None = None,
    deleted_by=None,
    deleted_at=None,
):
    creator = create_user(
        db,
    )

    company = create_company(
        db,
        name=company_name,
    )

    section = create_section(
        db,
        company=company,
        created_by=creator,
        name=section_name,
    )

    section_list = create_section_list(
        db,
        section=section,
        name=list_name,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title=title,
        description=description,
        deleted_by=deleted_by or creator,
    )

    if deleted_at is not None:
        task.deleted_at = deleted_at
        db.flush()

    return (
        creator,
        company,
        section,
        section_list,
        task,
    )


def test_list_all_deleted_returns_only_deleted_tasks(
    db: Session,
) -> None:
    (
        creator,
        _,
        _,
        section_list,
        deleted,
    ) = _create_deleted_task(
        db,
        company_name="Deleted Company",
        section_name="Deleted Section",
        list_name="Deleted List",
        title="Deleted Task",
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Active Task",
    )

    result = TaskRepository.list_all_deleted(
        db,
    )

    assert result == [
        deleted,
    ]


def test_list_all_deleted_searches_task_and_location(
    db: Session,
) -> None:
    _, _, _, _, title_match = _create_deleted_task(
        db,
        company_name="First Company",
        section_name="Operations",
        list_name="To Do",
        title="Order coffee",
    )

    _, _, _, _, company_match = _create_deleted_task(
        db,
        company_name="Coffee Company",
        section_name="Kitchen",
        list_name="Backlog",
        title="Clean shelves",
    )

    _create_deleted_task(
        db,
        company_name="Other Company",
        section_name="Cellar",
        list_name="Later",
        title="Count bottles",
    )

    result = TaskRepository.list_all_deleted(
        db,
        search="coffee",
    )

    assert set(
        result,
    ) == {
        title_match,
        company_match,
    }


def test_list_all_deleted_filters_by_company_and_section(
    db: Session,
) -> None:
    (
        _,
        company,
        section,
        _,
        matching,
    ) = _create_deleted_task(
        db,
        company_name="Matching Company",
        section_name="Matching Section",
        list_name="To Do",
        title="Matching Task",
    )

    _create_deleted_task(
        db,
        company_name="Other Company",
        section_name="Other Section",
        list_name="To Do",
        title="Other Task",
    )

    result = TaskRepository.list_all_deleted(
        db,
        company_id=company.id,
        section_id=section.id,
    )

    assert result == [
        matching,
    ]


def test_list_all_deleted_filters_by_deleting_user(
    db: Session,
) -> None:
    deleting_user = create_user(
        db,
    )

    _, _, _, _, matching = _create_deleted_task(
        db,
        company_name="First Company",
        section_name="First Section",
        list_name="To Do",
        title="Matching Task",
        deleted_by=deleting_user,
    )

    _create_deleted_task(
        db,
        company_name="Second Company",
        section_name="Second Section",
        list_name="To Do",
        title="Other Task",
    )

    result = TaskRepository.list_all_deleted(
        db,
        deleted_by_user_id=deleting_user.id,
    )

    assert result == [
        matching,
    ]


def test_list_all_deleted_filters_by_date_range(
    db: Session,
) -> None:
    now = utc_now()

    _, _, _, _, matching = _create_deleted_task(
        db,
        company_name="Matching Company",
        section_name="Matching Section",
        list_name="To Do",
        title="Matching Task",
        deleted_at=now - timedelta(
            days=2,
        ),
    )

    _create_deleted_task(
        db,
        company_name="Old Company",
        section_name="Old Section",
        list_name="To Do",
        title="Old Task",
        deleted_at=now - timedelta(
            days=20,
        ),
    )

    result = TaskRepository.list_all_deleted(
        db,
        deleted_from=now - timedelta(
            days=5,
        ),
        deleted_to=now,
    )

    assert result == [
        matching,
    ]


def test_count_and_list_deleted_support_pagination(
    db: Session,
) -> None:
    now = utc_now()

    _, _, _, _, newest = _create_deleted_task(
        db,
        company_name="Newest Company",
        section_name="Newest Section",
        list_name="To Do",
        title="Newest Task",
        deleted_at=now,
    )

    _, _, _, _, older = _create_deleted_task(
        db,
        company_name="Older Company",
        section_name="Older Section",
        list_name="To Do",
        title="Older Task",
        deleted_at=now - timedelta(
            days=1,
        ),
    )

    result = TaskRepository.list_all_deleted(
        db,
        limit=1,
        offset=1,
    )

    count = TaskRepository.count_all_deleted(
        db,
    )

    assert result == [
        older,
    ]

    assert newest not in result
    assert count == 2