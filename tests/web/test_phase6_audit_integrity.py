from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import AuditAction
from app.models.audit_log import AuditLog
from app.services.audit_service import AuditService
from tests.factories import (
    create_administrator,
    create_audit_log,
    create_user,
)


def test_audit_record_preserves_actor_and_entity(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    audit_log = AuditService.record(
        db,
        user=administrator,
        action=AuditAction.USER_DEACTIVATED,
        summary="A user was deactivated.",
        entity_type="user",
        entity_id=42,
        metadata_json={
            "is_active": False,
        },
        commit=False,
    )

    assert audit_log.user_id == administrator.id
    assert audit_log.entity_type == "user"
    assert audit_log.entity_id == 42
    assert audit_log.action == (
        AuditAction.USER_DEACTIVATED.value
    )


def test_audit_record_redacts_sensitive_metadata(
    db: Session,
) -> None:
    audit_log = AuditService.record(
        db,
        action="security_test",
        summary="Sensitive metadata test.",
        metadata_json={
            "password": "plain-text-password",
            "csrf_token": "csrf-secret",
            "database_url": "postgresql://secret",
            "nested": {
                "session_token": "session-secret",
                "safe_value": "visible",
            },
        },
        commit=False,
    )

    assert audit_log.metadata_json[
        "password"
    ] == "[REDACTED]"

    assert audit_log.metadata_json[
        "csrf_token"
    ] == "[REDACTED]"

    assert audit_log.metadata_json[
        "database_url"
    ] == "[REDACTED]"

    assert audit_log.metadata_json[
        "nested"
    ][
        "session_token"
    ] == "[REDACTED]"

    assert audit_log.metadata_json[
        "nested"
    ][
        "safe_value"
    ] == "visible"


def test_audit_record_does_not_store_comment_content(
    db: Session,
) -> None:
    audit_log = AuditService.record(
        db,
        action=AuditAction.TASK_COMMENT_ADDED,
        summary="A task comment was added.",
        metadata_json={
            "comment_id": 10,
            "comment_content": (
                "This content must not be stored."
            ),
        },
        commit=False,
    )

    assert audit_log.metadata_json[
        "comment_id"
    ] == 10

    assert audit_log.metadata_json[
        "comment_content"
    ] == "[REDACTED]"


def test_system_audit_event_has_no_actor(
    db: Session,
) -> None:
    audit_log = AuditService.record_system_event(
        db,
        action=AuditAction.NOTIFICATION_FAILED,
        summary="Notification delivery failed.",
        metadata_json={
            "notification_id": 20,
        },
        commit=False,
    )

    assert audit_log.user_id is None
    assert audit_log.action == (
        AuditAction.NOTIFICATION_FAILED.value
    )


def test_audit_log_ordering_is_deterministic(
    db: Session,
) -> None:
    first = create_audit_log(
        db,
        action="first",
        summary="First audit event.",
    )

    second = create_audit_log(
        db,
        action="second",
        summary="Second audit event.",
    )

    second.created_at = first.created_at

    db.flush()

    results = AuditService.list_logs(
        db,
        limit=10,
    )

    matching_ids = [
        audit_log.id
        for audit_log in results
        if audit_log.id
        in {
            first.id,
            second.id,
        }
    ]

    assert matching_ids == [
        second.id,
        first.id,
    ]


def test_audit_log_count_matches_filtered_results(
    db: Session,
) -> None:
    create_audit_log(
        db,
        action="task_created",
        summary="First filtered event.",
    )

    create_audit_log(
        db,
        action="task_created",
        summary="Second filtered event.",
    )

    create_audit_log(
        db,
        action="task_deleted",
        summary="Hidden event.",
    )

    count = AuditService.count_logs(
        db,
        action="task_created",
    )

    logs = AuditService.list_logs(
        db,
        action="task_created",
    )

    assert count == 2
    assert len(
        logs,
    ) == count


def test_anonymised_user_audit_relationship_is_preserved(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="anonymised-audit-user",
        display_name="Anonymised Audit User",
        is_active=False,
        is_anonymised=True,
    )

    audit_log = create_audit_log(
        db,
        user=user,
        action="task_updated",
        summary="An anonymised user updated a task.",
    )

    db.commit()
    db.expire_all()

    persisted = db.scalar(
        select(
            AuditLog,
        ).where(
            AuditLog.id == audit_log.id,
        ),
    )

    assert persisted is not None
    assert persisted.user_id == user.id
    assert persisted.user is not None
    assert persisted.user.is_anonymised is True


def test_audit_metadata_is_always_a_dictionary(
    db: Session,
) -> None:
    audit_log = AuditService.record(
        db,
        action="empty_metadata",
        summary="No metadata supplied.",
        metadata_json=None,
        commit=False,
    )

    assert audit_log.metadata_json == {}