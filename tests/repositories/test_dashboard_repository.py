from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.constants import CompanyRole
from app.core.timezone import utc_now
from app.repositories.dashboard_repository import (
    DashboardRepository,
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


def _create_company_context(
    db: Session,
    *,
    company_name: str,
    creator,
    company_role: CompanyRole = CompanyRole.MANAGER,
    section_name: str = "Operations",
    list_name: str = "To Do",
):
    company = create_company(
        db,
        name=company_name,
    )

    create_company_membership(
        db,
        company=company,
        user=creator,
        role=company_role,
    )

    section = create_section(
        db,
        company=company,
        created_by=creator,
        name=section_name,
    )

    section_list = create_section_list(
        db,
        section=section,
        name=list_name,
    )

    return (
        company,
        section,
        section_list,
    )


def test_get_metrics_returns_global_administrator_totals(
    db: Session,
) -> None:
    now = utc_now()

    administrator = create_administrator(
        db,
    )

    first_creator = create_user(
        db,
    )

    (
        _,
        _,
        first_list,
    ) = _create_company_context(
        db,
        company_name="First Company",
        creator=first_creator,
    )

    second_creator = create_user(
        db,
    )

    (
        _,
        _,
        second_list,
    ) = _create_company_context(
        db,
        company_name="Second Company",
        creator=second_creator,
    )

    create_task(
        db,
        section_list=first_list,
        created_by=first_creator,
        title="Open Task",
    )

    create_task(
        db,
        section_list=first_list,
        created_by=first_creator,
        title="Overdue Task",
        due_at=now - timedelta(
            days=1,
        ),
    )

    create_task(
        db,
        section_list=second_list,
        created_by=second_creator,
        title="Completed Task",
        completed_by=second_creator,
    )

    create_task(
        db,
        section_list=second_list,
        created_by=second_creator,
        title="Deleted Task",
        deleted_by=second_creator,
    )

    inactive_user = create_user(
        db,
        is_active=False,
    )

    anonymised_user = create_user(
        db,
        is_active=False,
        is_anonymised=True,
    )

    db.flush()

    result = DashboardRepository.get_metrics(
        db,
        actor=administrator,
        now=now,
    )

    assert result == {
        "company_count": 2,
        "section_count": 2,
        "active_user_count": 3,
        "open_task_count": 2,
        "overdue_task_count": 1,
        "completed_task_count": 1,
        "deleted_task_count": 1,
    }

    assert inactive_user.is_active is False
    assert anonymised_user.is_anonymised is True


def test_get_metrics_scopes_standard_user_to_accessible_data(
    db: Session,
) -> None:
    now = utc_now()

    user = create_user(
        db,
    )

    (
        accessible_company,
        accessible_section,
        accessible_list,
    ) = _create_company_context(
        db,
        company_name="Accessible Company",
        creator=user,
    )

    inaccessible_creator = create_user(
        db,
    )

    (
        inaccessible_company,
        inaccessible_section,
        inaccessible_list,
    ) = _create_company_context(
        db,
        company_name="Hidden Company",
        creator=inaccessible_creator,
    )

    create_task(
        db,
        section_list=accessible_list,
        created_by=user,
        title="Accessible Task",
    )

    create_task(
        db,
        section_list=inaccessible_list,
        created_by=inaccessible_creator,
        title="Hidden Task",
    )

    result = DashboardRepository.get_metrics(
        db,
        actor=user,
        now=now,
    )

    assert result == {
        "company_count": 1,
        "section_count": 1,
        "active_user_count": None,
        "open_task_count": 1,
        "overdue_task_count": 0,
        "completed_task_count": 0,
        "deleted_task_count": 0,
    }

    assert accessible_company.id != inaccessible_company.id
    assert accessible_section.id != inaccessible_section.id


def test_get_metrics_includes_explicit_section_membership(
    db: Session,
) -> None:
    now = utc_now()

    user = create_user(
        db,
    )

    company = create_company(
        db,
        name="Member Company",
    )

    create_company_membership(
        db,
        company=company,
        user=user,
        role=CompanyRole.EMPLOYEE,
    )

    section_creator = create_user(
        db,
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

    create_section_membership(
        db,
        section=section,
        user=user,
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    create_task(
        db,
        section_list=section_list,
        created_by=section_creator,
    )

    result = DashboardRepository.get_metrics(
        db,
        actor=user,
        now=now,
    )

    assert result["company_count"] == 1
    assert result["section_count"] == 1
    assert result["open_task_count"] == 1


def test_get_metrics_excludes_archived_companies_sections_and_lists(
    db: Session,
) -> None:
    now = utc_now()

    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    active_company = create_company(
        db,
        name="Active Company",
    )

    create_company_membership(
        db,
        company=active_company,
        user=creator,
        role=CompanyRole.MANAGER,
    )

    active_section = create_section(
        db,
        company=active_company,
        created_by=creator,
        name="Active Section",
    )

    active_list = create_section_list(
        db,
        section=active_section,
        name="Active List",
    )

    archived_list = create_section_list(
        db,
        section=active_section,
        name="Archived List",
        is_archived=True,
    )

    archived_section = create_section(
        db,
        company=active_company,
        created_by=creator,
        name="Archived Section",
        is_archived=True,
    )

    archived_section_list = create_section_list(
        db,
        section=archived_section,
    )

    archived_company = create_company(
        db,
        name="Archived Company",
        is_archived=True,
    )

    archived_company_section = create_section(
        db,
        company=archived_company,
        created_by=creator,
    )

    archived_company_list = create_section_list(
        db,
        section=archived_company_section,
    )

    create_task(
        db,
        section_list=active_list,
        created_by=creator,
        title="Visible Task",
    )

    create_task(
        db,
        section_list=archived_list,
        created_by=creator,
        title="Archived List Task",
    )

    create_task(
        db,
        section_list=archived_section_list,
        created_by=creator,
        title="Archived Section Task",
    )

    create_task(
        db,
        section_list=archived_company_list,
        created_by=creator,
        title="Archived Company Task",
    )

    result = DashboardRepository.get_metrics(
        db,
        actor=administrator,
        now=now,
    )

    assert result["company_count"] == 1
    assert result["section_count"] == 1
    assert result["open_task_count"] == 1


def test_list_company_summaries_returns_task_counts(
    db: Session,
) -> None:
    now = utc_now()

    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    (
        company,
        _,
        section_list,
    ) = _create_company_context(
        db,
        company_name="Summary Company",
        creator=creator,
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
        due_at=now - timedelta(
            hours=1,
        ),
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Completed",
        completed_by=creator,
    )

    result = DashboardRepository.list_company_summaries(
        db,
        actor=administrator,
        now=now,
    )

    assert result == [
        {
            "id": company.id,
            "name": "Summary Company",
            "section_count": 1,
            "open_task_count": 2,
            "overdue_task_count": 1,
            "completed_task_count": 1,
        },
    ]


def test_list_company_summaries_includes_company_without_sections(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    company = create_company(
        db,
        name="Empty Company",
    )

    result = DashboardRepository.list_company_summaries(
        db,
        actor=administrator,
        now=utc_now(),
    )

    assert result == [
        {
            "id": company.id,
            "name": "Empty Company",
            "section_count": 0,
            "open_task_count": 0,
            "overdue_task_count": 0,
            "completed_task_count": 0,
        },
    ]


def test_list_company_summaries_scopes_standard_user(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    (
        accessible_company,
        _,
        accessible_list,
    ) = _create_company_context(
        db,
        company_name="Accessible Company",
        creator=user,
    )

    hidden_creator = create_user(
        db,
    )

    (
        _,
        _,
        hidden_list,
    ) = _create_company_context(
        db,
        company_name="Hidden Company",
        creator=hidden_creator,
    )

    create_task(
        db,
        section_list=accessible_list,
        created_by=user,
    )

    create_task(
        db,
        section_list=hidden_list,
        created_by=hidden_creator,
    )

    result = DashboardRepository.list_company_summaries(
        db,
        actor=user,
        now=utc_now(),
    )

    assert len(result) == 1
    assert result[0]["id"] == accessible_company.id
    assert result[0]["open_task_count"] == 1


def test_list_due_soon_tasks_orders_by_due_date(
    db: Session,
) -> None:
    now = utc_now()

    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    (
        _,
        _,
        section_list,
    ) = _create_company_context(
        db,
        company_name="Due Soon Company",
        creator=creator,
    )

    later = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Later",
        due_at=now + timedelta(
            days=3,
        ),
    )

    first = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="First",
        due_at=now + timedelta(
            hours=2,
        ),
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Overdue",
        due_at=now - timedelta(
            hours=1,
        ),
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Too Far Away",
        due_at=now + timedelta(
            days=10,
        ),
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Completed",
        due_at=now + timedelta(
            days=1,
        ),
        completed_by=creator,
    )

    result = DashboardRepository.list_due_soon_tasks(
        db,
        actor=administrator,
        due_from=now,
        due_to=now + timedelta(
            days=7,
        ),
    )

    assert result == [
        first,
        later,
    ]


def test_list_due_soon_tasks_loads_assignees(
    db: Session,
) -> None:
    now = utc_now()

    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    (
        _,
        _,
        section_list,
    ) = _create_company_context(
        db,
        company_name="Assigned Company",
        creator=creator,
    )

    assignee = create_user(
        db,
        display_name="Assigned User",
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        due_at=now + timedelta(
            days=1,
        ),
    )

    assignment = create_task_assignee(
        db,
        task=task,
        user=assignee,
    )

    result = DashboardRepository.list_due_soon_tasks(
        db,
        actor=administrator,
        due_from=now,
        due_to=now + timedelta(
            days=7,
        ),
    )

    assert result == [
        task,
    ]
    assert assignment in result[0].assignees
    assert result[0].assignees[0].user is assignee


def test_list_recent_tasks_orders_by_updated_at(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    (
        _,
        _,
        section_list,
    ) = _create_company_context(
        db,
        company_name="Recent Company",
        creator=creator,
    )

    older = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Older",
    )

    newer = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Newer",
    )

    older.updated_at = utc_now() - timedelta(
        days=2,
    )

    newer.updated_at = utc_now() - timedelta(
        hours=1,
    )

    db.flush()

    result = DashboardRepository.list_recent_tasks(
        db,
        actor=administrator,
    )

    assert result == [
        newer,
        older,
    ]


def test_list_recent_tasks_excludes_deleted_tasks(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    (
        _,
        _,
        section_list,
    ) = _create_company_context(
        db,
        company_name="Recent Company",
        creator=creator,
    )

    visible = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Visible",
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Deleted",
        deleted_by=creator,
    )

    result = DashboardRepository.list_recent_tasks(
        db,
        actor=administrator,
    )

    assert result == [
        visible,
    ]


def test_repository_limits_company_and_task_results(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    first_company = create_company(
        db,
        name="A Company",
    )

    second_company = create_company(
        db,
        name="B Company",
    )

    first_section = create_section(
        db,
        company=first_company,
        created_by=creator,
    )

    second_section = create_section(
        db,
        company=second_company,
        created_by=creator,
    )

    first_list = create_section_list(
        db,
        section=first_section,
    )

    second_list = create_section_list(
        db,
        section=second_section,
    )

    first_task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        due_at=utc_now() + timedelta(
            hours=1,
        ),
    )

    create_task(
        db,
        section_list=second_list,
        created_by=creator,
        due_at=utc_now() + timedelta(
            hours=2,
        ),
    )

    companies = DashboardRepository.list_company_summaries(
        db,
        actor=administrator,
        now=utc_now(),
        limit=1,
    )

    due_tasks = DashboardRepository.list_due_soon_tasks(
        db,
        actor=administrator,
        due_from=utc_now() - timedelta(
            minutes=1,
        ),
        due_to=utc_now() + timedelta(
            days=7,
        ),
        limit=1,
    )

    assert len(companies) == 1
    assert companies[0]["name"] == "A Company"

    assert due_tasks == [
        first_task,
    ]