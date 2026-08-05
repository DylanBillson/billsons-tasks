from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from tests.factories import (
    create_auth_session,
    create_company,
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



def test_phase65_my_tasks_overview_layout(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(db)
    db.commit()
    _authenticate(client, db, user=user)

    response = client.get("/my-tasks")

    assert response.status_code == 200
    assert 'class="my-task-overview"' in response.text
    assert 'class="my-task-summary"' in response.text
    assert "my-task-filter-card" in response.text
    assert "metric-grid my-task-metric-grid" in response.text
    assert "filter-panel my-task-filter-panel" in response.text
    assert "filter-grid my-task-filter-grid" in response.text


def test_phase65_my_tasks_results_follow_overview(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(db)
    db.commit()
    _authenticate(client, db, user=user)

    response = client.get("/my-tasks")

    overview_position = response.text.index(
        'class="my-task-overview"',
    )
    results_position = response.text.index(
        'id="my-task-results-heading"',
    )

    assert overview_position < results_position


def test_phase65_my_tasks_uses_compact_due_datetime(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(db)
    creator = create_user(db)
    company = create_company(db)
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
        title="Phase 6.5 Assigned Task",
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
    _authenticate(client, db, user=user)

    response = client.get("/my-tasks")

    assert response.status_code == 200
    assert "Phase 6.5 Assigned Task" in response.text
    assert "12:00 07/08/26" in response.text
