from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import AuditAction
from app.models.audit_log import AuditLog
from app.services.feedback_service import (
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


def test_feedback_requires_authentication(
    client: TestClient,
) -> None:
    response = client.post(
        "/feedback",
        data={
            "csrf_token": "invalid",
            "message": "Unauthenticated feedback.",
            "page_url": "http://testserver/",
        },
        headers={
            "accept": "text/html",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert response.headers[
        "location"
    ].startswith(
        "/login?next_url=%2Ffeedback",
    )


def test_feedback_requires_csrf_token(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    _authenticate(
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
                "message": "Missing CSRF token.",
                "page_url": "http://testserver/",
            },
            follow_redirects=False,
        )

    assert response.status_code == 403
    deliver_mock.assert_not_called()


def test_feedback_rejects_invalid_csrf_token(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    _authenticate(
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
                "csrf_token": "incorrect-token",
                "message": "Invalid CSRF token.",
                "page_url": "http://testserver/",
            },
            follow_redirects=False,
        )

    assert response.status_code == 403
    deliver_mock.assert_not_called()


def test_inactive_user_session_cannot_submit_feedback(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
        is_active=True,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=user,
    )

    user.is_active = False
    db.add(
        user,
    )
    db.commit()

    with patch.object(
        FeedbackService,
        "deliver_email",
    ) as deliver_mock:
        response = client.post(
            "/feedback",
            data={
                "csrf_token": csrf_token,
                "message": "Inactive user feedback.",
                "page_url": "http://testserver/",
            },
            headers={
                "accept": "application/json",
            },
            follow_redirects=False,
        )

    assert response.status_code == 401
    deliver_mock.assert_not_called()


def test_anonymised_user_session_cannot_submit_feedback(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
        is_active=True,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=user,
    )

    user.is_active = False
    user.is_anonymised = True

    db.add(
        user,
    )
    db.commit()

    with patch.object(
        FeedbackService,
        "deliver_email",
    ) as deliver_mock:
        response = client.post(
            "/feedback",
            data={
                "csrf_token": csrf_token,
                "message": "Anonymised user feedback.",
                "page_url": "http://testserver/",
            },
            headers={
                "accept": "application/json",
            },
            follow_redirects=False,
        )

    assert response.status_code == 401
    deliver_mock.assert_not_called()


def test_failed_csrf_submission_creates_no_audit_entry(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.post(
        "/feedback",
        data={
            "csrf_token": "invalid-token",
            "message": "This must not be audited.",
            "page_url": "http://testserver/",
        },
        follow_redirects=False,
    )

    assert response.status_code == 403

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action
            == AuditAction.FEEDBACK_SUBMITTED.value,
            AuditLog.user_id == user.id,
        )
    )

    assert audit_log is None


def test_feedback_audit_actor_is_authenticated_user(
    client: TestClient,
    db: Session,
) -> None:
    first_user = create_user(
        db,
        display_name="First Feedback User",
    )

    second_user = create_user(
        db,
        display_name="Second Feedback User",
    )

    csrf_token = _authenticate(
        client,
        db,
        user=first_user,
    )

    with (
        patch.object(
            FeedbackService,
            "generate_issue_number",
            return_value="987654",
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
                "message": (
                    "The authenticated user must own "
                    "this audit event."
                ),
                "page_url": "http://testserver/",
            },
            follow_redirects=False,
        )

    assert response.status_code == 303

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action
            == AuditAction.FEEDBACK_SUBMITTED.value,
            AuditLog.metadata_json[
                "issue_number"
            ].as_string()
            == "987654",
        )
    )

    assert audit_log is not None
    assert audit_log.user_id == first_user.id
    assert audit_log.user_id != second_user.id