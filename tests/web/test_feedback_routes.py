from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import AuditAction
from app.models.audit_log import AuditLog
from app.services.feedback_service import (
    FeedbackDeliveryError,
    FeedbackService,
)
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

    return csrf_token


def test_authenticated_user_submits_feedback(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
        display_name="Feedback Route User",
    )

    csrf_token = _authenticate(
        client,
        db,
        user=user,
    )

    with (
        patch.object(
            FeedbackService,
            "generate_issue_number",
            return_value="123456",
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
                "message": (
                    "The task board needs more spacing."
                ),
                "page_url": (
                    "http://testserver/sections/42"
                ),
            },
            headers={
                "user-agent": "Feedback route test",
            },
            follow_redirects=False,
        )

    assert response.status_code == 303

    assert response.headers[
        "location"
    ].startswith(
        "/sections/42?",
    )

    assert (
        "Reference%3A+123456"
        in response.headers["location"]
    )

    deliver_mock.assert_called_once()

    delivered_message = (
        deliver_mock.call_args.args[0]
    )

    assert (
        "The task board needs more spacing."
        in delivered_message.get_content()
    )

    assert (
        "Page: http://testserver/sections/42"
        in delivered_message.get_content()
    )


def test_feedback_submission_creates_safe_audit_entry(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
        display_name="Audited Feedback User",
    )

    csrf_token = _authenticate(
        client,
        db,
        user=user,
    )

    feedback_message = (
        "This message must be emailed but not audited."
    )

    with (
        patch.object(
            FeedbackService,
            "generate_issue_number",
            return_value="654321",
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
                "message": feedback_message,
                "page_url": (
                    "http://testserver/tasks/19"
                ),
            },
            follow_redirects=False,
        )

    assert response.status_code == 303

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action
            == AuditAction.FEEDBACK_SUBMITTED.value,
            AuditLog.user_id == user.id,
            AuditLog.entity_type == "feedback",
        )
    )

    assert audit_log is not None
    assert audit_log.entity_id is None

    assert audit_log.metadata_json[
        "issue_number"
    ] == "654321"

    assert audit_log.metadata_json[
        "page_url"
    ] == "http://testserver/tasks/19"

    assert (
        audit_log.metadata_json["recipient"]
        == settings.feedback_email_to
    )

    assert "message" not in audit_log.metadata_json
    assert feedback_message not in audit_log.summary
    assert feedback_message not in str(
        audit_log.metadata_json,
    )


def test_blank_feedback_message_is_rejected(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=user,
    )

    with patch.object(
        FeedbackService,
        "deliver_email",
    ) as deliver_mock:
        response = client.post(
            "/feedback",
            data={
                "csrf_token": csrf_token,
                "message": "   ",
                "page_url": "http://testserver/",
            },
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "/?error=",
    )

    deliver_mock.assert_not_called()


def test_feedback_message_over_maximum_length_is_rejected(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=user,
    )

    with patch.object(
        FeedbackService,
        "deliver_email",
    ) as deliver_mock:
        response = client.post(
            "/feedback",
            data={
                "csrf_token": csrf_token,
                "message": "x" * 5_001,
                "page_url": "http://testserver/",
            },
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "/?error=",
    )

    deliver_mock.assert_not_called()


def test_feedback_delivery_failure_returns_error(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=user,
    )

    with patch.object(
        FeedbackService,
        "deliver_email",
        side_effect=FeedbackDeliveryError(
            "The feedback email could not be sent.",
        ),
    ):
        response = client.post(
            "/feedback",
            data={
                "csrf_token": csrf_token,
                "message": "Please investigate this issue.",
                "page_url": (
                    "http://testserver/my-tasks"
                ),
            },
            follow_redirects=False,
        )

    assert response.status_code == 303

    assert response.headers[
        "location"
    ].startswith(
        "/my-tasks?error=",
    )

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action
            == AuditAction.FEEDBACK_SUBMITTED.value,
            AuditLog.user_id == user.id,
        )
    )

    assert audit_log is None


def test_external_page_url_is_not_used_for_redirect(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=user,
    )

    with patch.object(
        FeedbackService,
        "deliver_email",
    ):
        response = client.post(
            "/feedback",
            data={
                "csrf_token": csrf_token,
                "message": "A test message.",
                "page_url": (
                    "https://malicious.example/steal"
                ),
            },
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "/?success=",
    )

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action
            == AuditAction.FEEDBACK_SUBMITTED.value,
            AuditLog.user_id == user.id,
        )
    )

    assert audit_log is not None

    assert audit_log.metadata_json[
        "page_url"
    ] == "http://testserver/"