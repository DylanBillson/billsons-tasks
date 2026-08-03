from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.timezone import utc_now
from tests.factories import (
    create_company,
    create_section,
    create_section_list,
    create_task,
    create_user,
)


def _create_task_context(
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

    section_list = create_section_list(
        db,
        section=section,
    )

    return (
        creator,
        section,
        section_list,
    )


def test_task_defaults(
    db: Session,
) -> None:
    (
        creator,
        section,
        section_list,
    ) = _create_task_context(
        db,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
    )

    assert task.id is not None
    assert task.section_list_id == section_list.id
    assert task.created_by_user_id == creator.id
    assert task.title.startswith(
        "Test Task ",
    )
    assert task.description is None
    assert task.due_at is None
    assert task.completed_at is None
    assert task.completed_by_user_id is None
    assert task.sort_position == 1000
    assert task.deleted_at is None
    assert task.deleted_by_user_id is None
    assert task.section_id == section.id
    assert task.is_completed is False
    assert task.is_deleted is False
    assert task.is_overdue is False
    assert task.state == "open"


def test_task_relationships(
    db: Session,
) -> None:
    (
        creator,
        _,
        section_list,
    ) = _create_task_context(
        db,
    )

    completer = create_user(
        db,
    )

    deleter = create_user(
        db,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        completed_by=completer,
        deleted_by=deleter,
    )

    assert task.section_list is section_list
    assert task in section_list.tasks

    assert task.created_by is creator
    assert task in creator.created_tasks

    assert task.completed_by is completer
    assert task in completer.completed_tasks

    assert task.deleted_by is deleter
    assert task in deleter.deleted_tasks


def test_completed_task_state(
    db: Session,
) -> None:
    creator, _, section_list = _create_task_context(
        db,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        completed_by=creator,
    )

    assert task.completed_at is not None
    assert task.completed_by_user_id == creator.id
    assert task.is_completed is True
    assert task.is_overdue is False
    assert task.state == "completed"


def test_deleted_task_state_takes_precedence(
    db: Session,
) -> None:
    creator, _, section_list = _create_task_context(
        db,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        completed_by=creator,
        deleted_by=creator,
    )

    assert task.is_completed is True
    assert task.is_deleted is True
    assert task.is_overdue is False
    assert task.state == "deleted"


def test_overdue_task_state(
    db: Session,
) -> None:
    creator, _, section_list = _create_task_context(
        db,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        due_at=(
            utc_now()
            - timedelta(
                hours=1,
            )
        ),
    )

    assert task.is_overdue is True
    assert task.state == "overdue"


def test_future_task_is_not_overdue(
    db: Session,
) -> None:
    creator, _, section_list = _create_task_context(
        db,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        due_at=(
            utc_now()
            + timedelta(
                days=1,
            )
        ),
    )

    assert task.is_overdue is False
    assert task.state == "open"


def test_task_completion_fields_must_be_consistent(
    db: Session,
) -> None:
    creator, _, section_list = _create_task_context(
        db,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
    )

    task.completed_by = creator
    task.completed_at = None

    with pytest.raises(
        IntegrityError,
    ):
        db.flush()


def test_task_deletion_fields_must_be_consistent(
    db: Session,
) -> None:
    creator, _, section_list = _create_task_context(
        db,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
    )

    task.deleted_by = creator
    task.deleted_at = None

    with pytest.raises(
        IntegrityError,
    ):
        db.flush()


def test_negative_task_position_is_rejected(
    db: Session,
) -> None:
    creator, _, section_list = _create_task_context(
        db,
    )

    with pytest.raises(
        IntegrityError,
    ):
        create_task(
            db,
            section_list=section_list,
            created_by=creator,
            sort_position=-1,
        )


def test_task_repr(
    db: Session,
) -> None:
    creator, _, section_list = _create_task_context(
        db,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Order supplies",
        sort_position=2000,
    )

    representation = repr(
        task,
    )

    assert "Task" in representation
    assert f"id={task.id!r}" in representation
    assert f"section_list_id={section_list.id!r}" in representation
    assert "title='Order supplies'" in representation
    assert "sort_position=2000" in representation
    assert "state='open'" in representation