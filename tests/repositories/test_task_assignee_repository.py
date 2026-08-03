from sqlalchemy.orm import Session

from app.repositories.task_assignee_repository import (
    TaskAssigneeRepository,
)
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

    return creator, task


def test_get_by_id(
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

    result = TaskAssigneeRepository.get_by_id(
        db,
        task_assignee_id=assignment.id,
    )

    assert result is assignment
    assert result.task is task
    assert result.user is user


def test_get_by_task_and_user(
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

    result = (
        TaskAssigneeRepository.get_by_task_and_user(
            db,
            task_id=task.id,
            user_id=user.id,
        )
    )

    assert result is assignment


def test_get_by_task_and_user_returns_none(
    db: Session,
) -> None:
    _, task = _create_task(
        db,
    )

    user = create_user(
        db,
    )

    result = (
        TaskAssigneeRepository.get_by_task_and_user(
            db,
            task_id=task.id,
            user_id=user.id,
        )
    )

    assert result is None


def test_exists(
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

    assert TaskAssigneeRepository.exists(
        db,
        task_id=task.id,
        user_id=user.id,
    ) is True


def test_exists_returns_false(
    db: Session,
) -> None:
    _, task = _create_task(
        db,
    )

    user = create_user(
        db,
    )

    assert TaskAssigneeRepository.exists(
        db,
        task_id=task.id,
        user_id=user.id,
    ) is False


def test_list_for_task_orders_by_user_name(
    db: Session,
) -> None:
    _, task = _create_task(
        db,
    )

    charlie = create_user(
        db,
        display_name="Charlie",
    )

    alice = create_user(
        db,
        display_name="Alice",
    )

    bob = create_user(
        db,
        display_name="Bob",
    )

    charlie_assignment = create_task_assignee(
        db,
        task=task,
        user=charlie,
    )

    alice_assignment = create_task_assignee(
        db,
        task=task,
        user=alice,
    )

    bob_assignment = create_task_assignee(
        db,
        task=task,
        user=bob,
    )

    result = TaskAssigneeRepository.list_for_task(
        db,
        task_id=task.id,
    )

    assert result == [
        alice_assignment,
        bob_assignment,
        charlie_assignment,
    ]


def test_list_for_user(
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

    result = TaskAssigneeRepository.list_for_user(
        db,
        user_id=user.id,
    )

    assert set(result) == {
        first_assignment,
        second_assignment,
    }


def test_create_assignment(
    db: Session,
) -> None:
    _, task = _create_task(
        db,
    )

    user = create_user(
        db,
    )

    assignment = TaskAssigneeRepository.create(
        db,
        task_id=task.id,
        user_id=user.id,
    )

    assert assignment.id is not None
    assert assignment.task_id == task.id
    assert assignment.user_id == user.id


def test_delete_assignment(
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

    TaskAssigneeRepository.delete(
        db,
        assignment=assignment,
    )

    assert (
        TaskAssigneeRepository.get_by_task_and_user(
            db,
            task_id=task.id,
            user_id=user.id,
        )
        is None
    )


def test_delete_all_for_task_except(
    db: Session,
) -> None:
    _, task = _create_task(
        db,
    )

    retained_user = create_user(
        db,
    )

    removed_user = create_user(
        db,
    )

    retained = create_task_assignee(
        db,
        task=task,
        user=retained_user,
    )

    create_task_assignee(
        db,
        task=task,
        user=removed_user,
    )

    removed_ids = (
        TaskAssigneeRepository.delete_all_for_task_except(
            db,
            task_id=task.id,
            retained_user_ids={
                retained_user.id,
            },
        )
    )

    assert removed_ids == [
        removed_user.id,
    ]

    assert (
        TaskAssigneeRepository.list_for_task(
            db,
            task_id=task.id,
        )
        == [
            retained,
        ]
    )