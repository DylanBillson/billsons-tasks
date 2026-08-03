from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.main import app
from app.web.routes.home import router as home_router
from app.web.routes.my_tasks import (
    router as my_tasks_router,
)
from tests.factories import (
    create_auth_session,
    create_company,
    create_section,
    create_section_list,
    create_task,
    create_task_assignee,
    create_user,
)


def _route_is_registered(
    *,
    path: str,
    name: str,
) -> bool:
    return any(
        route.path == path
        and route.name == name
        for route in app.routes
    )


if not _route_is_registered(
    path="/",
    name="home",
):
    app.include_router(
        home_router,
    )


if not _route_is_registered(
    path="/my-tasks",
    name="my_tasks",
):
    app.include_router(
        my_tasks_router,
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


def _create_task_context(
    db: Session,
    *,
    title: str,
):
    creator = create_user(
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
        title=title,
    )

    return (
        company,
        section,
        task,
    )


def test_user_sees_only_tasks_assigned_to_them(
    client: TestClient,
    db: Session,
) -> None:
    first_user = create_user(
        db,
    )

    second_user = create_user(
        db,
    )

    _, _, first_task = _create_task_context(
        db,
        title="First User Task",
    )

    _, _, second_task = _create_task_context(
        db,
        title="Second User Task",
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


def test_company_filter_cannot_expose_another_users_tasks(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    other_user = create_user(
        db,
    )

    company, _, other_task = _create_task_context(
        db,
        title="Other User Company Task",
    )

    create_task_assignee(
        db,
        task=other_task,
        user=other_user,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        (
            "/my-tasks"
            f"?state=all&company_id={company.id}"
        ),
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "/my-tasks?"
    )
    assert "Other User Company Task" not in response.text


def test_section_filter_cannot_expose_another_users_tasks(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    other_user = create_user(
        db,
    )

    company, section, other_task = _create_task_context(
        db,
        title="Other User Section Task",
    )

    create_task_assignee(
        db,
        task=other_task,
        user=other_user,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        (
            "/my-tasks"
            f"?state=all&company_id={company.id}"
            f"&section_id={section.id}"
        ),
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "/my-tasks?"
    )


def test_deleted_assigned_task_is_not_visible(
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
        title="Deleted Assigned Task",
        deleted_by=creator,
    )

    create_task_assignee(
        db,
        task=task,
        user=user,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        "/my-tasks?state=all",
    )

    assert response.status_code == 200
    assert task.title not in response.text


def test_archived_company_task_is_not_visible(
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

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Archived Company Assigned Task",
    )

    create_task_assignee(
        db,
        task=task,
        user=user,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        "/my-tasks?state=all",
    )

    assert response.status_code == 200
    assert task.title not in response.text


def test_archived_section_task_is_not_visible(
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

    section = create_section(
        db,
        company=company,
        created_by=creator,
        is_archived=True,
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Archived Section Assigned Task",
    )

    create_task_assignee(
        db,
        task=task,
        user=user,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        "/my-tasks?state=all",
    )

    assert response.status_code == 200
    assert task.title not in response.text