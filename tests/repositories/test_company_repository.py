from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.constants import CompanyRole
from app.core.timezone import utc_now
from app.repositories.company_repository import (
    CompanyRepository,
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


def test_get_dashboard_metrics_returns_company_totals(
    db: Session,
) -> None:
    now = utc_now()

    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    company = create_company(
        db,
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
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
        due_at=now - timedelta(
            days=1,
        ),
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
        completed_by=creator,
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
        deleted_by=creator,
    )

    result = CompanyRepository.get_dashboard_metrics(
        db,
        company_id=company.id,
        actor=administrator,
        now=now,
    )

    assert result == {
        "section_count": 1,
        "member_count": 1,
        "open_task_count": 2,
        "overdue_task_count": 1,
        "completed_task_count": 1,
        "deleted_task_count": 1,
    }


def test_dashboard_metrics_scope_standard_user_sections(
    db: Session,
) -> None:
    now = utc_now()

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
        name="Visible",
    )

    hidden_section = create_section(
        db,
        company=company,
        created_by=other_creator,
        name="Hidden",
    )

    visible_list = create_section_list(
        db,
        section=visible_section,
    )

    hidden_list = create_section_list(
        db,
        section=hidden_section,
    )

    create_task(
        db,
        section_list=visible_list,
        created_by=user,
    )

    create_task(
        db,
        section_list=hidden_list,
        created_by=other_creator,
    )

    result = CompanyRepository.get_dashboard_metrics(
        db,
        company_id=company.id,
        actor=user,
        now=now,
    )

    assert result["section_count"] == 1
    assert result["open_task_count"] == 1


def test_dashboard_metrics_include_assigned_section(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    creator = create_user(
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

    section = create_section(
        db,
        company=company,
        created_by=creator,
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
        created_by=creator,
    )

    result = CompanyRepository.get_dashboard_metrics(
        db,
        company_id=company.id,
        actor=user,
        now=utc_now(),
    )

    assert result["section_count"] == 1
    assert result["open_task_count"] == 1


def test_list_dashboard_due_soon_tasks_is_company_scoped(
    db: Session,
) -> None:
    now = utc_now()

    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    first_company = create_company(
        db,
    )

    second_company = create_company(
        db,
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

    visible = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        due_at=now + timedelta(
            days=1,
        ),
    )

    create_task(
        db,
        section_list=second_list,
        created_by=creator,
        due_at=now + timedelta(
            days=1,
        ),
    )

    result = (
        CompanyRepository.list_dashboard_due_soon_tasks(
            db,
            company_id=first_company.id,
            actor=administrator,
            due_from=now,
            due_to=now + timedelta(
                days=7,
            ),
        )
    )

    assert result == [
        visible,
    ]


def test_dashboard_tasks_load_assignees(
    db: Session,
) -> None:
    now = utc_now()

    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    assignee = create_user(
        db,
    )

    company = create_company(
        db,
    )

    section = create_section(
        db,
        company=company,
        created_by=creator,
    )

    section_list = create_section_list(
        db,
        section=section,
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

    result = (
        CompanyRepository.list_dashboard_due_soon_tasks(
            db,
            company_id=company.id,
            actor=administrator,
            due_from=now,
            due_to=now + timedelta(
                days=7,
            ),
        )
    )

    assert result == [
        task,
    ]

    assert assignment in task.assignees