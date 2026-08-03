import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.factories import (
    create_company,
    create_section,
    create_section_list,
    create_task,
    create_task_assignee,
    create_user,
)


def _create_task(
    db: Session,
):
    creator = create_user(
        db,
    )

    task = create_task(
        db,
        section_list=create_section_list(
            db,
            section=create_section(
                db,
                company=create_company(
                    db,
                ),
                created_by=creator,
            ),
        ),
        created_by=creator,
    )

    return (
        creator,
        task,
    )


def test_task_assignee_relationships(
    db: Session,
) -> None:
    _, task = _create_task(
        db,
    )

    user = create_user(
        db,
    )

    assignment = create_task_assignee(
        db,
        task=task,
        user=user,
    )

    assert assignment.task_id == task.id
    assert assignment.user_id == user.id
    assert assignment.task is task
    assert assignment.user is user
    assert assignment in task.assignees
    assert assignment in user.task_assignments


def test_task_can_have_multiple_assignees(
    db: Session,
) -> None:
    _, task = _create_task(
        db,
    )

    first_user = create_user(
        db,
    )

    second_user = create_user(
        db,
    )

    first = create_task_assignee(
        db,
        task=task,
        user=first_user,
    )

    second = create_task_assignee(
        db,
        task=task,
        user=second_user,
    )

    assert first in task.assignees
    assert second in task.assignees
    assert len(task.assignees) == 2


def test_user_can_be_assigned_to_multiple_tasks(
    db: Session,
) -> None:
    creator, first_task = _create_task(
        db,
    )

    second_task = create_task(
        db,
        section_list=first_task.section_list,
        created_by=creator,
    )

    user = create_user(
        db,
    )

    first_assignment = create_task_assignee(
        db,
        task=first_task,
        user=user,
    )

    second_assignment = create_task_assignee(
        db,
        task=second_task,
        user=user,
    )

    assert first_assignment in user.task_assignments
    assert second_assignment in user.task_assignments
    assert len(user.task_assignments) == 2


def test_duplicate_task_assignee_is_rejected(
    db: Session,
) -> None:
    _, task = _create_task(
        db,
    )

    user = create_user(
        db,
    )

    create_task_assignee(
        db,
        task=task,
        user=user,
    )

    with pytest.raises(
        IntegrityError,
    ):
        create_task_assignee(
            db,
            task=task,
            user=user,
        )


def test_task_assignee_repr(
    db: Session,
) -> None:
    _, task = _create_task(
        db,
    )

    user = create_user(
        db,
    )

    assignment = create_task_assignee(
        db,
        task=task,
        user=user,
    )

    representation = repr(
        assignment,
    )

    assert "TaskAssignee" in representation
    assert f"id={assignment.id!r}" in representation
    assert f"task_id={task.id!r}" in representation
    assert f"user_id={user.id!r}" in representation