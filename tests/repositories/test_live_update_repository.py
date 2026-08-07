from sqlalchemy.orm import Session

from app.repositories.live_update_repository import (
    LiveUpdateRepository,
)
from tests.factories import (
    create_company,
    create_section,
    create_section_list,
    create_task,
    create_task_assignee,
    create_task_comment,
    create_task_history_event,
    create_user,
)


def _create_context(
    db: Session,
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
    )

    return (
        creator,
        section,
        section_list,
        task,
    )


def test_get_section_snapshot_returns_none_for_missing_section(
    db: Session,
) -> None:
    result = (
        LiveUpdateRepository.get_section_snapshot(
            db,
            section_id=999_999,
        )
    )

    assert result is None


def test_get_section_snapshot_contains_board_counts(
    db: Session,
) -> None:
    (
        creator,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    assignee = create_user(
        db,
    )

    create_task_assignee(
        db,
        task=task,
        user=assignee,
    )

    db.commit()

    snapshot = (
        LiveUpdateRepository.get_section_snapshot(
            db,
            section_id=section.id,
        )
    )

    assert snapshot is not None
    assert snapshot.section_id == section.id
    assert snapshot.section_list_count == 1
    assert snapshot.task_count == 1
    assert snapshot.task_assignee_count == 1

    assert (
        snapshot.section_updated_at
        == section.updated_at
    )

    assert (
        snapshot.latest_section_list_updated_at
        is not None
    )

    assert snapshot.latest_task_updated_at is not None

    assert (
        snapshot.latest_task_assignee_updated_at
        is not None
    )


def test_section_snapshot_changes_when_task_is_added(
    db: Session,
) -> None:
    (
        creator,
        section,
        section_list,
        _,
    ) = _create_context(
        db,
    )

    before = (
        LiveUpdateRepository.get_section_snapshot(
            db,
            section_id=section.id,
        )
    )

    assert before is not None

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
    )

    db.flush()

    after = (
        LiveUpdateRepository.get_section_snapshot(
            db,
            section_id=section.id,
        )
    )

    assert after is not None
    assert after.task_count == before.task_count + 1


def test_get_task_snapshot_returns_none_for_missing_task(
    db: Session,
) -> None:
    result = LiveUpdateRepository.get_task_snapshot(
        db,
        task_id=999_999,
    )

    assert result is None


def test_get_task_snapshot_contains_related_counts(
    db: Session,
) -> None:
    (
        creator,
        section,
        section_list,
        task,
    ) = _create_context(
        db,
    )

    assignee = create_user(
        db,
    )

    create_task_assignee(
        db,
        task=task,
        user=assignee,
    )

    create_task_comment(
        db,
        task=task,
        user=creator,
    )

    create_task_history_event(
        db,
        task=task,
        user=creator,
    )

    db.commit()

    snapshot = (
        LiveUpdateRepository.get_task_snapshot(
            db,
            task_id=task.id,
        )
    )

    assert snapshot is not None

    assert snapshot.task_id == task.id

    assert (
        snapshot.section_list_id
        == section_list.id
    )

    assert snapshot.section_id == section.id

    assert snapshot.comment_count == 1
    assert snapshot.history_event_count == 1
    assert snapshot.task_assignee_count == 1

    assert snapshot.latest_comment_updated_at is not None

    assert (
        snapshot.latest_history_event_created_at
        is not None
    )

    assert (
        snapshot.latest_task_assignee_updated_at
        is not None
    )


def test_task_snapshot_changes_when_comment_is_added(
    db: Session,
) -> None:
    (
        creator,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    before = LiveUpdateRepository.get_task_snapshot(
        db,
        task_id=task.id,
    )

    assert before is not None

    create_task_comment(
        db,
        task=task,
        user=creator,
    )

    db.flush()

    after = LiveUpdateRepository.get_task_snapshot(
        db,
        task_id=task.id,
    )

    assert after is not None

    assert (
        after.comment_count
        == before.comment_count + 1
    )