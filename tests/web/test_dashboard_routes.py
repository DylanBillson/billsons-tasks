from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.core.timezone import utc_now
from app.core.config import settings
from app.core.constants import CompanyRole
from app.main import app
from app.web.routes.home import router as home_router
from tests.factories import (
    create_administrator,
    create_auth_session,
    create_company,
    create_company_membership,
    create_section,
    create_section_list,
    create_section_membership,
    create_task,
    create_task_assignee,
    create_user,
)


def _home_route_is_registered() -> bool:
    return any(
        route.path == "/"
        and route.name == "home"
        for route in app.routes
    )


if not _home_route_is_registered():
    app.include_router(
        home_router,
    )


def _authenticate(
    client: TestClient,
    db: Session,
    *,
    user,
) -> str:
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

    return csrf_token


def _create_company_context(
    db: Session,
    *,
    company_name: str,
    creator,
):
    company = create_company(
        db,
        name=company_name,
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
        name=f"{company_name} Section",
    )

    section_list = create_section_list(
        db,
        section=section,
        name="To Do",
    )

    return (
        company,
        section,
        section_list,
    )


def test_dashboard_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        "/",
        headers={
            "accept": "text/html",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert response.headers["location"] == (
        "/login?next_url=%2F"
    )


def test_dashboard_returns_json_401_for_api_style_request(
    client: TestClient,
) -> None:
    response = client.get(
        "/",
        headers={
            "accept": "application/json",
        },
        follow_redirects=False,
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Authentication is required.",
    }


def test_administrator_dashboard_renders_global_metrics(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        display_name="Dashboard Administrator",
    )

    creator = create_user(
        db,
    )

    (
        company,
        section,
        section_list,
    ) = _create_company_context(
        db,
        company_name="Global Company",
        creator=creator,
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Global Open Task",
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Global Overdue Task",
        due_at=utc_now() - timedelta(
            days=1,
        ),
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/",
    )

    assert response.status_code == 200

    assert "Dashboard" in response.text
    assert "Dashboard Administrator" in response.text
    assert "System-wide activity" in response.text
    assert "Active Users" in response.text
    assert "Deleted Tasks" in response.text

    assert company.name in response.text
    assert section.name in response.text
    assert "Global Open Task" in response.text
    assert "Global Overdue Task" in response.text


def test_standard_user_dashboard_hides_administrator_metrics(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
        display_name="Standard Dashboard User",
    )

    (
        company,
        _,
        section_list,
    ) = _create_company_context(
        db,
        company_name="Member Company",
        creator=user,
    )

    create_task(
        db,
        section_list=section_list,
        created_by=user,
        title="Visible Member Task",
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        "/",
    )

    assert response.status_code == 200

    assert "Standard Dashboard User" in response.text
    assert "Activity across the companies" in response.text
    assert company.name in response.text
    assert "Visible Member Task" in response.text

    assert "Active Users" not in response.text
    assert "Deleted Tasks" not in response.text


def test_standard_user_dashboard_excludes_inaccessible_company(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    (
        visible_company,
        _,
        visible_list,
    ) = _create_company_context(
        db,
        company_name="Visible Dashboard Company",
        creator=user,
    )

    hidden_creator = create_user(
        db,
    )

    (
        hidden_company,
        _,
        hidden_list,
    ) = _create_company_context(
        db,
        company_name="Hidden Dashboard Company",
        creator=hidden_creator,
    )

    create_task(
        db,
        section_list=visible_list,
        created_by=user,
        title="Visible Dashboard Task",
    )

    create_task(
        db,
        section_list=hidden_list,
        created_by=hidden_creator,
        title="Hidden Dashboard Task",
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        "/",
    )

    assert response.status_code == 200

    assert visible_company.name in response.text
    assert "Visible Dashboard Task" in response.text

    assert hidden_company.name not in response.text
    assert "Hidden Dashboard Task" not in response.text


def test_explicit_section_member_sees_section_tasks(
    client: TestClient,
    db: Session,
) -> None:
    member = create_user(
        db,
    )

    creator = create_user(
        db,
    )

    company = create_company(
        db,
        name="Assigned Company",
    )

    create_company_membership(
        db,
        company=company,
        user=member,
        role=CompanyRole.EMPLOYEE,
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
        name="Assigned Section",
    )

    create_section_membership(
        db,
        section=section,
        user=member,
    )

    section_list = create_section_list(
        db,
        section=section,
        name="Assigned List",
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Assigned Section Task",
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=member,
    )

    response = client.get(
        "/",
    )

    assert response.status_code == 200
    assert company.name in response.text
    assert section.name in response.text
    assert "Assigned Section Task" in response.text


def test_dashboard_renders_due_soon_task(
    client: TestClient,
    db: Session,
) -> None:
    from app.core.timezone import utc_now

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
        company_name="Due Company",
        creator=creator,
    )

    due_task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Task Due Tomorrow",
        due_at=utc_now() + timedelta(
            days=1,
        ),
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/",
    )

    assert response.status_code == 200
    assert "Due Soon" in response.text
    assert due_task.title in response.text
    assert due_task.section_list.name in response.text


def test_dashboard_renders_task_assignee(
    client: TestClient,
    db: Session,
) -> None:
    from app.core.timezone import utc_now

    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    (
        company,
        section,
        section_list,
    ) = _create_company_context(
        db,
        company_name="Assignee Company",
        creator=creator,
    )

    assignee = create_user(
        db,
        display_name="Dashboard Assignee",
    )

    create_company_membership(
        db,
        company=company,
        user=assignee,
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
        title="Assigned Dashboard Task",
        due_at=utc_now() + timedelta(
            days=1,
        ),
    )

    create_task_assignee(
        db,
        task=task,
        user=assignee,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/",
    )

    assert response.status_code == 200
    assert task.title in response.text
    assert "Dashboard Assignee" in response.text


def test_dashboard_renders_empty_states(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        "/",
    )

    assert response.status_code == 200

    assert "Nothing due soon" in response.text
    assert "No recent tasks" in response.text
    assert "No companies available" in response.text


def test_dashboard_excludes_archived_company(
    client: TestClient,
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
        name="Archived Dashboard Company",
        is_archived=True,
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
        title="Archived Dashboard Task",
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/",
    )

    assert response.status_code == 200

    assert company.name not in response.text
    assert "Archived Dashboard Task" not in response.text


def test_dashboard_contains_navigation_links(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    company = create_company(
        db,
        name="Linked Company",
    )

    create_company_membership(
        db,
        company=company,
        user=user,
    )

    section = create_section(
        db,
        company=company,
        created_by=user,
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=user,
        title="Linked Task",
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        "/",
    )

    assert response.status_code == 200

    assert (
        f'href="http://testserver/companies/{company.id}"'
        in response.text
    )

    assert (
        f'href="http://testserver/tasks/{task.id}"'
        in response.text
    )