import pytest
from sqlalchemy.orm import Session
from app.core.timezone import utc_now
from app.auth.permissions import PermissionDeniedError
from app.schemas.live_updates import LiveUpdateScope
from app.services.live_update_service import (
    LiveUpdateResourceNotFoundError,
    LiveUpdateService,
)
from tests.factories import (
    create_company,
    create_company_membership,
    create_section,
    create_section_list,
    create_section_membership,
    create_task,
    create_task_comment,
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

    create_company_membership(
        db,
        company=company,
        user=creator,
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
        company,
        section,
        task,
    )


def test_get_section_revision_returns_stable_revision(
    db: Session,
) -> None:
    (
        creator,
        _,
        section,
        _,
    ) = _create_context(
        db,
    )

    first = LiveUpdateService.get_section_revision(
        db,
        actor=creator,
        section_id=section.id,
    )

    second = LiveUpdateService.get_section_revision(
        db,
        actor=creator,
        section_id=section.id,
    )

    assert first.scope == LiveUpdateScope.SECTION
    assert first.resource_id == section.id
    assert first.revision
    assert first.revision == second.revision
    assert len(first.revision) == 24


def test_section_revision_changes_after_board_change(
    db: Session,
) -> None:
    (
        creator,
        _,
        section,
        task,
    ) = _create_context(
        db,
    )

    before = LiveUpdateService.get_section_revision(
        db,
        actor=creator,
        section_id=section.id,
    )

    task.title = "Updated task title"
    task.updated_at = utc_now()

    db.flush()

    after = LiveUpdateService.get_section_revision(
        db,
        actor=creator,
        section_id=section.id,
    )

    assert before.revision != after.revision


def test_get_task_revision_returns_stable_revision(
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

    first = LiveUpdateService.get_task_revision(
        db,
        actor=creator,
        task_id=task.id,
    )

    second = LiveUpdateService.get_task_revision(
        db,
        actor=creator,
        task_id=task.id,
    )

    assert first.scope == LiveUpdateScope.TASK
    assert first.resource_id == task.id
    assert first.revision
    assert first.revision == second.revision
    assert len(first.revision) == 24


def test_task_revision_changes_after_comment_is_added(
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

    before = LiveUpdateService.get_task_revision(
        db,
        actor=creator,
        task_id=task.id,
    )

    create_task_comment(
        db,
        task=task,
        user=creator,
    )

    db.flush()

    after = LiveUpdateService.get_task_revision(
        db,
        actor=creator,
        task_id=task.id,
    )

    assert before.revision != after.revision


def test_section_has_changed_compares_known_revision(
    db: Session,
) -> None:
    (
        creator,
        _,
        section,
        task,
    ) = _create_context(
        db,
    )

    revision = LiveUpdateService.get_section_revision(
        db,
        actor=creator,
        section_id=section.id,
    )

    assert (
        LiveUpdateService.section_has_changed(
            db,
            actor=creator,
            section_id=section.id,
            known_revision=revision.revision,
        )
        is False
    )

    task.title = "Changed title"
    task.updated_at = utc_now()

    db.flush()

    assert (
        LiveUpdateService.section_has_changed(
            db,
            actor=creator,
            section_id=section.id,
            known_revision=revision.revision,
        )
        is True
    )


def test_task_has_changed_compares_known_revision(
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

    revision = LiveUpdateService.get_task_revision(
        db,
        actor=creator,
        task_id=task.id,
    )

    assert (
        LiveUpdateService.task_has_changed(
            db,
            actor=creator,
            task_id=task.id,
            known_revision=revision.revision,
        )
        is False
    )

    create_task_comment(
        db,
        task=task,
        user=creator,
    )

    db.flush()

    assert (
        LiveUpdateService.task_has_changed(
            db,
            actor=creator,
            task_id=task.id,
            known_revision=revision.revision,
        )
        is True
    )


def test_section_revision_rejects_user_without_access(
    db: Session,
) -> None:
    (
        _,
        _,
        section,
        _,
    ) = _create_context(
        db,
    )

    unrelated_user = create_user(
        db,
    )

    with pytest.raises(
        PermissionDeniedError,
    ):
        LiveUpdateService.get_section_revision(
            db,
            actor=unrelated_user,
            section_id=section.id,
        )


def test_task_revision_allows_assigned_section_member(
    db: Session,
) -> None:
    (
        _,
        company,
        section,
        task,
    ) = _create_context(
        db,
    )

    member = create_user(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=member,
    )

    create_section_membership(
        db,
        section=section,
        user=member,
    )

    revision = LiveUpdateService.get_task_revision(
        db,
        actor=member,
        task_id=task.id,
    )

    assert revision.scope == LiveUpdateScope.TASK
    assert revision.resource_id == task.id


def test_task_revision_rejects_user_without_access(
    db: Session,
) -> None:
    (
        _,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    unrelated_user = create_user(
        db,
    )

    with pytest.raises(
        PermissionDeniedError,
    ):
        LiveUpdateService.get_task_revision(
            db,
            actor=unrelated_user,
            task_id=task.id,
        )


def test_missing_section_raises_not_found(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    with pytest.raises(
        LiveUpdateResourceNotFoundError,
        match="Section was not found",
    ):
        LiveUpdateService.get_section_revision(
            db,
            actor=user,
            section_id=999_999,
        )


def test_missing_task_raises_not_found(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    with pytest.raises(
        LiveUpdateResourceNotFoundError,
        match="Task was not found",
    ):
        LiveUpdateService.get_task_revision(
            db,
            actor=user,
            task_id=999_999,
        )