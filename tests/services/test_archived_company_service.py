from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import AuditAction
from app.models.audit_log import AuditLog
from app.services.company_service import (
    CompanyService,
)
from tests.factories import (
    create_administrator,
    create_company,
    create_company_membership,
    create_user,
)


def test_administrator_lists_archived_companies(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    active = create_company(
        db,
        name="Active Company",
    )

    archived = create_company(
        db,
        name="Archived Company",
        is_archived=True,
    )

    result = CompanyService.list_companies_for_actor(
        db,
        actor=administrator,
        include_archived=True,
    )

    assert result == [
        active,
        archived,
    ]


def test_standard_user_lists_only_their_companies(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    assigned_archived = create_company(
        db,
        name="Assigned Archived Company",
        is_archived=True,
    )

    create_company(
        db,
        name="Unassigned Archived Company",
        is_archived=True,
    )

    create_company_membership(
        db,
        company=assigned_archived,
        user=user,
    )

    result = CompanyService.list_companies_for_actor(
        db,
        actor=user,
        include_archived=True,
    )

    assert result == [
        assigned_archived,
    ]


def test_restore_archived_company(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    company = create_company(
        db,
        name="Restored Company",
        is_archived=True,
    )

    result = CompanyService.set_archived_status_by_id(
        db,
        actor=administrator,
        company_id=company.id,
        is_archived=False,
        commit=False,
    )

    assert result is company
    assert company.is_archived is False


def test_restore_archived_company_records_audit_log(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    company = create_company(
        db,
        name="Audited Restored Company",
        is_archived=True,
    )

    CompanyService.set_archived_status_by_id(
        db,
        actor=administrator,
        company_id=company.id,
        is_archived=False,
        ip_address="192.0.2.50",
        user_agent="pytest archive service",
        commit=False,
    )

    audit_log = db.scalar(
        select(
            AuditLog,
        ).where(
            AuditLog.action
            == AuditAction.COMPANY_RESTORED.value,
            AuditLog.entity_type
            == "company",
            AuditLog.entity_id
            == company.id,
        ),
    )

    assert audit_log is not None
    assert audit_log.user_id == administrator.id
    assert audit_log.metadata_json[
        "name"
    ] == company.name
    assert audit_log.metadata_json[
        "is_archived"
    ] is False
    assert audit_log.ip_address == "192.0.2.50"
    assert audit_log.user_agent == (
        "pytest archive service"
    )


def test_restoring_active_company_is_idempotent(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    company = create_company(
        db,
        is_archived=False,
    )

    result = CompanyService.set_archived_status_by_id(
        db,
        actor=administrator,
        company_id=company.id,
        is_archived=False,
        commit=False,
    )

    audit_logs = list(
        db.scalars(
            select(
                AuditLog,
            ).where(
                AuditLog.action
                == AuditAction.COMPANY_RESTORED.value,
                AuditLog.entity_type
                == "company",
                AuditLog.entity_id
                == company.id,
            ),
        ).all(),
    )

    assert result is company
    assert company.is_archived is False
    assert audit_logs == []