import pytest
from sqlalchemy.orm import Session

from app.auth.permissions import PermissionDeniedError
from app.services.company_service import CompanyService
from app.services.dashboard_service import DashboardService
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


def _create_company_task(
    db: Session,
    *,
    company_name: str,
    task_title: str,
):
    creator = create_user(
        db,
    )

    company = create_company(
        db,
        name=company_name,
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
        title=task_title,
    )

    return (
        creator,
        company,
        section,
        task,
    )


def test_global_dashboard_is_scoped_to_accessible_companies(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    (
        _,
        accessible_company,
        accessible_section,
        accessible_task,
    ) = _create_company_task(
        db,
        company_name="Accessible Dashboard Company",
        task_title="Accessible Dashboard Task",
    )

    (
        _,
        inaccessible_company,
        _,
        inaccessible_task,
    ) = _create_company_task(
        db,
        company_name="Hidden Dashboard Company",
        task_title="Hidden Dashboard Task",
    )

    create_company_membership(
        db,
        company=accessible_company,
        user=user,
    )
    create_section_membership(
        db,
        section=accessible_section,
        user=user,
    )
    db.commit()

    dashboard = DashboardService.get_dashboard(
        db,
        actor=user,
    )

    dashboard_text = str(
        dashboard.model_dump(),
    )

    assert accessible_company.name in dashboard_text
    assert inaccessible_company.name not in dashboard_text
    assert accessible_task.title in dashboard_text
    assert inaccessible_task.title not in dashboard_text

def test_administrator_dashboard_can_include_all_companies(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    _, first_company, _, _ = _create_company_task(
        db,
        company_name="First Administrator Company",
        task_title="First Administrator Task",
    )

    _, second_company, _, _ = _create_company_task(
        db,
        company_name="Second Administrator Company",
        task_title="Second Administrator Task",
    )

    db.commit()

    dashboard = DashboardService.get_dashboard(
        db,
        actor=administrator,
    )

    dashboard_text = str(
        dashboard.model_dump(),
    )

    assert first_company.name in dashboard_text
    assert second_company.name in dashboard_text


def test_outsider_cannot_load_company_dashboard(
    db: Session,
) -> None:
    outsider = create_user(
        db,
    )

    _, company, _, _ = _create_company_task(
        db,
        company_name="Protected Company Dashboard",
        task_title="Protected Dashboard Task",
    )

    db.commit()

    with pytest.raises(
        PermissionDeniedError,
    ):
        CompanyService.get_company_dashboard(
            db,
            actor=outsider,
            company_id=company.id,
        )


def test_company_member_cannot_load_other_company_dashboard(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    _, own_company, _, _ = _create_company_task(
        db,
        company_name="Own Dashboard Company",
        task_title="Own Dashboard Task",
    )

    _, other_company, _, _ = _create_company_task(
        db,
        company_name="Other Dashboard Company",
        task_title="Other Dashboard Task",
    )

    create_company_membership(
        db,
        company=own_company,
        user=user,
    )

    db.commit()

    own_dashboard = CompanyService.get_company_dashboard(
        db,
        actor=user,
        company_id=own_company.id,
    )

    assert own_dashboard[
        "company"
    ].id == own_company.id

    with pytest.raises(
        PermissionDeniedError,
    ):
        CompanyService.get_company_dashboard(
            db,
            actor=user,
            company_id=other_company.id,
        )


def test_my_tasks_service_never_returns_another_users_assignment(
    db: Session,
) -> None:
    first_user = create_user(
        db,
    )

    second_user = create_user(
        db,
    )

    _, company, _, first_task = _create_company_task(
        db,
        company_name="My Tasks Isolation Company",
        task_title="First User Assigned Task",
    )

    section = first_task.section_list.section

    second_task = create_task(
        db,
        section_list=first_task.section_list,
        created_by=first_task.created_by,
        title="Second User Assigned Task",
    )

    create_company_membership(
        db,
        company=company,
        user=first_user,
    )

    create_company_membership(
        db,
        company=company,
        user=second_user,
    )

    create_task_assignee(
        db,
        task=first_task,
        user=first_user,
    )

    create_task_assignee(
        db,
        task=second_task,
        user=second_user,
    )

    db.commit()

    from app.schemas.my_tasks import (
        MyTasksFilterOptions,
    )
    from app.services.task_service import TaskService

    result = TaskService.get_my_tasks(
        db,
        actor=first_user,
        filters=MyTasksFilterOptions(
            state="all",
        ),
    )

    task_ids = {
        task.id
        for task in result.tasks
    }

    assert first_task.id in task_ids
    assert second_task.id not in task_ids
    assert section.company_id == company.id