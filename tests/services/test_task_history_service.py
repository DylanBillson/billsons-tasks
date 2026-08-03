import pytest
from sqlalchemy.orm import Session

from app.core.constants import TaskHistoryEventType
from app.repositories.task_history_repository import (
    TaskHistoryRepository,
)
from app.services.task_history_service import (
    TaskHistoryEventNotFoundError,
    TaskHistoryService,
    TaskHistoryServiceError,
)
from tests.factories import (
    create_company,
    create_section,
    create_section_list,
    create_task,
    create_task_history_event,
    create_user,
)


def _create_context(
    db: Session,
):
    actor = create_user(
        db,
        display_name="Task History Actor",
    )

    company = create_company(
        db,
    )

    section = create_section(
        db,
        company=company,
        created_by=actor,
    )

    section_list = create_section_list(
        db,
        section=section,
        name="To Do",
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=actor,
        title="Test the task history",
    )

    return (
        actor,
        task,
    )


def test_get_event_returns_existing_event(
    db: Session,
) -> None:
    actor, task = _create_context(
        db,
    )

    event = create_task_history_event(
        db,
        task=task,
        user=actor,
    )

    result = TaskHistoryService.get_event(
        db,
        history_event_id=event.id,
    )

    assert result is event


def test_get_event_returns_none_for_unknown_event(
    db: Session,
) -> None:
    result = TaskHistoryService.get_event(
        db,
        history_event_id=999999,
    )

    assert result is None


def test_require_event_returns_existing_event(
    db: Session,
) -> None:
    actor, task = _create_context(
        db,
    )

    event = create_task_history_event(
        db,
        task=task,
        user=actor,
    )

    result = TaskHistoryService.require_event(
        db,
        history_event_id=event.id,
    )

    assert result is event


def test_require_event_raises_for_unknown_event(
    db: Session,
) -> None:
    with pytest.raises(
        TaskHistoryEventNotFoundError,
        match="Task history event was not found",
    ):
        TaskHistoryService.require_event(
            db,
            history_event_id=999999,
        )


def test_list_for_task_returns_events_newest_first(
    db: Session,
) -> None:
    actor, task = _create_context(
        db,
    )

    first = create_task_history_event(
        db,
        task=task,
        user=actor,
        summary="First event.",
    )

    second = create_task_history_event(
        db,
        task=task,
        user=actor,
        summary="Second event.",
    )

    result = TaskHistoryService.list_for_task(
        db,
        task=task,
    )

    assert result == [
        second,
        first,
    ]


def test_list_for_task_applies_limit_and_offset(
    db: Session,
) -> None:
    actor, task = _create_context(
        db,
    )

    first = create_task_history_event(
        db,
        task=task,
        user=actor,
        summary="First event.",
    )

    second = create_task_history_event(
        db,
        task=task,
        user=actor,
        summary="Second event.",
    )

    third = create_task_history_event(
        db,
        task=task,
        user=actor,
        summary="Third event.",
    )

    result = TaskHistoryService.list_for_task(
        db,
        task=task,
        limit=1,
        offset=1,
    )

    assert result == [
        second,
    ]

    assert result[0] is not first
    assert result[0] is not third


def test_list_for_task_normalises_non_positive_limit(
    db: Session,
) -> None:
    actor, task = _create_context(
        db,
    )

    create_task_history_event(
        db,
        task=task,
        user=actor,
        summary="First event.",
    )

    second = create_task_history_event(
        db,
        task=task,
        user=actor,
        summary="Second event.",
    )

    result = TaskHistoryService.list_for_task(
        db,
        task=task,
        limit=0,
    )

    assert result == [
        second,
    ]


def test_list_for_task_normalises_negative_offset(
    db: Session,
) -> None:
    actor, task = _create_context(
        db,
    )

    first = create_task_history_event(
        db,
        task=task,
        user=actor,
        summary="First event.",
    )

    second = create_task_history_event(
        db,
        task=task,
        user=actor,
        summary="Second event.",
    )

    result = TaskHistoryService.list_for_task(
        db,
        task=task,
        offset=-10,
    )

    assert result == [
        second,
        first,
    ]


def test_record_creates_history_event_from_enum(
    db: Session,
) -> None:
    actor, task = _create_context(
        db,
    )

    event = TaskHistoryService.record(
        db,
        task=task,
        actor=actor,
        event_type=TaskHistoryEventType.MOVED,
        summary="Task moved to In Progress.",
        metadata_json={
            "previous_list_id": 1,
            "section_list_id": 2,
        },
        commit=False,
    )

    assert event.id is not None
    assert event.task_id == task.id
    assert event.user_id == actor.id
    assert event.event_type == TaskHistoryEventType.MOVED.value
    assert event.summary == "Task moved to In Progress."
    assert event.metadata_json == {
        "previous_list_id": 1,
        "section_list_id": 2,
    }


def test_record_accepts_string_event_type(
    db: Session,
) -> None:
    actor, task = _create_context(
        db,
    )

    event = TaskHistoryService.record(
        db,
        task=task,
        actor=actor,
        event_type="custom_event",
        summary="A custom event occurred.",
        commit=False,
    )

    assert event.event_type == "custom_event"
    assert event.summary == "A custom event occurred."


def test_record_strips_event_type_and_summary(
    db: Session,
) -> None:
    actor, task = _create_context(
        db,
    )

    event = TaskHistoryService.record(
        db,
        task=task,
        actor=actor,
        event_type="  custom_event  ",
        summary="  A custom event occurred.  ",
        commit=False,
    )

    assert event.event_type == "custom_event"
    assert event.summary == "A custom event occurred."


def test_record_uses_explicit_user_id_without_actor(
    db: Session,
) -> None:
    actor, task = _create_context(
        db,
    )

    event = TaskHistoryService.record(
        db,
        task=task,
        user_id=actor.id,
        event_type=TaskHistoryEventType.UPDATED,
        summary="Task updated.",
        commit=False,
    )

    assert event.user_id == actor.id


def test_record_allows_system_event_without_user(
    db: Session,
) -> None:
    _, task = _create_context(
        db,
    )

    event = TaskHistoryService.record(
        db,
        task=task,
        event_type=TaskHistoryEventType.UPDATED,
        summary="Task updated automatically.",
        commit=False,
    )

    assert event.user_id is None
    assert event.user is None


def test_record_actor_takes_precedence_over_user_id(
    db: Session,
) -> None:
    actor, task = _create_context(
        db,
    )

    other_user = create_user(
        db,
    )

    event = TaskHistoryService.record(
        db,
        task=task,
        actor=actor,
        user_id=other_user.id,
        event_type=TaskHistoryEventType.UPDATED,
        summary="Task updated.",
        commit=False,
    )

    assert event.user_id == actor.id
    assert event.user_id != other_user.id


def test_record_defaults_metadata_to_empty_dictionary(
    db: Session,
) -> None:
    actor, task = _create_context(
        db,
    )

    event = TaskHistoryService.record(
        db,
        task=task,
        actor=actor,
        event_type=TaskHistoryEventType.UPDATED,
        summary="Task updated.",
        commit=False,
    )

    assert event.metadata_json == {}


def test_record_sanitises_sensitive_metadata(
    db: Session,
) -> None:
    actor, task = _create_context(
        db,
    )

    event = TaskHistoryService.record(
        db,
        task=task,
        actor=actor,
        event_type=TaskHistoryEventType.UPDATED,
        summary="Task updated.",
        metadata_json={
            "title": "Visible value",
            "password": "Do not retain this",
        },
        commit=False,
    )

    assert event.metadata_json["title"] == "Visible value"
    assert (
        event.metadata_json["password"]
        != "Do not retain this"
    )


def test_record_created_creates_expected_event(
    db: Session,
) -> None:
    actor, task = _create_context(
        db,
    )

    event = TaskHistoryService.record_created(
        db,
        task=task,
        actor=actor,
        commit=False,
    )

    assert event.task_id == task.id
    assert event.user_id == actor.id
    assert event.event_type == TaskHistoryEventType.CREATED.value
    assert event.summary == (
        "Task History Actor created this task."
    )
    assert event.metadata_json["section_list_id"] == (
        task.section_list_id
    )
    assert event.metadata_json["title"] == task.title
    assert "due_at" in event.metadata_json


def test_record_updated_creates_expected_event(
    db: Session,
) -> None:
    actor, task = _create_context(
        db,
    )

    changes = {
        "title": {
            "previous": "Old title",
            "current": "New title",
        },
    }

    event = TaskHistoryService.record_updated(
        db,
        task=task,
        actor=actor,
        changes=changes,
        commit=False,
    )

    assert event.task_id == task.id
    assert event.user_id == actor.id
    assert event.event_type == TaskHistoryEventType.UPDATED.value
    assert event.summary == (
        "Task History Actor updated this task."
    )
    assert event.metadata_json == {
        "changes": changes,
    }


def test_record_persists_event_in_repository(
    db: Session,
) -> None:
    actor, task = _create_context(
        db,
    )

    event = TaskHistoryService.record(
        db,
        task=task,
        actor=actor,
        event_type=TaskHistoryEventType.COMPLETED,
        summary="Task completed.",
        commit=False,
    )

    stored_event = TaskHistoryRepository.get_by_id(
        db,
        history_event_id=event.id,
    )

    assert stored_event is event


def test_normalise_event_type_returns_enum_value() -> None:
    result = TaskHistoryService.normalise_event_type(
        TaskHistoryEventType.COMPLETED,
    )

    assert result == TaskHistoryEventType.COMPLETED.value


def test_normalise_event_type_strips_string() -> None:
    result = TaskHistoryService.normalise_event_type(
        "  custom_event  ",
    )

    assert result == "custom_event"


def test_normalise_event_type_rejects_blank_string() -> None:
    with pytest.raises(
        TaskHistoryServiceError,
        match="event type cannot be empty",
    ):
        TaskHistoryService.normalise_event_type(
            "   ",
        )


def test_normalise_summary_strips_value() -> None:
    result = TaskHistoryService.normalise_summary(
        "  Task was updated.  ",
    )

    assert result == "Task was updated."


def test_normalise_summary_rejects_blank_value() -> None:
    with pytest.raises(
        TaskHistoryServiceError,
        match="summary cannot be empty",
    ):
        TaskHistoryService.normalise_summary(
            "   ",
        )