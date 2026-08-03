from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import PermissionDeniedError
from app.core.constants import AuditAction, CompanyRole
from app.core.timezone import utc_now
from app.models.audit_log import AuditLog
from app.models.company import Company
from app.schemas.company import (
    CompanyCreateRequest,
    CompanyUpdateRequest,
)
from app.services.company_service import (
    CompanyDashboardError,
    CompanyNameAlreadyExistsError,
    CompanyNotFoundError,
    CompanyService,
)
from tests.factories import (
    create_administrator,
    create_company,
    create_company_membership,
    create_section,
    create_section_list,
    create_task,
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

def test_get_company_dashboard_returns_company_data(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    company = create_company(
        db,
        name="Dashboard Company",
    )

    section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Operations",
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Due Soon",
        due_at=utc_now() + timedelta(
            days=1,
        ),
    )

    dashboard = CompanyService.get_company_dashboard(
        db,
        actor=administrator,
        company_id=company.id,
    )

    assert dashboard["company"] is company
    assert dashboard["metrics"]["section_count"] == 1
    assert dashboard["metrics"]["open_task_count"] == 1
    assert dashboard["due_soon_tasks"][0].id == task.id


def test_company_dashboard_scopes_standard_user_sections(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    other_creator = create_user(
        db,
    )

    company = create_company(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=user,
    )

    visible_section = create_section(
        db,
        company=company,
        created_by=user,
        name="Visible Section",
    )

    hidden_section = create_section(
        db,
        company=company,
        created_by=other_creator,
        name="Hidden Section",
    )

    visible_list = create_section_list(
        db,
        section=visible_section,
    )

    hidden_list = create_section_list(
        db,
        section=hidden_section,
    )

    visible_task = create_task(
        db,
        section_list=visible_list,
        created_by=user,
    )

    create_task(
        db,
        section_list=hidden_list,
        created_by=other_creator,
    )

    dashboard = CompanyService.get_company_dashboard(
        db,
        actor=user,
        company_id=company.id,
    )

    assert dashboard["metrics"]["section_count"] == 1

    assert [
        task.id
        for task in dashboard["recent_tasks"]
    ] == [
        visible_task.id,
    ]


def test_company_dashboard_requires_company_access(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    company = create_company(
        db,
    )

    with pytest.raises(
        PermissionDeniedError,
    ):
        CompanyService.get_company_dashboard(
            db,
            actor=user,
            company_id=company.id,
        )


@pytest.mark.parametrize(
    (
        "due_soon_days",
        "task_limit",
    ),
    [
        (
            0,
            10,
        ),
        (
            7,
            0,
        ),
    ],
)
def test_company_dashboard_rejects_invalid_limits(
    db: Session,
    due_soon_days: int,
    task_limit: int,
) -> None:
    administrator = create_administrator(
        db,
    )

    company = create_company(
        db,
    )

    with pytest.raises(
        CompanyDashboardError,
    ):
        CompanyService.get_company_dashboard(
            db,
            actor=administrator,
            company_id=company.id,
            due_soon_days=due_soon_days,
            task_limit=task_limit,
        )