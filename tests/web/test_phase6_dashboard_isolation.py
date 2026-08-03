from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
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
    _, session_token, csrf_token = (
        create_auth_session(
            db,
            user=user,
        )
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


def test_global_dashboard_excludes_inaccessible_company(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    _, accessible_company, accessible_section, _ = (
        _create_company_task(
            db,
            company_name="Accessible Phase Six Company",
            task_title="Accessible Phase Six Task",
        )
    )

    _, hidden_company, _, _ = _create_company_task(
        db,
        company_name="Hidden Phase Six Company",
        task_title="Hidden Phase Six Task",
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

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        "/",
    )

    assert response.status_code == 200

    assert accessible_company.name in response.text
    assert hidden_company.name not in response.text


def test_global_dashboard_excludes_inaccessible_section_task(
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
        name="Section Isolation Company",
    )

    create_company_membership(
        db,
        company=company,
        user=user,
    )

    visible_section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Visible Phase Six Section",
    )

    hidden_section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Hidden Phase Six Section",
    )

    create_section_membership(
        db,
        section=visible_section,
        user=user,
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
        created_by=creator,
        title="Visible Phase Six Task",
    )

    hidden_task = create_task(
        db,
        section_list=hidden_list,
        created_by=creator,
        title="Hidden Phase Six Task",
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

    assert visible_section.name in response.text
    assert hidden_section.name not in response.text

    if visible_task.title in response.text:
        assert hidden_task.title not in response.text


def test_company_dashboard_rejects_outsider(
    client: TestClient,
    db: Session,
) -> None:
    outsider = create_user(
        db,
    )

    company = create_company(
        db,
        name="Protected Phase Six Company",
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=outsider,
    )

    response = client.get(
        f"/companies/{company.id}/dashboard",
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert response.headers[
        "location"
    ].startswith(
        "/companies?error=",
    )


def test_company_dashboard_does_not_expose_hidden_section(
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
        name="Dashboard Section Isolation Company",
    )

    create_company_membership(
        db,
        company=company,
        user=user,
    )

    visible_section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Visible Company Dashboard Section",
    )

    hidden_section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Hidden Company Dashboard Section",
    )

    create_section_membership(
        db,
        section=visible_section,
        user=user,
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
    assert visible_section.name in response.text
    assert hidden_section.name not in response.text


def test_my_tasks_excludes_other_users_assignment(
    client: TestClient,
    db: Session,
) -> None:
    first_user = create_user(
        db,
    )

    second_user = create_user(
        db,
    )

    creator = create_user(
        db,
    )

    company = create_company(
        db,
        name="My Tasks Phase Six Company",
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

    first_task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="First User Phase Six Task",
    )

    second_task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Second User Phase Six Task",
    )

    for user in (
        first_user,
        second_user,
    ):
        create_company_membership(
            db,
            company=company,
            user=user,
        )

        create_section_membership(
            db,
            section=section,
            user=user,
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

    _authenticate(
        client,
        db,
        user=first_user,
    )

    response = client.get(
        "/my-tasks?state=all",
    )

    assert response.status_code == 200
    assert first_task.title in response.text
    assert second_task.title not in response.text


def test_administrator_dashboard_can_include_all_companies(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    first_company = create_company(
        db,
        name="First Global Administrator Company",
    )

    second_company = create_company(
        db,
        name="Second Global Administrator Company",
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
    assert first_company.name in response.text
    assert second_company.name in response.text