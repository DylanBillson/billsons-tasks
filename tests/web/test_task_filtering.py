from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import CompanyRole
from app.core.timezone import utc_now
from tests.factories import (
    create_auth_session,
    create_company,
    create_company_membership,
    create_section,
    create_section_list,
    create_task,
    create_task_assignee,
    create_user,
)


def _authenticate(
    client: TestClient,
    db: Session,
    *,
    user,
) -> None:
    _, session_token, csrf_token = create_auth_session(
        db,
        user=user,
    )
    db.commit()

    client.cookies.set(
        settings.session_cookie_name,
        session_token,
    )
    client.cookies.set(
        f"{settings.session_cookie_name}_csrf",
        csrf_token,
    )


def _create_context(
    db: Session,
):
    company = create_company(db)

    creator = create_user(db)

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

    first_list = create_section_list(
        db,
        section=section,
        name="To Do",
    )

    second_list = create_section_list(
        db,
        section=section,
        name="In Progress",
    )

    return creator, section, first_list, second_list


def test_filter_tasks_by_search_text(
    client: TestClient,
    db: Session,
) -> None:
    creator, section, first_list, _ = (
        _create_context(db)
    )

    create_task(
        db,
        section_list=first_list,
        created_by=creator,
        title="Order coffee beans",
    )

    create_task(
        db,
        section_list=first_list,
        created_by=creator,
        title="Clean the cellar",
    )
    db.commit()

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.get(
        f"/sections/{section.id}",
        params={
            "search": "coffee",
        },
    )

    assert response.status_code == 200
    assert "Order coffee beans" in response.text
    assert "Clean the cellar" not in response.text


def test_filter_tasks_by_list(
    client: TestClient,
    db: Session,
) -> None:
    creator, section, first_list, second_list = (
        _create_context(db)
    )

    create_task(
        db,
        section_list=first_list,
        created_by=creator,
        title="First List Task",
    )

    create_task(
        db,
        section_list=second_list,
        created_by=creator,
        title="Second List Task",
    )
    db.commit()

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.get(
        f"/sections/{section.id}",
        params={
            "section_list_id": first_list.id,
        },
    )

    assert response.status_code == 200
    assert "First List Task" in response.text
    assert "Second List Task" not in response.text


def test_filter_tasks_by_assignee(
    client: TestClient,
    db: Session,
) -> None:
    creator, section, section_list, _ = (
        _create_context(db)
    )

    assignee = create_user(db)

    create_company_membership(
        db,
        company=section.company,
        user=assignee,
    )

    from tests.factories import create_section_membership

    create_section_membership(
        db,
        section=section,
        user=assignee,
    )

    assigned_task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Assigned Task",
    )

    create_task_assignee(
        db,
        task=assigned_task,
        user=assignee,
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Unassigned Task",
    )
    db.commit()

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.get(
        f"/sections/{section.id}",
        params={
            "assignee_user_id": assignee.id,
        },
    )

    assert response.status_code == 200
    assert "Assigned Task" in response.text
    assert "Unassigned Task" not in response.text


def test_filter_completed_tasks(
    client: TestClient,
    db: Session,
) -> None:
    creator, section, section_list, _ = (
        _create_context(db)
    )

    completed = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Completed Task",
        completed_by=creator,
    )

    open_task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Open Task",
    )
    db.commit()

    assert completed.is_completed is True
    assert open_task.is_completed is False

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.get(
        f"/sections/{section.id}",
        params={
            "state": "completed",
        },
    )

    assert response.status_code == 200
    assert "Completed Task" in response.text
    assert "Open Task" not in response.text


def test_filter_overdue_tasks(
    client: TestClient,
    db: Session,
) -> None:
    creator, section, section_list, _ = (
        _create_context(db)
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Overdue Task",
        due_at=utc_now() - timedelta(days=1),
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Future Task",
        due_at=utc_now() + timedelta(days=1),
    )
    db.commit()

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.get(
        f"/sections/{section.id}",
        params={
            "state": "overdue",
        },
    )

    assert response.status_code == 200
    assert "Overdue Task" in response.text
    assert "Future Task" not in response.text


def test_foreign_list_filter_does_not_expose_tasks(
    client: TestClient,
    db: Session,
) -> None:
    creator, section, section_list, _ = (
        _create_context(db)
    )

    other_section = create_section(
        db,
        company=section.company,
        created_by=creator,
        name="Other Section",
    )

    foreign_list = create_section_list(
        db,
        section=other_section,
    )

    create_task(
        db,
        section_list=foreign_list,
        created_by=creator,
        title="Foreign Filter Task",
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Local Task",
    )
    db.commit()

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.get(
        f"/sections/{section.id}",
        params={
            "section_list_id": foreign_list.id,
        },
    )

    assert response.status_code == 200
    assert "Foreign Filter Task" not in response.text