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



def test_phase65_feedback_ui_and_submission(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
        display_name="Phase 6.5 Feedback User",
    )
    csrf_token = _authenticate(
        client,
        db,
        user=user,
    )

    page = client.get("/")

    assert page.status_code == 200
    assert "data-feedback-open" in page.text
    assert "data-feedback-modal" in page.text
    assert 'action="http://testserver/feedback"' in page.text
    assert "Send a quick note about an issue, bug, suggestion," in page.text

    with (
        patch.object(
            FeedbackService,
            "generate_issue_number",
            return_value="654321",
        ),
        patch.object(
            FeedbackService,
            "deliver_email",
        ) as deliver_mock,
    ):
        response = client.post(
            "/feedback",
            data={
                "csrf_token": csrf_token,
                "message": "Phase 6.5 feedback acceptance test.",
                "page_url": "http://testserver/",
            },
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert "654321" in response.headers["location"]
    deliver_mock.assert_called_once()

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action
            == AuditAction.FEEDBACK_SUBMITTED.value,
            AuditLog.user_id == user.id,
        )
    )

    assert audit_log is not None
    assert audit_log.metadata_json["issue_number"] == "654321"
    assert "message" not in audit_log.metadata_json
    assert (
        "Phase 6.5 feedback acceptance test."
        not in audit_log.summary
    )


def test_phase65_feedback_is_not_available_without_authentication(
    client: TestClient,
) -> None:
    response = client.get("/login")

    assert response.status_code == 200
    assert "data-feedback-open" not in response.text
    assert "data-feedback-modal" not in response.text


def test_phase65_feedback_requires_csrf(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(db)
    _authenticate(client, db, user=user)

    with patch.object(
        FeedbackService,
        "deliver_email",
    ) as deliver_mock:
        response = client.post(
            "/feedback",
            data={
                "message": "Missing CSRF.",
                "page_url": "http://testserver/",
            },
            follow_redirects=False,
        )

    assert response.status_code == 403
    deliver_mock.assert_not_called()
