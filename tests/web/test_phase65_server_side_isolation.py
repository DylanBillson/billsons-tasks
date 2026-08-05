from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import AuditAction
from app.models.audit_log import AuditLog
from app.services.feedback_service import FeedbackService
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



def test_phase65_section_ui_does_not_bypass_section_isolation(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(db)
    outsider = create_user(db)
    company = create_company(db)
    section = create_section(
        db,
        company=company,
        created_by=outsider,
    )
    db.commit()
    _authenticate(client, db, user=user)

    response = client.get(
        f"/sections/{section.id}",
        follow_redirects=False,
    )

    assert response.status_code in {303, 403, 404}
    assert "task-board" not in response.text


def test_phase65_task_ui_does_not_bypass_task_isolation(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(db)
    outsider = create_user(db)
    company = create_company(db)
    section = create_section(
        db,
        company=company,
        created_by=outsider,
    )
    section_list = create_section_list(
        db,
        section=section,
    )
    task = create_task(
        db,
        section_list=section_list,
        created_by=outsider,
        title="Hidden Phase 6.5 Task",
    )
    db.commit()
    _authenticate(client, db, user=user)

    response = client.get(
        f"/tasks/{task.id}",
        follow_redirects=False,
    )

    assert response.status_code in {303, 403, 404}
    assert "Hidden Phase 6.5 Task" not in response.text
    assert "task-detail-columns" not in response.text


def test_phase65_my_tasks_only_shows_authenticated_users_assignments(
    client: TestClient,
    db: Session,
) -> None:
    first_user = create_user(db)
    second_user = create_user(db)
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

    first_task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="First User Phase 6.5 Task",
    )
    second_task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Second User Phase 6.5 Task",
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
    _authenticate(client, db, user=first_user)

    response = client.get(
        "/my-tasks?state=all",
    )

    assert response.status_code == 200
    assert "First User Phase 6.5 Task" in response.text
    assert "Second User Phase 6.5 Task" not in response.text


def test_phase65_feedback_audit_actor_cannot_be_spoofed(
    client: TestClient,
    db: Session,
) -> None:
    authenticated_user = create_user(db)
    other_user = create_user(db)
    csrf_token = _authenticate(
        client,
        db,
        user=authenticated_user,
    )

    with (
        patch.object(
            FeedbackService,
            "generate_issue_number",
            return_value="765432",
        ),
        patch.object(
            FeedbackService,
            "deliver_email",
        ),
    ):
        response = client.post(
            "/feedback",
            data={
                "csrf_token": csrf_token,
                "message": "Isolation feedback.",
                "page_url": "http://testserver/",
                "user_id": str(other_user.id),
            },
            follow_redirects=False,
        )

    assert response.status_code == 303

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action
            == AuditAction.FEEDBACK_SUBMITTED.value,
            AuditLog.metadata_json["issue_number"].as_string()
            == "765432",
        )
    )

    assert audit_log is not None
    assert audit_log.user_id == authenticated_user.id
    assert audit_log.user_id != other_user.id
