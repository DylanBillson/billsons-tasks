import pytest
from sqlalchemy.orm import Session

from app.schemas.audit_log import (
    AuditLogFilterOptions,
)
from app.services.audit_service import (
    AuditLogPermissionError,
    AuditService,
)
from tests.factories import (
    create_administrator,
    create_audit_log,
    create_user,
)


def test_standard_user_cannot_list_audit_logs(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    create_audit_log(
        db,
        action="task_created",
        summary="Protected audit event.",
    )

    with pytest.raises(
        AuditLogPermissionError,
    ):
        AuditService.get_log_page(
            db,
            actor=user,
        )


def test_standard_user_cannot_filter_audit_logs(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    audit_log = create_audit_log(
        db,
        action="company_created",
        summary="Filtered protected event.",
        entity_type="company",
        entity_id=42,
    )

    with pytest.raises(
        AuditLogPermissionError,
    ):
        AuditService.get_log_page(
            db,
            actor=user,
            filters=AuditLogFilterOptions(
                search="protected",
                action=audit_log.action,
                entity_type=audit_log.entity_type,
                entity_id=audit_log.entity_id,
            ),
        )


def test_standard_user_cannot_view_audit_detail(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    audit_log = create_audit_log(
        db,
        action="settings_updated",
        summary="Protected audit detail.",
        metadata_json={
            "protected_value": "hidden",
        },
    )

    with pytest.raises(
        AuditLogPermissionError,
    ):
        AuditService.get_log_detail(
            db,
            actor=user,
            audit_log_id=audit_log.id,
        )


def test_company_manager_cannot_view_company_audit_data(
    db: Session,
) -> None:
    manager = create_user(
        db,
    )

    audit_log = create_audit_log(
        db,
        action="company_updated",
        summary="Company manager protected entry.",
        entity_type="company",
        entity_id=100,
    )

    with pytest.raises(
        AuditLogPermissionError,
    ):
        AuditService.get_log_detail(
            db,
            actor=manager,
            audit_log_id=audit_log.id,
        )


def test_inactive_administrator_cannot_view_audit_logs(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        is_active=False,
    )

    create_audit_log(
        db,
        action="task_created",
        summary="Inactive administrator protected entry.",
    )

    with pytest.raises(
        AuditLogPermissionError,
        match="administrator account is not available",
    ):
        AuditService.get_log_page(
            db,
            actor=administrator,
        )


def test_anonymised_administrator_cannot_view_audit_logs(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        is_active=False,
        is_anonymised=True,
    )

    create_audit_log(
        db,
        action="task_created",
        summary="Anonymised administrator protected entry.",
    )

    with pytest.raises(
        AuditLogPermissionError,
    ):
        AuditService.get_log_page(
            db,
            actor=administrator,
        )


def test_administrator_can_view_all_audit_entities(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    first = create_audit_log(
        db,
        action="company_created",
        summary="First protected company event.",
        entity_type="company",
        entity_id=1,
    )

    second = create_audit_log(
        db,
        action="task_created",
        summary="Second protected task event.",
        entity_type="task",
        entity_id=2,
    )

    result = AuditService.get_log_page(
        db,
        actor=administrator,
        filters=AuditLogFilterOptions(
            page_size=100,
        ),
    )

    result_ids = {
        audit_log.id
        for audit_log in result.logs
    }

    assert first.id in result_ids
    assert second.id in result_ids


def test_audit_filter_choices_are_administrator_only(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    create_audit_log(
        db,
        action="task_created",
        summary="Filter choice event.",
        entity_type="task",
    )

    with pytest.raises(
        AuditLogPermissionError,
    ):
        AuditService.get_filter_choices(
            db,
            actor=user,
        )