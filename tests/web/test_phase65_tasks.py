from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import CompanyRole
from app.services.task_history_service import TaskHistoryService
from tests.factories import (
    create_auth_session,
    create_company,
    create_company_membership,
    create_section,
    create_section_list,
    create_task,
    create_task_comment,
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



def _create_task_context(db: Session):
    user = create_user(
        db,
        display_name="Phase 6.5 Task User",
    )
    company = create_company(db)
    create_company_membership(
        db,
        company=company,
        user=user,
        role=CompanyRole.MANAGER,
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
        title="Phase 6.5 Task",
        description="Prominent Phase 6.5 description.",
        due_at=datetime(
            2026,
            8,
            7,
            11,
            0,
            tzinfo=UTC,
        ),
    )
    comment = create_task_comment(
        db,
        task=task,
        user=user,
        body="Phase 6.5 comment bubble.",
    )
    comment.created_at = datetime(
        2026,
        8,
        3,
        18,
        55,
        tzinfo=UTC,
    )
    TaskHistoryService.record_created(
        db,
        task=task,
        actor=user,
        commit=False,
    )
    db.commit()
    return user, task


def test_phase65_task_detail_layout(
    client: TestClient,
    db: Session,
) -> None:
    user, task = _create_task_context(db)
    _authenticate(client, db, user=user)

    response = client.get(
        f"/tasks/{task.id}",
    )

    assert response.status_code == 200
    assert "task-description-card" in response.text
    assert "Prominent Phase 6.5 description." in response.text
    assert "task-comments-card" in response.text
    assert "task-comment" in response.text
    assert "Phase 6.5 comment bubble." in response.text
    assert "19:55 03/08/26" in response.text
    assert "task-detail-columns" in response.text
    assert "task-information-card" in response.text
    assert "task-history-card" in response.text
    assert "12:00 07/08/26" in response.text


def test_phase65_comments_precede_detail_columns(
    client: TestClient,
    db: Session,
) -> None:
    user, task = _create_task_context(db)
    _authenticate(client, db, user=user)

    response = client.get(
        f"/tasks/{task.id}",
    )

    comments_position = response.text.index(
        'id="task-comments-heading"',
    )
    columns_position = response.text.index(
        'class="task-detail-columns"',
    )

    assert comments_position < columns_position


def test_phase65_task_create_uses_aligned_assignee_list(
    client: TestClient,
    db: Session,
) -> None:
    user, task = _create_task_context(db)
    _authenticate(client, db, user=user)

    response = client.get(
        f"/section-lists/{task.section_list_id}/tasks/create",
    )

    assert response.status_code == 200
    assert "task-assignee-choice-list" in response.text
    assert "task-assignee-choice-control" in response.text
    assert "task-assignee-choice-user" in response.text
