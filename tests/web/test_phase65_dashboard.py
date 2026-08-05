from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from tests.factories import (
    create_administrator,
    create_auth_session,
    create_company,
    create_section,
    create_section_list,
    create_task,
    create_user,
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



def test_phase65_dashboard_recent_tasks_are_separated_and_scrollable(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(db)
    creator = create_user(db)
    company = create_company(
        db,
        name="Phase 6.5 Dashboard Company",
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
        title="Phase 6.5 Recent Task",
    )
    task.updated_at = datetime(
        2026,
        8,
        7,
        11,
        0,
        tzinfo=UTC,
    )

    db.add(task)
    db.commit()
    _authenticate(client, db, user=administrator)

    response = client.get("/")

    assert response.status_code == 200
    assert "dashboard-balanced-grid" in response.text
    assert "dashboard-panel-scroll" in response.text
    assert "dashboard-task-list" in response.text
    assert "dashboard-task-item" in response.text
    assert "Phase 6.5 Recent Task" in response.text
    assert "12:00 07/08/26" in response.text


def test_phase65_dashboard_due_and_recent_panels_share_grid(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(db)
    _authenticate(client, db, user=user)

    response = client.get("/")

    assert response.status_code == 200

    grid_start = response.text.index(
        "dashboard-grid dashboard-balanced-grid",
    )
    companies_start = response.text.index(
        'id="dashboard-companies-heading"',
    )
    grid_html = response.text[
        grid_start:companies_start
    ]

    assert 'id="due-soon-heading"' in grid_html
    assert 'id="recent-tasks-heading"' in grid_html
