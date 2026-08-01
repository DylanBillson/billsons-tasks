import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import PermissionDeniedError
from app.core.constants import AuditAction, CompanyRole
from app.models.audit_log import AuditLog
from app.models.company import Company
from app.schemas.company import CompanyCreateRequest, CompanyUpdateRequest
from app.services.company_service import (
    CompanyNameAlreadyExistsError,
    CompanyNotFoundError,
    CompanyService,
)
from tests.factories import (
    create_administrator,
    create_company,
    create_company_membership,
    create_user,
)


def test_require_company_returns_company(db: Session) -> None:
    company = create_company(db)

    assert CompanyService.require_company(
        db,
        company_id=company.id,
    ) is company


def test_require_company_raises_for_missing_company(db: Session) -> None:
    with pytest.raises(
        CompanyNotFoundError,
        match="Company was not found",
    ):
        CompanyService.require_company(db, company_id=999_999)


def test_administrator_lists_all_companies(db: Session) -> None:
    administrator = create_administrator(db)
    first = create_company(db)
    second = create_company(db)

    companies = CompanyService.list_companies_for_actor(
        db,
        actor=administrator,
    )

    assert first in companies
    assert second in companies


def test_standard_user_lists_only_member_companies(db: Session) -> None:
    user = create_user(db)
    visible = create_company(db)
    hidden = create_company(db)
    create_company_membership(db, company=visible, user=user)

    companies = CompanyService.list_companies_for_actor(
        db,
        actor=user,
    )

    assert visible in companies
    assert hidden not in companies


def test_administrator_creates_company(db: Session) -> None:
    administrator = create_administrator(db)

    company = CompanyService.create_company(
        db,
        actor=administrator,
        company_create=CompanyCreateRequest(
            name="Anchor Hotel",
            description="Hospitality operations.",
        ),
    )

    assert company.id is not None
    assert company.name == "Anchor Hotel"
    assert company.description == "Hospitality operations."


def test_non_administrator_cannot_create_company(db: Session) -> None:
    user = create_user(db)

    with pytest.raises(PermissionDeniedError):
        CompanyService.create_company(
            db,
            actor=user,
            company_create=CompanyCreateRequest(name="Denied Company"),
        )


def test_create_company_rejects_duplicate_name(db: Session) -> None:
    administrator = create_administrator(db)
    create_company(db, name="Duplicate Company")

    with pytest.raises(
        CompanyNameAlreadyExistsError,
        match="already exists",
    ):
        CompanyService.create_company(
            db,
            actor=administrator,
            company_create=CompanyCreateRequest(
                name="Duplicate Company",
            ),
        )


def test_create_company_records_audit_log(db: Session) -> None:
    administrator = create_administrator(db)

    company = CompanyService.create_company(
        db,
        actor=administrator,
        company_create=CompanyCreateRequest(name="Audited Company"),
    )

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action == AuditAction.COMPANY_CREATED.value,
            AuditLog.entity_id == company.id,
        )
    )

    assert audit_log is not None
    assert audit_log.user_id == administrator.id


def test_administrator_updates_company(db: Session) -> None:
    administrator = create_administrator(db)
    company = create_company(db, name="Old Name")

    updated = CompanyService.update_company(
        db,
        actor=administrator,
        company=company,
        company_update=CompanyUpdateRequest(
            name="New Name",
            description="Updated description.",
        ),
    )

    assert updated.name == "New Name"
    assert updated.description == "Updated description."


def test_company_manager_cannot_update_company(db: Session) -> None:
    company = create_company(db)
    manager = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    with pytest.raises(PermissionDeniedError):
        CompanyService.update_company(
            db,
            actor=manager,
            company=company,
            company_update=CompanyUpdateRequest(name="Denied Update"),
        )


def test_administrator_archives_and_restores_company(db: Session) -> None:
    administrator = create_administrator(db)
    company = create_company(db)

    CompanyService.set_archived_status(
        db,
        actor=administrator,
        company=company,
        is_archived=True,
    )
    assert company.is_archived is True

    CompanyService.set_archived_status(
        db,
        actor=administrator,
        company=company,
        is_archived=False,
    )
    assert company.is_archived is False


def test_delete_company_removes_record(db: Session) -> None:
    administrator = create_administrator(db)
    company = create_company(db)
    company_id = company.id

    CompanyService.delete_company(
        db,
        actor=administrator,
        company=company,
    )

    assert db.scalar(
        select(Company).where(Company.id == company_id)
    ) is None
