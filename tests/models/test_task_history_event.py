from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.constants import TaskHistoryEventType
from app.core.timezone import utc_now
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

    return (
        creator,
        task,
    )


def test_task_history_event_defaults(
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

    assert event.id is not None
    assert event.task_id == task.id
    assert event.user_id == user.id
    assert event.event_type == TaskHistoryEventType.CREATED.value
    assert event.summary == "Test task history event."
    assert event.metadata_json == {}
    assert event.created_at is not None


def test_task_history_event_accepts_custom_values(
    db: Session,
) -> None:
    user, task = _create_task(
        db,
    )

    event = create_task_history_event(
        db,
        task=task,
        user=user,
        event_type=TaskHistoryEventType.MOVED,
        summary="Task moved to In Progress.",
        metadata_json={
            "previous_list_id": 1,
            "section_list_id": 2,
        },
    )

    assert event.event_type == TaskHistoryEventType.MOVED.value
    assert event.summary == "Task moved to In Progress."
    assert event.metadata_json == {
        "previous_list_id": 1,
        "section_list_id": 2,
    }


def test_task_history_event_relationships(
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

    assert event.task is task
    assert event in task.history_events

    assert event.user is user
    assert event in user.task_history_events


def test_task_history_event_allows_system_event(
    db: Session,
) -> None:
    _, task = _create_task(
        db,
    )

    event = create_task_history_event(
        db,
        task=task,
        user=None,
        event_type=TaskHistoryEventType.UPDATED,
        summary="Task updated automatically.",
    )

    assert event.user is None
    assert event.user_id is None


def test_task_history_events_are_ordered_newest_first(
    db: Session,
) -> None:
    user, task = _create_task(
        db,
    )

    now = utc_now()

    older = create_task_history_event(
        db,
        task=task,
        user=user,
        summary="Older event.",
        created_at=(
            now
            - timedelta(
                minutes=10,
            )
        ),
    )

    newer = create_task_history_event(
        db,
        task=task,
        user=user,
        summary="Newer event.",
        created_at=now,
    )

    db.expire(
        task,
        [
            "history_events",
        ],
    )

    assert task.history_events == [
        newer,
        older,
    ]


def test_task_history_event_has_no_updated_at(
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

    assert not hasattr(
        event,
        "updated_at",
    )


def test_task_history_event_repr(
    db: Session,
) -> None:
    user, task = _create_task(
        db,
    )

    event = create_task_history_event(
        db,
        task=task,
        user=user,
        event_type=TaskHistoryEventType.COMPLETED,
    )

    representation = repr(
        event,
    )

    assert "TaskHistoryEvent" in representation
    assert f"id={event.id!r}" in representation
    assert f"task_id={task.id!r}" in representation
    assert f"user_id={user.id!r}" in representation
    assert "event_type='completed'" in representation