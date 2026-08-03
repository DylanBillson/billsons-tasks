from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.constants import CompanyRole
from app.core.timezone import utc_now
from app.schemas.dashboard import (
    DashboardCompanySummary,
    DashboardData,
    DashboardMetrics,
    DashboardTaskSummary,
)
from app.services.dashboard_service import (
    DashboardAccessError,
    DashboardService,
    DashboardServiceError,
)
from tests.factories import (
    create_administrator,
    create_company,
    create_company_membership,
    create_section,
    create_section_list,
    create_section_membership,
    create_task,
    create_task_assignee,
    create_user,
)


def _create_context(
    db: Session,
):
    company = create_company(
        db,
        name="Dashboard Company",
    )

    creator = create_user(
        db,
        display_name="Section Creator",
    )

    create_company_membership(
        db,
        company=company,
        user=creator,
        role=CompanyRole.MANAGER,
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
        name="To Do",
    )

    return (
        company,
        creator,
        section,
        section_list,
    )


def test_get_dashboard_returns_dashboard_data_for_administrator(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    (
        company,
        creator,
        section,
        section_list,
    ) = _create_context(
        db,
    )

    assignee = create_user(
        db,
        display_name="Assigned User",
    )

    create_company_membership(
        db,
        company=company,
        user=assignee,
        role=CompanyRole.EMPLOYEE,
    )

    create_section_membership(
        db,
        section=section,
        user=assignee,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Due Soon Task",
        due_at=utc_now() + timedelta(
            days=2,
        ),
    )

    create_task_assignee(
        db,
        task=task,
        user=assignee,
    )

    result = DashboardService.get_dashboard(
        db,
        actor=administrator,
    )

    assert isinstance(
        result,
        DashboardData,
    )

    assert result.is_administrator_view is True

    assert isinstance(
        result.metrics,
        DashboardMetrics,
    )

    assert result.metrics.company_count == 1
    assert result.metrics.section_count == 1
    assert result.metrics.active_user_count == 3
    assert result.metrics.open_task_count == 1
    assert result.metrics.overdue_task_count == 0
    assert result.metrics.completed_task_count == 0
    assert result.metrics.deleted_task_count == 0

    assert result.companies == [
        DashboardCompanySummary(
            id=company.id,
            name=company.name,
            section_count=1,
            open_task_count=1,
            overdue_task_count=0,
            completed_task_count=0,
        ),
    ]

    assert len(
        result.due_soon_tasks,
    ) == 1

    task_summary = result.due_soon_tasks[0]

    assert isinstance(
        task_summary,
        DashboardTaskSummary,
    )

    assert task_summary.id == task.id
    assert task_summary.title == "Due Soon Task"
    assert task_summary.company_id == company.id
    assert task_summary.company_name == company.name
    assert task_summary.section_id == section.id
    assert task_summary.section_name == section.name
    assert task_summary.section_list_id == section_list.id
    assert task_summary.section_list_name == section_list.name
    assert task_summary.state == "open"
    assert task_summary.assignee_names == [
        "Assigned User",
    ]


def test_get_dashboard_returns_restricted_standard_user_view(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    (
        accessible_company,
        _,
        _,
        accessible_list,
    ) = _create_context(
        db,
    )

    create_company_membership(
        db,
        company=accessible_company,
        user=user,
        role=CompanyRole.EMPLOYEE,
    )

    accessible_section = accessible_list.section

    create_section_membership(
        db,
        section=accessible_section,
        user=user,
    )

    accessible_task = create_task(
        db,
        section_list=accessible_list,
        created_by=accessible_section.created_by,
        title="Accessible Task",
        due_at=utc_now() + timedelta(
            days=1,
        ),
    )

    hidden_creator = create_user(
        db,
    )

    hidden_company = create_company(
        db,
        name="Hidden Company",
    )

    create_company_membership(
        db,
        company=hidden_company,
        user=hidden_creator,
        role=CompanyRole.MANAGER,
    )

    hidden_section = create_section(
        db,
        company=hidden_company,
        created_by=hidden_creator,
    )

    hidden_list = create_section_list(
        db,
        section=hidden_section,
    )

    create_task(
        db,
        section_list=hidden_list,
        created_by=hidden_creator,
        title="Hidden Task",
        due_at=utc_now() + timedelta(
            days=1,
        ),
    )

    result = DashboardService.get_dashboard(
        db,
        actor=user,
    )

    assert result.is_administrator_view is False
    assert result.metrics.active_user_count is None
    assert result.metrics.company_count == 1
    assert result.metrics.section_count == 1
    assert result.metrics.open_task_count == 1

    assert [
        company.id
        for company in result.companies
    ] == [
        accessible_company.id,
    ]

    assert [
        task.id
        for task in result.due_soon_tasks
    ] == [
        accessible_task.id,
    ]

    assert all(
        task.title != "Hidden Task"
        for task in result.recent_tasks
    )


def test_get_dashboard_includes_overdue_completed_and_deleted_counts(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    (
        _,
        creator,
        _,
        section_list,
    ) = _create_context(
        db,
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Open",
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Overdue",
        due_at=utc_now() - timedelta(
            days=1,
        ),
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Completed",
        completed_by=creator,
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Deleted",
        deleted_by=creator,
    )

    result = DashboardService.get_dashboard(
        db,
        actor=administrator,
    )

    assert result.metrics.open_task_count == 2
    assert result.metrics.overdue_task_count == 1
    assert result.metrics.completed_task_count == 1
    assert result.metrics.deleted_task_count == 1


def test_get_dashboard_excludes_task_outside_due_soon_window(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    (
        _,
        creator,
        _,
        section_list,
    ) = _create_context(
        db,
    )

    included = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Included",
        due_at=utc_now() + timedelta(
            days=2,
        ),
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Excluded",
        due_at=utc_now() + timedelta(
            days=8,
        ),
    )

    result = DashboardService.get_dashboard(
        db,
        actor=administrator,
        due_soon_days=7,
    )

    assert [
        task.id
        for task in result.due_soon_tasks
    ] == [
        included.id,
    ]


def test_get_dashboard_applies_company_and_task_limits(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    first_creator = create_user(
        db,
    )

    first_company = create_company(
        db,
        name="A Company",
    )

    first_section = create_section(
        db,
        company=first_company,
        created_by=first_creator,
    )

    first_list = create_section_list(
        db,
        section=first_section,
    )

    first_task = create_task(
        db,
        section_list=first_list,
        created_by=first_creator,
        title="First Task",
        due_at=utc_now() + timedelta(
            hours=1,
        ),
    )

    second_creator = create_user(
        db,
    )

    second_company = create_company(
        db,
        name="B Company",
    )

    second_section = create_section(
        db,
        company=second_company,
        created_by=second_creator,
    )

    second_list = create_section_list(
        db,
        section=second_section,
    )

    create_task(
        db,
        section_list=second_list,
        created_by=second_creator,
        title="Second Task",
        due_at=utc_now() + timedelta(
            hours=2,
        ),
    )

    result = DashboardService.get_dashboard(
        db,
        actor=administrator,
        company_limit=1,
        task_limit=1,
    )

    assert len(
        result.companies,
    ) == 1

    assert result.companies[0].name == "A Company"

    assert len(
        result.due_soon_tasks,
    ) == 1

    assert result.due_soon_tasks[0].id == first_task.id

    assert len(
        result.recent_tasks,
    ) == 1


@pytest.mark.parametrize(
    (
        "due_soon_days",
        "company_limit",
        "task_limit",
        "message",
    ),
    [
        (
            0,
            20,
            10,
            "due-soon period",
        ),
        (
            7,
            0,
            10,
            "company limit",
        ),
        (
            7,
            20,
            0,
            "task limit",
        ),
    ],
)
def test_get_dashboard_rejects_invalid_limits(
    db: Session,
    due_soon_days: int,
    company_limit: int,
    task_limit: int,
    message: str,
) -> None:
    administrator = create_administrator(
        db,
    )

    with pytest.raises(
        DashboardServiceError,
        match=message,
    ):
        DashboardService.get_dashboard(
            db,
            actor=administrator,
            due_soon_days=due_soon_days,
            company_limit=company_limit,
            task_limit=task_limit,
        )


def test_get_dashboard_rejects_inactive_user(
    db: Session,
) -> None:
    inactive_user = create_user(
        db,
        is_active=False,
    )

    with pytest.raises(
        DashboardAccessError,
        match="active user account",
    ):
        DashboardService.get_dashboard(
            db,
            actor=inactive_user,
        )


def test_get_dashboard_rejects_anonymised_user(
    db: Session,
) -> None:
    anonymised_user = create_user(
        db,
        is_active=False,
        is_anonymised=True,
    )

    with pytest.raises(
        DashboardAccessError,
        match="active user account",
    ):
        DashboardService.get_dashboard(
            db,
            actor=anonymised_user,
        )


def test_build_task_summary_preserves_task_state(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        section_list,
    ) = _create_context(
        db,
    )

    overdue_task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Overdue Task",
        due_at=utc_now() - timedelta(
            hours=1,
        ),
    )

    summary = DashboardService._build_task_summary(
        overdue_task,
    )

    assert summary == DashboardTaskSummary(
        id=overdue_task.id,
        title=overdue_task.title,
        company_id=company.id,
        company_name=company.name,
        section_id=section.id,
        section_name=section.name,
        section_list_id=section_list.id,
        section_list_name=section_list.name,
        due_at=overdue_task.due_at,
        updated_at=overdue_task.updated_at,
        state="overdue",
        assignee_names=[],
    )