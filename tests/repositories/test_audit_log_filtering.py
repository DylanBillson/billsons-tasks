from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.timezone import utc_now
from app.repositories.audit_repository import (
    AuditRepository,
)
from tests.factories import (
    create_audit_log,
    create_user,
)


def test_list_logs_returns_newest_first(
    db: Session,
) -> None:
    now = utc_now()

    older = create_audit_log(
        db,
        action="older_action",
        summary="Older audit entry",
    )

    newer = create_audit_log(
        db,
        action="newer_action",
        summary="Newer audit entry",
    )

    older.created_at = now - timedelta(
        hours=1,
    )

    newer.created_at = now

    db.flush()

    result = AuditRepository.list_logs(
        db,
    )

    assert result == [
        newer,
        older,
    ]


def test_list_logs_filters_by_user(
    db: Session,
) -> None:
    first_user = create_user(
        db,
    )

    second_user = create_user(
        db,
    )

    matching = create_audit_log(
        db,
        action="user_action",
        summary="Matching user event",
        user=first_user,
    )

    create_audit_log(
        db,
        action="user_action",
        summary="Other user event",
        user=second_user,
    )

    result = AuditRepository.list_logs(
        db,
        user_id=first_user.id,
    )

    assert result == [
        matching,
    ]


def test_list_logs_filters_by_action(
    db: Session,
) -> None:
    matching = create_audit_log(
        db,
        action="task_created",
        summary="Task created",
    )

    create_audit_log(
        db,
        action="task_deleted",
        summary="Task deleted",
    )

    result = AuditRepository.list_logs(
        db,
        action="task_created",
    )

    assert result == [
        matching,
    ]


def test_list_logs_filters_by_entity(
    db: Session,
) -> None:
    matching = create_audit_log(
        db,
        action="task_updated",
        summary="Matching task",
        entity_type="task",
        entity_id=42,
    )

    create_audit_log(
        db,
        action="task_updated",
        summary="Other task",
        entity_type="task",
        entity_id=43,
    )

    result = AuditRepository.list_logs(
        db,
        entity_type="task",
        entity_id=42,
    )

    assert result == [
        matching,
    ]


def test_list_logs_filters_by_date_range(
    db: Session,
) -> None:
    now = utc_now()

    matching = create_audit_log(
        db,
        action="recent_action",
        summary="Recent event",
    )

    hidden = create_audit_log(
        db,
        action="old_action",
        summary="Old event",
    )

    matching.created_at = now - timedelta(
        days=1,
    )

    hidden.created_at = now - timedelta(
        days=20,
    )

    db.flush()

    result = AuditRepository.list_logs(
        db,
        created_from=now - timedelta(
            days=5,
        ),
        created_to=now,
    )

    assert result == [
        matching,
    ]


def test_list_logs_searches_summary(
    db: Session,
) -> None:
    matching = create_audit_log(
        db,
        action="task_updated",
        summary="Coffee order was updated",
    )

    create_audit_log(
        db,
        action="task_updated",
        summary="Cellar cleaning was updated",
    )

    result = AuditRepository.list_logs(
        db,
        search="coffee",
    )

    assert result == [
        matching,
    ]


def test_list_logs_searches_action_and_entity_type(
    db: Session,
) -> None:
    action_match = create_audit_log(
        db,
        action="company_archived",
        summary="First event",
        entity_type="company",
    )

    entity_match = create_audit_log(
        db,
        action="record_updated",
        summary="Second event",
        entity_type="archived_company_record",
    )

    create_audit_log(
        db,
        action="task_updated",
        summary="Hidden event",
        entity_type="task",
    )

    result = AuditRepository.list_logs(
        db,
        search="company",
    )

    assert set(
        result,
    ) == {
        action_match,
        entity_match,
    }


def test_list_logs_searches_user_identity(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="coffee-manager",
        display_name="Coffee Manager",
    )

    matching = create_audit_log(
        db,
        action="login",
        summary="User signed in",
        user=user,
    )

    create_audit_log(
        db,
        action="login",
        summary="System sign in",
    )

    result = AuditRepository.list_logs(
        db,
        search="coffee",
    )

    assert result == [
        matching,
    ]


def test_count_logs_matches_filters(
    db: Session,
) -> None:
    create_audit_log(
        db,
        action="task_created",
        summary="First matching event",
    )

    create_audit_log(
        db,
        action="task_created",
        summary="Second matching event",
    )

    create_audit_log(
        db,
        action="task_deleted",
        summary="Hidden event",
    )

    count = AuditRepository.count_logs(
        db,
        action="task_created",
    )

    assert count == 2


def test_list_logs_supports_pagination(
    db: Session,
) -> None:
    now = utc_now()

    newest = create_audit_log(
        db,
        action="newest",
        summary="Newest",
    )

    middle = create_audit_log(
        db,
        action="middle",
        summary="Middle",
    )

    oldest = create_audit_log(
        db,
        action="oldest",
        summary="Oldest",
    )

    newest.created_at = now
    middle.created_at = now - timedelta(
        minutes=1,
    )
    oldest.created_at = now - timedelta(
        minutes=2,
    )

    db.flush()

    result = AuditRepository.list_logs(
        db,
        limit=1,
        offset=1,
    )

    assert result == [
        middle,
    ]


def test_list_actions_returns_distinct_sorted_values(
    db: Session,
) -> None:
    create_audit_log(
        db,
        action="task_updated",
        summary="First",
    )

    create_audit_log(
        db,
        action="company_created",
        summary="Second",
    )

    create_audit_log(
        db,
        action="task_updated",
        summary="Third",
    )

    result = AuditRepository.list_actions(
        db,
    )

    assert result == [
        "company_created",
        "task_updated",
    ]


def test_list_entity_types_returns_distinct_sorted_values(
    db: Session,
) -> None:
    create_audit_log(
        db,
        action="first",
        summary="First",
        entity_type="task",
    )

    create_audit_log(
        db,
        action="second",
        summary="Second",
        entity_type="company",
    )

    create_audit_log(
        db,
        action="third",
        summary="Third",
        entity_type="task",
    )

    result = AuditRepository.list_entity_types(
        db,
    )

    assert result == [
        "company",
        "task",
    ]