from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import CompanyRole
from app.core.timezone import utc_now
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


def test_company_dashboard_requires_authentication(
    client: TestClient,
    db: Session,
) -> None:
    company = create_company(
        db,
    )

    db.commit()

    response = client.get(
        f"/companies/{company.id}/dashboard",
        headers={
            "accept": "text/html",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303


def test_administrator_can_view_company_dashboard(
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
        name="Dashboard Route Company",
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
        title="Company Dashboard Task",
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
        f"/companies/{company.id}/dashboard",
    )

    assert response.status_code == 200
    assert company.name in response.text
    assert section.name in response.text
    assert task.title in response.text
    assert "Company Dashboard" in response.text
    assert "Deleted" in response.text


def test_standard_user_requires_company_membership(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    company = create_company(
        db,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        f"/companies/{company.id}/dashboard",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "/companies?"
    )


def test_company_dashboard_hides_inaccessible_section(
    client: TestClient,
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
        role=CompanyRole.EMPLOYEE,
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

    create_task(
        db,
        section_list=visible_list,
        created_by=user,
        title="Visible Task",
    )

    create_task(
        db,
        section_list=hidden_list,
        created_by=other_creator,
        title="Hidden Task",
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        f"/companies/{company.id}/dashboard",
    )

    assert response.status_code == 200
    assert "Visible Section" in response.text
    assert "Visible Task" in response.text
    assert "Hidden Section" not in response.text
    assert "Hidden Task" not in response.text


def test_assigned_section_is_visible_on_company_dashboard(
    client: TestClient,
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
        name="Assigned Section",
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
        title="Assigned Task",
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        f"/companies/{company.id}/dashboard",
    )

    assert response.status_code == 200
    assert "Assigned Section" in response.text
    assert "Assigned Task" in response.text


def test_company_dashboard_renders_assignee(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    assignee = create_user(
        db,
        display_name="Company Assignee",
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
        f"/companies/{company.id}/dashboard",
    )

    assert response.status_code == 200
    assert "Company Assignee" in response.text


def test_company_detail_links_to_dashboard(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    company = create_company(
        db,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        f"/companies/{company.id}",
    )

    assert response.status_code == 200

    assert (
        f"/companies/{company.id}/dashboard"
        in response.text
    )

def test_company_manager_sees_one_membership_management_link(
    client: TestClient,
    db: Session,
) -> None:
    manager = create_user(
        db,
    )

    company = create_company(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=manager,
    )

    response = client.get(
        f"/companies/{company.id}",
    )

    assert response.status_code == 200

    membership_url = (
        f"http://testserver/companies/"
        f"{company.id}/members"
    )

    assert response.text.count(
        f'href="{membership_url}"',
    ) == 1

    assert "Manage Members" in response.text
    assert "Manage Company Members" not in response.text


def test_company_employee_sees_no_membership_management_link(
    client: TestClient,
    db: Session,
) -> None:
    employee = create_user(
        db,
    )

    company = create_company(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=employee,
        role=CompanyRole.EMPLOYEE,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=employee,
    )

    response = client.get(
        f"/companies/{company.id}",
    )

    assert response.status_code == 200

    assert (
        f"/companies/{company.id}/members"
        not in response.text
    )

    assert "Manage Members" not in response.text
    assert "Manage Company Members" not in response.text