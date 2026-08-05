from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timezone import utc_now
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


def _create_context(
    db: Session,
):
    user = create_user(
        db,
        display_name="Assigned User",
    )

    creator = create_user(
        db,
    )

    company = create_company(
        db,
        name="My Tasks Route Company",
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
        user,
        creator,
        company,
        section,
        section_list,
    )


def test_my_tasks_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        "/my-tasks",
        headers={
            "accept": "text/html",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert response.headers["location"] == (
        "/login?next_url=%2Fmy-tasks"
    )


def test_my_tasks_returns_json_401_for_api_style_request(
    client: TestClient,
) -> None:
    response = client.get(
        "/my-tasks",
        headers={
            "accept": "application/json",
        },
        follow_redirects=False,
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Authentication is required.",
    }


def test_my_tasks_renders_assigned_open_task(
    client: TestClient,
    db: Session,
) -> None:
    (
        user,
        creator,
        company,
        section,
        section_list,
    ) = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Assigned Route Task",
        due_at=utc_now() + timedelta(
            days=1,
        ),
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
        "/my-tasks",
    )

    assert response.status_code == 200

    assert "My Tasks" in response.text
    assert "Assigned Route Task" in response.text
    assert company.name in response.text
    assert section.name in response.text
    assert section_list.name in response.text


def test_my_tasks_does_not_show_unassigned_task(
    client: TestClient,
    db: Session,
) -> None:
    (
        user,
        creator,
        _,
        _,
        section_list,
    ) = _create_context(
        db,
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Unassigned Route Task",
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        "/my-tasks",
    )

    assert response.status_code == 200
    assert "Unassigned Route Task" not in response.text
    assert "No assigned tasks found" in response.text


def test_my_tasks_defaults_to_open_tasks(
    client: TestClient,
    db: Session,
) -> None:
    (
        user,
        creator,
        _,
        _,
        section_list,
    ) = _create_context(
        db,
    )

    open_task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Open Assigned Task",
    )

    completed_task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Completed Assigned Task",
        completed_by=creator,
    )

    create_task_assignee(
        db,
        task=open_task,
        user=user,
    )

    create_task_assignee(
        db,
        task=completed_task,
        user=user,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        "/my-tasks",
    )

    assert response.status_code == 200
    assert "Open Assigned Task" in response.text
    assert "Completed Assigned Task" not in response.text


def test_my_tasks_renders_empty_state(
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
        "/my-tasks",
    )

    assert response.status_code == 200
    assert "No assigned tasks found" in response.text


def test_my_tasks_contains_task_navigation_link(
    client: TestClient,
    db: Session,
) -> None:
    (
        user,
        creator,
        _,
        _,
        section_list,
    ) = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
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
        "/my-tasks",
    )

    assert response.status_code == 200

    assert (
        f"/tasks/{task.id}"
        in response.text
    )


def test_my_tasks_renders_compact_local_due_datetime(
    client: TestClient,
    db: Session,
) -> None:
    (
        user,
        creator,
        _,
        _,
        section_list,
    ) = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Compact Due Task",
        due_at=datetime(
            2026,
            8,
            7,
            11,
            0,
            tzinfo=UTC,
        ),
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
        "/my-tasks",
    )

    assert response.status_code == 200
    assert "12:00 07/08/26" in response.text
    assert (
        'datetime="2026-08-07T11:00:00+00:00"'
        in response.text
    )


def test_my_tasks_renders_summary_and_filter_regions(
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
        "/my-tasks",
    )

    assert response.status_code == 200
    assert 'class="my-task-overview"' in response.text
    assert 'class="my-task-summary"' in response.text
    assert "my-task-filter-card" in response.text
    assert 'id="my-tasks-summary-heading"' in response.text
    assert 'id="my-task-filters-heading"' in response.text
