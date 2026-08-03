from datetime import timedelta

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


def _create_assigned_task(
    db: Session,
    *,
    user,
    creator,
    company_name: str,
    section_name: str,
    title: str,
    description: str | None = None,
    due_at=None,
    completed: bool = False,
):
    company = create_company(
        db,
        name=company_name,
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
        name="To Do",
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title=title,
        description=description,
        due_at=due_at,
        completed_by=(
            creator
            if completed
            else None
        ),
    )

    create_task_assignee(
        db,
        task=task,
        user=user,
    )

    return (
        company,
        section,
        task,
    )


def test_filter_my_tasks_by_completed_state(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    creator = create_user(
        db,
    )

    _create_assigned_task(
        db,
        user=user,
        creator=creator,
        company_name="State Company",
        section_name="Open Section",
        title="Open Filter Task",
    )

    _, _, completed_task = _create_assigned_task(
        db,
        user=user,
        creator=creator,
        company_name="Completed Company",
        section_name="Completed Section",
        title="Completed Filter Task",
        completed=True,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        "/my-tasks?state=completed",
    )

    assert response.status_code == 200
    assert completed_task.title in response.text
    assert "Open Filter Task" not in response.text


def test_filter_my_tasks_by_overdue_state(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    creator = create_user(
        db,
    )

    _, _, overdue_task = _create_assigned_task(
        db,
        user=user,
        creator=creator,
        company_name="Overdue Company",
        section_name="Overdue Section",
        title="Overdue Filter Task",
        due_at=utc_now() - timedelta(
            hours=1,
        ),
    )

    _create_assigned_task(
        db,
        user=user,
        creator=creator,
        company_name="Future Company",
        section_name="Future Section",
        title="Future Filter Task",
        due_at=utc_now() + timedelta(
            days=1,
        ),
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        "/my-tasks?state=overdue",
    )

    assert response.status_code == 200
    assert overdue_task.title in response.text
    assert "Future Filter Task" not in response.text


def test_filter_my_tasks_by_company(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    creator = create_user(
        db,
    )

    visible_company, _, visible_task = _create_assigned_task(
        db,
        user=user,
        creator=creator,
        company_name="Visible Filter Company",
        section_name="Visible Section",
        title="Visible Company Task",
    )

    _create_assigned_task(
        db,
        user=user,
        creator=creator,
        company_name="Hidden Filter Company",
        section_name="Hidden Section",
        title="Hidden Company Task",
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
            f"?state=all&company_id={visible_company.id}"
        ),
    )

    assert response.status_code == 200
    assert visible_task.title in response.text
    assert "Hidden Company Task" not in response.text


def test_filter_my_tasks_by_section(
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
        name="Section Filter Company",
    )

    first_section = create_section(
        db,
        company=company,
        created_by=creator,
        name="First Filter Section",
    )

    second_section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Second Filter Section",
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
        title="First Section Task",
    )

    second_task = create_task(
        db,
        section_list=second_list,
        created_by=creator,
        title="Second Section Task",
    )

    create_task_assignee(
        db,
        task=first_task,
        user=user,
    )

    create_task_assignee(
        db,
        task=second_task,
        user=user,
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
            f"&section_id={first_section.id}"
        ),
    )

    assert response.status_code == 200
    assert first_task.title in response.text
    assert second_task.title not in response.text


def test_filter_my_tasks_by_search(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    creator = create_user(
        db,
    )

    _, _, matching = _create_assigned_task(
        db,
        user=user,
        creator=creator,
        company_name="Search Company",
        section_name="Search Section",
        title="Order coffee beans",
    )

    _create_assigned_task(
        db,
        user=user,
        creator=creator,
        company_name="Other Search Company",
        section_name="Other Search Section",
        title="Clean the cellar",
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        "/my-tasks?state=all&search=coffee",
    )

    assert response.status_code == 200
    assert matching.title in response.text
    assert "Clean the cellar" not in response.text


def test_invalid_filter_returns_validation_response(
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
        "/my-tasks?state=not-a-state",
    )

    assert response.status_code == 422
    assert "Check the selected filters" in response.text