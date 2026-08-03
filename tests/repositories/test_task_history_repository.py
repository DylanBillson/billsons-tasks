from sqlalchemy.orm import Session

from app.core.constants import TaskHistoryEventType
from app.repositories.task_history_repository import (
    TaskHistoryRepository,
)
from tests.factories import (
    create_company,
    create_section,
    create_section_list,
    create_task,
    create_task_history_event,
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
    user, task = _create_task(
        db,
    )

    event = create_task_history_event(
        db,
        task=task,
        user=user,
    )

    result = TaskHistoryRepository.get_by_id(
        db,
        history_event_id=event.id,
    )

    assert result is event
    assert result.task is task
    assert result.user is user


def test_get_by_id_returns_none(
    db: Session,
) -> None:
    assert TaskHistoryRepository.get_by_id(
        db,
        history_event_id=999999,
    ) is None


def test_list_for_task_orders_newest_first(
    db: Session,
) -> None:
    user, task = _create_task(
        db,
    )

    older = create_task_history_event(
        db,
        task=task,
        user=user,
        summary="Older event.",
    )

    newer = create_task_history_event(
        db,
        task=task,
        user=user,
        summary="Newer event.",
    )

    result = TaskHistoryRepository.list_for_task(
        db,
        task_id=task.id,
    )

    assert result == [
        newer,
        older,
    ]


def test_list_for_task_supports_limit_and_offset(
    db: Session,
) -> None:
    user, task = _create_task(
        db,
    )

    first = create_task_history_event(
        db,
        task=task,
        user=user,
        summary="First.",
    )

    second = create_task_history_event(
        db,
        task=task,
        user=user,
        summary="Second.",
    )

    third = create_task_history_event(
        db,
        task=task,
        user=user,
        summary="Third.",
    )

    result = TaskHistoryRepository.list_for_task(
        db,
        task_id=task.id,
        limit=1,
        offset=1,
    )

    assert result == [
        second,
    ]

    assert first is not result[0]
    assert third is not result[0]


def test_create_history_event(
    db: Session,
) -> None:
    user, task = _create_task(
        db,
    )

    event = TaskHistoryRepository.create(
        db,
        task_id=task.id,
        user_id=user.id,
        event_type=TaskHistoryEventType.MOVED.value,
        summary="Moved to In Progress.",
        metadata_json={
            "section_list_id": 123,
        },
    )

    assert event.task_id == task.id
    assert event.user_id == user.id
    assert event.event_type == "moved"
    assert event.summary == "Moved to In Progress."
    assert event.metadata_json == {
        "section_list_id": 123,
    }


def test_create_history_event_defaults_metadata(
    db: Session,
) -> None:
    _, task = _create_task(
        db,
    )

    event = TaskHistoryRepository.create(
        db,
        task_id=task.id,
        event_type=TaskHistoryEventType.UPDATED.value,
        summary="Updated automatically.",
    )

    assert event.user_id is None
    assert event.metadata_json == {}


def test_delete_for_task(
    db: Session,
) -> None:
    user, task = _create_task(
        db,
    )

    first = create_task_history_event(
        db,
        task=task,
        user=user,
    )

    second = create_task_history_event(
        db,
        task=task,
        user=user,
    )

    deleted_count = TaskHistoryRepository.delete_for_task(
        db,
        task_id=task.id,
    )

    assert deleted_count == 2

    assert TaskHistoryRepository.get_by_id(
        db,
        history_event_id=first.id,
    ) is None

    assert TaskHistoryRepository.get_by_id(
        db,
        history_event_id=second.id,
    ) is None