from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.timezone import utc_now
from app.repositories.task_repository import TaskRepository
from tests.factories import (
    create_company,
    create_section,
    create_section_list,
    create_task,
    create_task_assignee,
    create_user,
)


def _create_context(
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

    first_list = create_section_list(
        db,
        section=section,
        name="To Do",
        sort_position=1000,
    )

    second_list = create_section_list(
        db,
        section=section,
        name="Done",
        sort_position=2000,
    )

    return creator, section, first_list, second_list


def test_get_by_id_returns_task_with_relationships(
    db: Session,
) -> None:
    creator, _, section_list, _ = _create_context(
        db,
    )

    assignee = create_user(
        db,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
    )

    assignment = create_task_assignee(
        db,
        task=task,
        user=assignee,
    )

    result = TaskRepository.get_by_id(
        db,
        task_id=task.id,
    )

    assert result is task
    assert result.section_list is section_list
    assert result.created_by is creator
    assert assignment in result.assignees


def test_get_by_id_returns_none_for_unknown_task(
    db: Session,
) -> None:
    assert (
        TaskRepository.get_by_id(
            db,
            task_id=999999,
        )
        is None
    )


def test_list_for_list_orders_by_position(
    db: Session,
) -> None:
    creator, _, section_list, _ = _create_context(
        db,
    )

    later = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        sort_position=3000,
    )

    first = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        sort_position=1000,
    )

    result = TaskRepository.list_for_list(
        db,
        section_list_id=section_list.id,
    )

    assert result == [
        first,
        later,
    ]


def test_list_for_list_excludes_deleted_by_default(
    db: Session,
) -> None:
    creator, _, section_list, _ = _create_context(
        db,
    )

    active = create_task(
        db,
        section_list=section_list,
        created_by=creator,
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
        deleted_by=creator,
        sort_position=2000,
    )

    result = TaskRepository.list_for_list(
        db,
        section_list_id=section_list.id,
    )

    assert result == [
        active,
    ]


def test_list_for_list_can_include_deleted(
    db: Session,
) -> None:
    creator, _, section_list, _ = _create_context(
        db,
    )

    active = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        sort_position=1000,
    )

    deleted = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        deleted_by=creator,
        sort_position=2000,
    )

    result = TaskRepository.list_for_list(
        db,
        section_list_id=section_list.id,
        include_deleted=True,
    )

    assert result == [
        active,
        deleted,
    ]


def test_list_for_section_orders_by_list_and_task_position(
    db: Session,
) -> None:
    creator, section, first_list, second_list = _create_context(
        db,
    )

    second_list_task = create_task(
        db,
        section_list=second_list,
        created_by=creator,
        sort_position=1000,
    )

    first_list_later = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        sort_position=2000,
    )

    first_list_first = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        sort_position=1000,
    )

    result = TaskRepository.list_for_section(
        db,
        section_id=section.id,
    )

    assert result == [
        first_list_first,
        first_list_later,
        second_list_task,
    ]


def test_list_for_section_filters_by_list(
    db: Session,
) -> None:
    creator, section, first_list, second_list = _create_context(
        db,
    )

    first_task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    create_task(
        db,
        section_list=second_list,
        created_by=creator,
    )

    result = TaskRepository.list_for_section(
        db,
        section_id=section.id,
        section_list_id=first_list.id,
    )

    assert result == [
        first_task,
    ]


def test_list_for_section_filters_by_assignee(
    db: Session,
) -> None:
    creator, section, first_list, _ = _create_context(
        db,
    )

    assignee = create_user(
        db,
    )

    assigned = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    unassigned = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    create_task_assignee(
        db,
        task=assigned,
        user=assignee,
    )

    result = TaskRepository.list_for_section(
        db,
        section_id=section.id,
        assignee_user_id=assignee.id,
    )

    assert assigned in result
    assert unassigned not in result


def test_list_for_section_filters_by_search(
    db: Session,
) -> None:
    creator, section, first_list, _ = _create_context(
        db,
    )

    title_match = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        title="Order coffee beans",
    )

    description_match = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        title="Call supplier",
        description="Ask about the coffee delivery.",
    )

    create_task(
        db,
        section_list=first_list,
        created_by=creator,
        title="Clean cellar",
    )

    result = TaskRepository.list_for_section(
        db,
        section_id=section.id,
        search="coffee",
    )

    assert set(result) == {
        title_match,
        description_match,
    }


def test_list_for_section_filters_open_tasks(
    db: Session,
) -> None:
    creator, section, first_list, _ = _create_context(
        db,
    )

    open_task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    create_task(
        db,
        section_list=first_list,
        created_by=creator,
        completed_by=creator,
    )

    create_task(
        db,
        section_list=first_list,
        created_by=creator,
        deleted_by=creator,
    )

    result = TaskRepository.list_for_section(
        db,
        section_id=section.id,
        state="open",
    )

    assert result == [
        open_task,
    ]


def test_list_for_section_filters_completed_tasks(
    db: Session,
) -> None:
    creator, section, first_list, _ = _create_context(
        db,
    )

    completed = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        completed_by=creator,
    )

    create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    result = TaskRepository.list_for_section(
        db,
        section_id=section.id,
        state="completed",
    )

    assert result == [
        completed,
    ]


def test_list_for_section_filters_overdue_tasks(
    db: Session,
) -> None:
    creator, section, first_list, _ = _create_context(
        db,
    )

    overdue = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        due_at=utc_now() - timedelta(
            hours=1,
        ),
    )

    create_task(
        db,
        section_list=first_list,
        created_by=creator,
        due_at=utc_now() + timedelta(
            days=1,
        ),
    )

    result = TaskRepository.list_for_section(
        db,
        section_id=section.id,
        state="overdue",
    )

    assert result == [
        overdue,
    ]


def test_list_for_section_filters_deleted_tasks(
    db: Session,
) -> None:
    creator, section, first_list, _ = _create_context(
        db,
    )

    deleted = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        deleted_by=creator,
    )

    create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    result = TaskRepository.list_for_section(
        db,
        section_id=section.id,
        state="deleted",
    )

    assert result == [
        deleted,
    ]


def test_list_for_section_filters_due_range(
    db: Session,
) -> None:
    creator, section, first_list, _ = _create_context(
        db,
    )

    now = utc_now()

    included = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        due_at=now + timedelta(
            days=2,
        ),
    )

    create_task(
        db,
        section_list=first_list,
        created_by=creator,
        due_at=now + timedelta(
            days=10,
        ),
    )

    result = TaskRepository.list_for_section(
        db,
        section_id=section.id,
        due_from=now + timedelta(
            days=1,
        ),
        due_to=now + timedelta(
            days=3,
        ),
    )

    assert result == [
        included,
    ]


def test_list_assigned_to_user(
    db: Session,
) -> None:
    creator, _, first_list, _ = _create_context(
        db,
    )

    assignee = create_user(
        db,
    )

    assigned = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    unassigned = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    create_task_assignee(
        db,
        task=assigned,
        user=assignee,
    )

    result = TaskRepository.list_assigned_to_user(
        db,
        user_id=assignee.id,
    )

    assert assigned in result
    assert unassigned not in result


def test_list_deleted_for_section(
    db: Session,
) -> None:
    creator, section, first_list, _ = _create_context(
        db,
    )

    deleted = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        deleted_by=creator,
    )

    create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    result = TaskRepository.list_deleted_for_section(
        db,
        section_id=section.id,
    )

    assert result == [
        deleted,
    ]


def test_get_next_sort_position(
    db: Session,
) -> None:
    creator, _, first_list, _ = _create_context(
        db,
    )

    create_task(
        db,
        section_list=first_list,
        created_by=creator,
        sort_position=3000,
    )

    position = TaskRepository.get_next_sort_position(
        db,
        section_list_id=first_list.id,
    )

    assert position == 4000


def test_create_task_uses_next_sort_position(
    db: Session,
) -> None:
    creator, _, first_list, _ = _create_context(
        db,
    )

    create_task(
        db,
        section_list=first_list,
        created_by=creator,
        sort_position=2000,
    )

    task = TaskRepository.create(
        db,
        section_list_id=first_list.id,
        created_by_user_id=creator.id,
        title="New task",
    )

    assert task.sort_position == 3000


def test_update_task(
    db: Session,
) -> None:
    creator, _, first_list, _ = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    due_at = utc_now() + timedelta(
        days=2,
    )

    TaskRepository.update(
        db,
        task=task,
        title="Updated task",
        description="Updated description.",
        due_at=due_at,
    )

    assert task.title == "Updated task"
    assert task.description == "Updated description."
    assert task.due_at == due_at


def test_move_task(
    db: Session,
) -> None:
    creator, _, first_list, second_list = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    TaskRepository.move(
        db,
        task=task,
        section_list_id=second_list.id,
        sort_position=500,
    )

    assert task.section_list_id == second_list.id
    assert task.sort_position == 500


def test_complete_and_reopen_task(
    db: Session,
) -> None:
    creator, _, first_list, _ = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    TaskRepository.set_completed(
        db,
        task=task,
        completed_by_user_id=creator.id,
    )

    assert task.completed_at is not None
    assert task.completed_by_user_id == creator.id

    TaskRepository.set_reopened(
        db,
        task=task,
    )

    assert task.completed_at is None
    assert task.completed_by_user_id is None


def test_soft_delete_and_restore_task(
    db: Session,
) -> None:
    creator, _, first_list, _ = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    TaskRepository.soft_delete(
        db,
        task=task,
        deleted_by_user_id=creator.id,
    )

    assert task.deleted_at is not None
    assert task.deleted_by_user_id == creator.id

    TaskRepository.restore(
        db,
        task=task,
    )

    assert task.deleted_at is None
    assert task.deleted_by_user_id is None


def test_update_positions(
    db: Session,
) -> None:
    creator, _, first_list, second_list = _create_context(
        db,
    )

    first_task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    second_task = create_task(
        db,
        section_list=second_list,
        created_by=creator,
    )

    TaskRepository.update_positions(
        db,
        positions={
            first_task.id: (
                second_list.id,
                2000,
            ),
            second_task.id: (
                first_list.id,
                1000,
            ),
        },
    )

    assert first_task.section_list_id == second_list.id
    assert first_task.sort_position == 2000
    assert second_task.section_list_id == first_list.id
    assert second_task.sort_position == 1000


def test_permanently_delete_task(
    db: Session,
) -> None:
    creator, _, first_list, _ = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    task_id = task.id

    TaskRepository.permanently_delete(
        db,
        task=task,
    )

    assert (
        TaskRepository.get_by_id(
            db,
            task_id=task_id,
        )
        is None
    )