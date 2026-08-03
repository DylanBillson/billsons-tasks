from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from app.auth.permissions import PermissionDeniedError
from app.core.timezone import utc_now
from app.services.task_service import (
    DeletedTaskFilterError,
    TaskService,
)
from tests.factories import (
    create_administrator,
    create_company,
    create_section,
    create_section_list,
    create_task,
    create_user,
)


def _create_deleted_task(
    db: Session,
    *,
    title: str = "Deleted Service Task",
):
    creator = create_user(
        db,
    )

    company = create_company(
        db,
    )

    section = create_section(
        db,
        company=company,
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
        title=title,
        deleted_by=creator,
    )

    return (
        creator,
        company,
        section,
        task,
    )


def test_administrator_lists_deleted_tasks(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    _, _, _, task = _create_deleted_task(
        db,
    )

    tasks, total_items = TaskService.list_deleted_tasks(
        db,
        actor=administrator,
    )

    assert tasks == [
        task,
    ]

    assert total_items == 1


def test_standard_user_cannot_list_deleted_tasks(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    with pytest.raises(
        PermissionDeniedError,
    ):
        TaskService.list_deleted_tasks(
            db,
            actor=user,
        )


def test_deleted_task_service_applies_search_filter(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    _, _, _, matching = _create_deleted_task(
        db,
        title="Order coffee",
    )

    _create_deleted_task(
        db,
        title="Clean cellar",
    )

    tasks, total_items = TaskService.list_deleted_tasks(
        db,
        actor=administrator,
        search="coffee",
    )

    assert tasks == [
        matching,
    ]

    assert total_items == 1


def test_deleted_task_service_supports_pagination(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    _, _, _, first = _create_deleted_task(
        db,
        title="First",
    )

    _, _, _, second = _create_deleted_task(
        db,
        title="Second",
    )

    first.deleted_at = utc_now()
    second.deleted_at = utc_now() - timedelta(
        days=1,
    )

    db.flush()

    tasks, total_items = TaskService.list_deleted_tasks(
        db,
        actor=administrator,
        page=2,
        page_size=1,
    )

    assert tasks == [
        second,
    ]

    assert first not in tasks
    assert total_items == 2


@pytest.mark.parametrize(
    (
        "page",
        "page_size",
    ),
    [
        (
            0,
            25,
        ),
        (
            1,
            0,
        ),
        (
            1,
            101,
        ),
    ],
)
def test_deleted_task_service_rejects_invalid_pagination(
    db: Session,
    page: int,
    page_size: int,
) -> None:
    administrator = create_administrator(
        db,
    )

    with pytest.raises(
        DeletedTaskFilterError,
    ):
        TaskService.list_deleted_tasks(
            db,
            actor=administrator,
            page=page,
            page_size=page_size,
        )


def test_deleted_task_service_rejects_reversed_date_range(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    now = utc_now()

    with pytest.raises(
        DeletedTaskFilterError,
        match="start date",
    ):
        TaskService.list_deleted_tasks(
            db,
            actor=administrator,
            deleted_from=now,
            deleted_to=now - timedelta(
                days=1,
            ),
        )