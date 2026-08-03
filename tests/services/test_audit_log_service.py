from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.constants import AuditAction
from app.core.timezone import utc_now
from app.schemas.audit_log import (
    AuditLogDetail,
    AuditLogFilterOptions,
    AuditLogPage,
)
from app.services.audit_service import (
    AuditLogNotFoundError,
    AuditLogPermissionError,
    AuditService,
)
from tests.factories import (
    create_administrator,
    create_audit_log,
    create_user,
)


def test_record_creates_audit_log(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    result = AuditService.record(
        db,
        user=user,
        action=AuditAction.TASK_CREATED,
        summary="  Task created.  ",
        entity_type=" task ",
        entity_id=42,
        commit=False,
    )

    assert result.user_id == user.id
    assert result.action == (
        AuditAction.TASK_CREATED.value
    )
    assert result.summary == "Task created."
    assert result.entity_type == "task"
    assert result.entity_id == 42


def test_record_system_event_has_no_user(
    db: Session,
) -> None:
    result = AuditService.record_system_event(
        db,
        action="notification_failed",
        summary="Notification delivery failed.",
        commit=False,
    )

    assert result.user_id is None
    assert result.action == "notification_failed"


def test_require_log_returns_existing_log(
    db: Session,
) -> None:
    audit_log = create_audit_log(
        db,
        action="task_created",
        summary="Task created",
    )

    result = AuditService.require_log(
        db,
        audit_log_id=audit_log.id,
    )

    assert result is audit_log


def test_require_log_rejects_unknown_log(
    db: Session,
) -> None:
    with pytest.raises(
        AuditLogNotFoundError,
    ):
        AuditService.require_log(
            db,
            audit_log_id=999999,
        )


def test_metadata_redacts_sensitive_values_recursively(
    db: Session,
) -> None:
    audit_log = AuditService.record(
        db,
        action="test_action",
        summary="Test event",
        metadata_json={
            "password": "secret-password",
            "nested": {
                "csrf_token": "secret-token",
                "safe": "visible",
            },
            "items": [
                {
                    "database_url": "secret-url",
                },
                {
                    "value": "visible-value",
                },
            ],
        },
        commit=False,
    )

    assert audit_log.metadata_json[
        "password"
    ] == "[REDACTED]"

    assert audit_log.metadata_json[
        "nested"
    ][
        "csrf_token"
    ] == "[REDACTED]"

    assert audit_log.metadata_json[
        "nested"
    ][
        "safe"
    ] == "visible"

    assert audit_log.metadata_json[
        "items"
    ][0][
        "database_url"
    ] == "[REDACTED]"

    assert audit_log.metadata_json[
        "items"
    ][1][
        "value"
    ] == "visible-value"


def test_metadata_redacts_comment_content(
    db: Session,
) -> None:
    audit_log = AuditService.record(
        db,
        action="task_comment_added",
        summary="Comment added",
        metadata_json={
            "comment_content": (
                "Private comment body"
            ),
            "deleted_comment_content": (
                "Deleted private comment"
            ),
        },
        commit=False,
    )

    assert audit_log.metadata_json[
        "comment_content"
    ] == "[REDACTED]"

    assert audit_log.metadata_json[
        "deleted_comment_content"
    ] == "[REDACTED]"


def test_get_log_page_requires_administrator(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    with pytest.raises(
        AuditLogPermissionError,
    ):
        AuditService.get_log_page(
            db,
            actor=user,
        )


def test_get_log_page_returns_paginated_results(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    now = utc_now()

    first = create_audit_log(
        db,
        action="first_action",
        summary="First event",
    )

    second = create_audit_log(
        db,
        action="second_action",
        summary="Second event",
    )

    first.created_at = now
    second.created_at = now - timedelta(
        minutes=1,
    )

    db.flush()

    result = AuditService.get_log_page(
        db,
        actor=administrator,
        filters=AuditLogFilterOptions(
            page=1,
            page_size=1,
        ),
    )

    assert isinstance(
        result,
        AuditLogPage,
    )

    assert result.total_items == 2
    assert result.total_pages == 2
    assert result.current_page == 1
    assert result.page_size == 1

    assert [
        log.id
        for log in result.logs
    ] == [
        first.id,
    ]


def test_get_log_page_applies_filters(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    matching = create_audit_log(
        db,
        action="task_created",
        summary="Coffee task created",
        entity_type="task",
        entity_id=42,
    )

    create_audit_log(
        db,
        action="task_deleted",
        summary="Cellar task deleted",
        entity_type="task",
        entity_id=43,
    )

    result = AuditService.get_log_page(
        db,
        actor=administrator,
        filters=AuditLogFilterOptions(
            search="coffee",
            action="task_created",
            entity_type="task",
            entity_id=42,
        ),
    )

    assert result.total_items == 1

    assert [
        log.id
        for log in result.logs
    ] == [
        matching.id,
    ]


def test_get_log_detail_returns_metadata(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    audit_log = create_audit_log(
        db,
        action="task_updated",
        summary="Task updated",
        entity_type="task",
        entity_id=42,
        metadata_json={
            "field": "title",
        },
    )

    result = AuditService.get_log_detail(
        db,
        actor=administrator,
        audit_log_id=audit_log.id,
    )

    assert isinstance(
        result,
        AuditLogDetail,
    )

    assert result.id == audit_log.id
    assert result.metadata_json == {
        "field": "title",
    }


def test_get_log_detail_requires_administrator(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    audit_log = create_audit_log(
        db,
        action="task_updated",
        summary="Task updated",
    )

    with pytest.raises(
        AuditLogPermissionError,
    ):
        AuditService.get_log_detail(
            db,
            actor=user,
            audit_log_id=audit_log.id,
        )


def test_filter_choices_return_available_values(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    create_audit_log(
        db,
        action="task_created",
        summary="Task created",
        entity_type="task",
    )

    create_audit_log(
        db,
        action="company_created",
        summary="Company created",
        entity_type="company",
    )

    result = AuditService.get_filter_choices(
        db,
        actor=administrator,
    )

    assert result.actions == [
        "company_created",
        "task_created",
    ]

    assert result.entity_types == [
        "company",
        "task",
    ]


def test_normalise_limit_clamps_values() -> None:
    assert AuditService.normalise_limit(
        0,
    ) == 1

    assert AuditService.normalise_limit(
        1000,
    ) == 500

    assert AuditService.normalise_limit(
        50,
    ) == 50


def test_normalise_offset_prevents_negative_values() -> None:
    assert AuditService.normalise_offset(
        -10,
    ) == 0

    assert AuditService.normalise_offset(
        10,
    ) == 10


@pytest.mark.parametrize(
    (
        "value",
        "field_name",
    ),
    [
        (
            "",
            "summary",
        ),
        (
            "   ",
            "action",
        ),
    ],
)
def test_required_strings_cannot_be_empty(
    value: str,
    field_name: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="cannot be empty",
    ):
        AuditService.normalise_required_string(
            value,
            field_name=field_name,
        )