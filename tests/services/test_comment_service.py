import pytest
from sqlalchemy.orm import Session

from app.auth.permissions import PermissionDeniedError
from app.core.constants import (
    AuditAction,
    CompanyRole,
    TaskHistoryEventType,
)
from app.repositories.audit_repository import AuditRepository
from app.repositories.task_history_repository import (
    TaskHistoryRepository,
)
from app.schemas.comment import TaskCommentCreateRequest
from app.services.comment_service import (
    CommentAlreadyDeletedError,
    CommentNotFoundError,
    CommentPermissionError,
    CommentService,
)
from tests.factories import (
    create_administrator,
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
    company = create_company(
        db,
    )

    section_creator = create_user(
        db,
        display_name="Section Creator",
    )

    create_company_membership(
        db,
        company=company,
        user=section_creator,
        role=CompanyRole.MANAGER,
    )

    section = create_section(
        db,
        company=company,
        created_by=section_creator,
    )

    section_list = create_section_list(
        db,
        section=section,
        name="To Do",
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=section_creator,
        title="Prepare the weekly report",
    )

    return (
        company,
        section_creator,
        section,
        section_list,
        task,
    )


def _create_section_member(
    db: Session,
    *,
    company,
    section,
    display_name: str | None = None,
):
    member = create_user(
        db,
        display_name=display_name,
    )

    create_company_membership(
        db,
        company=company,
        user=member,
        role=CompanyRole.EMPLOYEE,
    )

    create_section_membership(
        db,
        section=section,
        user=member,
    )

    return member


def test_get_comment_returns_existing_comment(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    comment = create_task_comment(
        db,
        task=task,
        user=creator,
    )

    result = CommentService.get_comment(
        db,
        comment_id=comment.id,
    )

    assert result is comment


def test_get_comment_returns_none_for_unknown_comment(
    db: Session,
) -> None:
    result = CommentService.get_comment(
        db,
        comment_id=999999,
    )

    assert result is None


def test_require_comment_returns_existing_comment(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    comment = create_task_comment(
        db,
        task=task,
        user=creator,
    )

    result = CommentService.require_comment(
        db,
        comment_id=comment.id,
    )

    assert result is comment


def test_require_comment_raises_for_unknown_comment(
    db: Session,
) -> None:
    with pytest.raises(
        CommentNotFoundError,
        match="Comment was not found",
    ):
        CommentService.require_comment(
            db,
            comment_id=999999,
        )


def test_section_creator_lists_comments(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    first = create_task_comment(
        db,
        task=task,
        user=creator,
        body="First comment.",
    )

    second = create_task_comment(
        db,
        task=task,
        user=creator,
        body="Second comment.",
    )

    result = CommentService.list_for_task(
        db,
        actor=creator,
        task=task,
    )

    assert result == [
        second,
        first,
    ]


def test_section_member_lists_comments(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    comment = create_task_comment(
        db,
        task=task,
        user=member,
    )

    result = CommentService.list_for_task(
        db,
        actor=member,
        task=task,
    )

    assert result == [
        comment,
    ]


def test_outsider_cannot_list_comments(
    db: Session,
) -> None:
    (
        _,
        _,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    outsider = create_user(
        db,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="access to this task",
    ):
        CommentService.list_for_task(
            db,
            actor=outsider,
            task=task,
        )


def test_deleted_comments_are_excluded_by_default(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    active = create_task_comment(
        db,
        task=task,
        user=creator,
        body="Visible comment.",
    )

    create_task_comment(
        db,
        task=task,
        user=creator,
        body="Deleted comment.",
        deleted_by=creator,
    )

    result = CommentService.list_for_task(
        db,
        actor=creator,
        task=task,
    )

    assert result == [
        active,
    ]


def test_section_creator_can_include_deleted_comments(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    active = create_task_comment(
        db,
        task=task,
        user=creator,
        body="Visible comment.",
    )

    deleted = create_task_comment(
        db,
        task=task,
        user=creator,
        body="Deleted comment.",
        deleted_by=creator,
    )

    result = CommentService.list_for_task(
        db,
        actor=creator,
        task=task,
        include_deleted=True,
    )

    assert result == [
        deleted,
        active,
    ]


def test_administrator_can_include_deleted_comments(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    administrator = create_administrator(
        db,
    )

    deleted = create_task_comment(
        db,
        task=task,
        user=creator,
        deleted_by=creator,
    )

    result = CommentService.list_for_task(
        db,
        actor=administrator,
        task=task,
        include_deleted=True,
    )

    assert result == [
        deleted,
    ]


def test_section_member_cannot_include_deleted_comments(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    active = create_task_comment(
        db,
        task=task,
        user=member,
        body="Visible comment.",
    )

    create_task_comment(
        db,
        task=task,
        user=creator,
        body="Deleted comment.",
        deleted_by=creator,
    )

    result = CommentService.list_for_task(
        db,
        actor=member,
        task=task,
        include_deleted=True,
    )

    assert result == [
        active,
    ]


def test_section_member_adds_comment(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
        display_name="Comment Author",
    )

    comment = CommentService.add_comment(
        db,
        actor=member,
        task=task,
        comment_create=TaskCommentCreateRequest(
            body="  This task is nearly complete.  ",
        ),
        commit=False,
    )

    assert comment.id is not None
    assert comment.task_id == task.id
    assert comment.user_id == member.id
    assert comment.body == "This task is nearly complete."
    assert comment.is_deleted is False


def test_section_creator_adds_comment(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    comment = CommentService.add_comment(
        db,
        actor=creator,
        task=task,
        comment_create=TaskCommentCreateRequest(
            body="Creator comment.",
        ),
        commit=False,
    )

    assert comment.user_id == creator.id
    assert comment.body == "Creator comment."


def test_administrator_adds_comment(
    db: Session,
) -> None:
    (
        _,
        _,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    administrator = create_administrator(
        db,
    )

    comment = CommentService.add_comment(
        db,
        actor=administrator,
        task=task,
        comment_create=TaskCommentCreateRequest(
            body="Administrator comment.",
        ),
        commit=False,
    )

    assert comment.user_id == administrator.id


def test_outsider_cannot_add_comment(
    db: Session,
) -> None:
    (
        _,
        _,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    outsider = create_user(
        db,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="comment on this task",
    ):
        CommentService.add_comment(
            db,
            actor=outsider,
            task=task,
            comment_create=TaskCommentCreateRequest(
                body="Unauthorised comment.",
            ),
            commit=False,
        )


def test_company_manager_cannot_comment_without_section_access(
    db: Session,
) -> None:
    (
        company,
        _,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    manager = create_user(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="comment on this task",
    ):
        CommentService.add_comment(
            db,
            actor=manager,
            task=task,
            comment_create=TaskCommentCreateRequest(
                body="Unauthorised manager comment.",
            ),
            commit=False,
        )


def test_deleted_task_cannot_receive_comment(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        section_list,
        _,
    ) = _create_context(
        db,
    )

    deleted_task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        deleted_by=creator,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="comment on this task",
    ):
        CommentService.add_comment(
            db,
            actor=creator,
            task=deleted_task,
            comment_create=TaskCommentCreateRequest(
                body="Comment on deleted task.",
            ),
            commit=False,
        )


def test_archived_list_task_cannot_receive_comment(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        section_list,
        task,
    ) = _create_context(
        db,
    )

    section_list.is_archived = True
    db.flush()

    with pytest.raises(
        PermissionDeniedError,
        match="comment on this task",
    ):
        CommentService.add_comment(
            db,
            actor=creator,
            task=task,
            comment_create=TaskCommentCreateRequest(
                body="Comment on archived list task.",
            ),
            commit=False,
        )


def test_add_comment_records_history_event(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
        display_name="Comment Author",
    )

    comment = CommentService.add_comment(
        db,
        actor=member,
        task=task,
        comment_create=TaskCommentCreateRequest(
            body="A new comment.",
        ),
        commit=False,
    )

    events = TaskHistoryRepository.list_for_task(
        db,
        task_id=task.id,
    )

    assert len(events) == 1

    event = events[0]

    assert (
        event.event_type
        == TaskHistoryEventType.COMMENT_ADDED.value
    )
    assert event.user_id == member.id
    assert event.metadata_json["comment_id"] == comment.id


def test_add_comment_records_audit_log(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
        display_name="Comment Author",
    )

    comment = CommentService.add_comment(
        db,
        actor=member,
        task=task,
        comment_create=TaskCommentCreateRequest(
            body="A visible audit comment.",
        ),
        ip_address="192.0.2.30",
        user_agent="pytest comment service",
        commit=False,
    )

    audit_logs = AuditRepository.list_logs(
        db,
        action=AuditAction.TASK_COMMENT_ADDED.value,
    )

    matching = [
        log
        for log in audit_logs
        if (
            log.entity_type == "task"
            and log.entity_id == task.id
        )
    ]

    assert len(matching) == 1

    audit_log = matching[0]

    assert audit_log.user_id == member.id
    assert audit_log.metadata_json["section_id"] == section.id
    assert audit_log.metadata_json["comment_id"] == comment.id

    assert (
        audit_log.metadata_json["comment_content"]
        == "[REDACTED]"
    )

    assert audit_log.ip_address == "192.0.2.30"


def test_comment_author_deletes_own_comment(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    author = _create_section_member(
        db,
        company=company,
        section=section,
    )

    comment = create_task_comment(
        db,
        task=task,
        user=author,
    )

    result = CommentService.delete_comment(
        db,
        actor=author,
        comment=comment,
        commit=False,
    )

    assert result is comment
    assert comment.is_deleted is True
    assert comment.deleted_at is not None
    assert comment.deleted_by_user_id == author.id


def test_section_creator_deletes_another_users_comment(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    author = _create_section_member(
        db,
        company=company,
        section=section,
    )

    comment = create_task_comment(
        db,
        task=task,
        user=author,
    )

    CommentService.delete_comment(
        db,
        actor=creator,
        comment=comment,
        commit=False,
    )

    assert comment.is_deleted is True
    assert comment.deleted_by_user_id == creator.id


def test_administrator_deletes_another_users_comment(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    author = _create_section_member(
        db,
        company=company,
        section=section,
    )

    administrator = create_administrator(
        db,
    )

    comment = create_task_comment(
        db,
        task=task,
        user=author,
    )

    CommentService.delete_comment(
        db,
        actor=administrator,
        comment=comment,
        commit=False,
    )

    assert comment.is_deleted is True
    assert comment.deleted_by_user_id == administrator.id


def test_section_member_cannot_delete_another_users_comment(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    author = _create_section_member(
        db,
        company=company,
        section=section,
    )

    other_member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    comment = create_task_comment(
        db,
        task=task,
        user=author,
    )

    with pytest.raises(
        CommentPermissionError,
        match="permission to delete this comment",
    ):
        CommentService.delete_comment(
            db,
            actor=other_member,
            comment=comment,
            commit=False,
        )

    assert comment.is_deleted is False


def test_outsider_cannot_delete_comment(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    outsider = create_user(
        db,
    )

    comment = create_task_comment(
        db,
        task=task,
        user=creator,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="access to this task",
    ):
        CommentService.delete_comment(
            db,
            actor=outsider,
            comment=comment,
            commit=False,
        )

    assert comment.is_deleted is False


def test_delete_comment_rejects_already_deleted_comment(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    comment = create_task_comment(
        db,
        task=task,
        user=creator,
        deleted_by=creator,
    )

    with pytest.raises(
        CommentAlreadyDeletedError,
        match="Comment is already deleted",
    ):
        CommentService.delete_comment(
            db,
            actor=creator,
            comment=comment,
            commit=False,
        )


def test_delete_comment_records_history_event(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    author = _create_section_member(
        db,
        company=company,
        section=section,
        display_name="Comment Author",
    )

    comment = create_task_comment(
        db,
        task=task,
        user=author,
    )

    CommentService.delete_comment(
        db,
        actor=author,
        comment=comment,
        commit=False,
    )

    events = TaskHistoryRepository.list_for_task(
        db,
        task_id=task.id,
    )

    assert len(events) == 1

    event = events[0]

    assert (
        event.event_type
        == TaskHistoryEventType.COMMENT_DELETED.value
    )
    assert event.user_id == author.id
    assert event.metadata_json["comment_id"] == comment.id

    assert (
        event.metadata_json["comment_author_user_id"]
        == author.id
    )


def test_delete_comment_records_audit_log(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    author = _create_section_member(
        db,
        company=company,
        section=section,
    )

    comment = create_task_comment(
        db,
        task=task,
        user=author,
        body="Comment content being deleted.",
    )

    CommentService.delete_comment(
        db,
        actor=author,
        comment=comment,
        ip_address="192.0.2.31",
        user_agent="pytest comment deletion",
        commit=False,
    )

    audit_logs = AuditRepository.list_logs(
        db,
        action=AuditAction.TASK_COMMENT_DELETED.value,
    )

    matching = [
        log
        for log in audit_logs
        if (
            log.entity_type == "task"
            and log.entity_id == task.id
        )
    ]

    assert len(matching) == 1

    audit_log = matching[0]

    assert audit_log.user_id == author.id
    assert audit_log.metadata_json["section_id"] == section.id
    assert audit_log.metadata_json["comment_id"] == comment.id

    assert (
        audit_log.metadata_json["comment_author_user_id"]
        == author.id
    )

    assert (
        audit_log.metadata_json["deleted_comment_content"]
        == "[REDACTED]"
    )

    assert audit_log.ip_address == "192.0.2.31"


def test_deleting_comment_does_not_remove_database_record(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    comment = create_task_comment(
        db,
        task=task,
        user=creator,
    )

    comment_id = comment.id

    CommentService.delete_comment(
        db,
        actor=creator,
        comment=comment,
        commit=False,
    )

    stored_comment = CommentService.get_comment(
        db,
        comment_id=comment_id,
    )

    assert stored_comment is comment
    assert stored_comment.is_deleted is True