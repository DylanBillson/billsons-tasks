"""
Web-route tests for administrator password resets.

These tests exercise the complete HTTP flow for:

    GET  /admin/users/{user_id}/reset-password
    POST /admin/users/{user_id}/reset-password

They verify:

- authentication and administrator access control
- reset-form rendering
- authenticated CSRF protection
- password validation
- successful password replacement
- target-user session revocation
- administrator-session preservation
- audit logging
- redirects and flash-message query parameters
- route helper functions
"""

from collections.abc import Generator
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import AuditAction
from app.core.security import verify_password
from app.db.session import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.session import AuthSession
from app.models.user import User
from app.services.user_service import (
    UserPermissionError,
    UserService,
)
from app.web.routes.admin_users import (
    _build_flash_messages,
    _get_authenticated_csrf_cookie_name,
    _get_form_value,
    _redirect_to_user_list,
)
from tests.factories import (
    DEFAULT_TEST_PASSWORD,
    create_administrator,
    create_auth_session,
    create_expired_auth_session,
    create_revoked_auth_session,
    create_user,
)


NEW_PASSWORD = "New-Secure-Password-987!"
ANOTHER_NEW_PASSWORD = "Another-Secure-Password-456!"


@pytest.fixture
def client(
    db: Session,
) -> Generator[TestClient, None, None]:
    """
    Provide a TestClient whose database dependency uses the isolated test
    session supplied by tests/conftest.py.
    """

    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(
            app,
            follow_redirects=False,
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def authenticate_client(
    client: TestClient,
    *,
    session_token: str,
    csrf_token: str,
) -> None:
    """
    Add the authenticated session and CSRF cookies expected by the app.
    """
    client.cookies.set(
        settings.session_cookie_name,
        session_token,
    )
    client.cookies.set(
        _get_authenticated_csrf_cookie_name(),
        csrf_token,
    )


def create_authenticated_administrator(
    db: Session,
    client: TestClient,
) -> tuple[User, AuthSession, str, str]:
    """
    Create an administrator and authenticate the supplied TestClient.
    """
    administrator = create_administrator(
        db,
    )

    auth_session, session_token, csrf_token = create_auth_session(
        db,
        user=administrator,
    )

    authenticate_client(
        client,
        session_token=session_token,
        csrf_token=csrf_token,
    )

    return (
        administrator,
        auth_session,
        session_token,
        csrf_token,
    )


def get_password_reset_audit_logs(
    db: Session,
    *,
    target_user_id: int | None = None,
) -> list[AuditLog]:
    """
    Return password-reset audit entries, optionally restricted to one target.
    """
    query = (
        select(AuditLog)
        .where(
            AuditLog.action == AuditAction.PASSWORD_RESET,
        )
        .order_by(
            AuditLog.id.asc(),
        )
    )

    if target_user_id is not None:
        query = query.where(
            AuditLog.entity_type == "user",
            AuditLog.entity_id == target_user_id,
        )

    return list(
        db.scalars(
            query,
        ).all(),
    )


def test_password_reset_page_renders_for_administrator(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, _ = create_authenticated_administrator(
        db,
        client,
    )

    target_user = create_user(
        db,
        username="target-user",
    )

    response = client.get(
        f"/admin/users/{target_user.id}/reset-password",
    )

    assert response.status_code == 200
    assert "Reset Password" in response.text
    assert "target-user" in response.text
    assert "New Password" in response.text
    assert "Confirm Password" in response.text


def test_password_reset_page_contains_correct_form_action(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, _ = create_authenticated_administrator(
        db,
        client,
    )

    target_user = create_user(
        db,
    )

    response = client.get(
        f"/admin/users/{target_user.id}/reset-password",
    )

    assert response.status_code == 200
    assert (
        f'action="/admin/users/{target_user.id}/reset-password"'
        in response.text
    )


def test_password_reset_page_uses_post_method(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, _ = create_authenticated_administrator(
        db,
        client,
    )

    target_user = create_user(
        db,
    )

    response = client.get(
        f"/admin/users/{target_user.id}/reset-password",
    )

    assert response.status_code == 200
    assert 'method="post"' in response.text


def test_password_reset_page_contains_correct_field_names(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, _ = create_authenticated_administrator(
        db,
        client,
    )

    target_user = create_user(
        db,
    )

    response = client.get(
        f"/admin/users/{target_user.id}/reset-password",
    )

    assert response.status_code == 200
    assert 'name="new_password"' in response.text
    assert 'name="confirm_password"' in response.text
    assert 'name="csrf_token"' in response.text


def test_password_reset_page_does_not_render_old_password(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, _ = create_authenticated_administrator(
        db,
        client,
    )

    target_user = create_user(
        db,
        password=DEFAULT_TEST_PASSWORD,
    )

    response = client.get(
        f"/admin/users/{target_user.id}/reset-password",
    )

    assert response.status_code == 200
    assert DEFAULT_TEST_PASSWORD not in response.text


def test_password_reset_page_renders_authenticated_csrf_token(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, csrf_token = create_authenticated_administrator(
        db,
        client,
    )

    target_user = create_user(
        db,
    )

    response = client.get(
        f"/admin/users/{target_user.id}/reset-password",
    )

    assert response.status_code == 200
    assert f'value="{csrf_token}"' in response.text


def test_password_reset_page_contains_cancel_link(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, _ = create_authenticated_administrator(
        db,
        client,
    )

    target_user = create_user(
        db,
    )

    response = client.get(
        f"/admin/users/{target_user.id}/reset-password",
    )

    assert response.status_code == 200
    assert 'href="/admin/users"' in response.text
    assert "Cancel" in response.text


def test_password_reset_page_requires_authentication(
    db: Session,
    client: TestClient,
) -> None:
    target_user = create_user(
        db,
    )

    response = client.get(
        f"/admin/users/{target_user.id}/reset-password",
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "/login",
    )


def test_password_reset_page_requires_administrator(
    db: Session,
    client: TestClient,
) -> None:
    standard_user = create_user(
        db,
    )
    _, session_token, csrf_token = create_auth_session(
        db,
        user=standard_user,
    )

    authenticate_client(
        client,
        session_token=session_token,
        csrf_token=csrf_token,
    )

    target_user = create_user(
        db,
    )

    response = client.get(
        f"/admin/users/{target_user.id}/reset-password",
    )

    assert response.status_code == 403


def test_password_reset_page_rejects_expired_session(
    db: Session,
    client: TestClient,
) -> None:
    administrator = create_administrator(
        db,
    )
    _, session_token, csrf_token = create_expired_auth_session(
        db,
        user=administrator,
    )

    authenticate_client(
        client,
        session_token=session_token,
        csrf_token=csrf_token,
    )

    target_user = create_user(
        db,
    )

    response = client.get(
        f"/admin/users/{target_user.id}/reset-password",
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "/login",
    )


def test_password_reset_page_rejects_revoked_session(
    db: Session,
    client: TestClient,
) -> None:
    administrator = create_administrator(
        db,
    )
    _, session_token, csrf_token = create_revoked_auth_session(
        db,
        user=administrator,
    )

    authenticate_client(
        client,
        session_token=session_token,
        csrf_token=csrf_token,
    )

    target_user = create_user(
        db,
    )

    response = client.get(
        f"/admin/users/{target_user.id}/reset-password",
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "/login",
    )


def test_password_reset_page_redirects_when_user_not_found(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, _ = create_authenticated_administrator(
        db,
        client,
    )

    response = client.get(
        "/admin/users/999999/reset-password",
    )

    assert response.status_code == 303

    parsed_location = urlparse(
        response.headers["location"],
    )
    query_parameters = parse_qs(
        parsed_location.query,
    )

    assert parsed_location.path == "/admin/users"
    assert query_parameters["error"] == [
        "The requested user could not be found.",
    ]


def test_password_reset_submit_requires_authentication(
    db: Session,
    client: TestClient,
) -> None:
    target_user = create_user(
        db,
    )
    original_hash = target_user.password_hash

    response = client.post(
        f"/admin/users/{target_user.id}/reset-password",
        data={
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
            "csrf_token": "not-authenticated",
        },
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "/login",
    )

    db.refresh(
        target_user,
    )
    assert target_user.password_hash == original_hash


def test_password_reset_submit_requires_administrator(
    db: Session,
    client: TestClient,
) -> None:
    standard_user = create_user(
        db,
    )
    _, session_token, csrf_token = create_auth_session(
        db,
        user=standard_user,
    )

    authenticate_client(
        client,
        session_token=session_token,
        csrf_token=csrf_token,
    )

    target_user = create_user(
        db,
    )
    original_hash = target_user.password_hash

    response = client.post(
        f"/admin/users/{target_user.id}/reset-password",
        data={
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 403

    db.refresh(
        target_user,
    )
    assert target_user.password_hash == original_hash


def test_password_reset_submit_requires_csrf_token(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, _ = create_authenticated_administrator(
        db,
        client,
    )

    target_user = create_user(
        db,
    )
    original_hash = target_user.password_hash

    response = client.post(
        f"/admin/users/{target_user.id}/reset-password",
        data={
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )

    assert response.status_code == 403

    db.refresh(
        target_user,
    )
    assert target_user.password_hash == original_hash


def test_password_reset_submit_rejects_invalid_csrf_token(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, _ = create_authenticated_administrator(
        db,
        client,
    )

    target_user = create_user(
        db,
    )
    original_hash = target_user.password_hash

    response = client.post(
        f"/admin/users/{target_user.id}/reset-password",
        data={
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
            "csrf_token": "incorrect-csrf-token",
        },
    )

    assert response.status_code == 403

    db.refresh(
        target_user,
    )
    assert target_user.password_hash == original_hash


def test_password_reset_submit_accepts_valid_header_csrf_token(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, csrf_token = create_authenticated_administrator(
        db,
        client,
    )

    target_user = create_user(
        db,
    )

    response = client.post(
        f"/admin/users/{target_user.id}/reset-password",
        data={
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
        headers={
            "x-csrf-token": csrf_token,
        },
    )

    assert response.status_code == 303

    db.refresh(
        target_user,
    )
    assert verify_password(
        NEW_PASSWORD,
        target_user.password_hash,
    )


def test_password_reset_submit_redirects_when_user_not_found(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, csrf_token = create_authenticated_administrator(
        db,
        client,
    )

    response = client.post(
        "/admin/users/999999/reset-password",
        data={
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 303

    parsed_location = urlparse(
        response.headers["location"],
    )
    query_parameters = parse_qs(
        parsed_location.query,
    )

    assert parsed_location.path == "/admin/users"
    assert query_parameters["error"] == [
        "The requested user could not be found.",
    ]


def test_password_reset_submit_returns_422_when_password_missing(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, csrf_token = create_authenticated_administrator(
        db,
        client,
    )

    target_user = create_user(
        db,
    )

    response = client.post(
        f"/admin/users/{target_user.id}/reset-password",
        data={
            "confirm_password": NEW_PASSWORD,
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 422
    assert "Reset Password" in response.text


def test_password_reset_submit_returns_422_when_confirmation_missing(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, csrf_token = create_authenticated_administrator(
        db,
        client,
    )

    target_user = create_user(
        db,
    )

    response = client.post(
        f"/admin/users/{target_user.id}/reset-password",
        data={
            "new_password": NEW_PASSWORD,
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 422
    assert "Reset Password" in response.text


def test_password_reset_submit_rejects_mismatched_passwords(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, csrf_token = create_authenticated_administrator(
        db,
        client,
    )

    target_user = create_user(
        db,
    )
    original_hash = target_user.password_hash

    response = client.post(
        f"/admin/users/{target_user.id}/reset-password",
        data={
            "new_password": NEW_PASSWORD,
            "confirm_password": ANOTHER_NEW_PASSWORD,
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 422
    assert "Passwords do not match." in response.text

    db.refresh(
        target_user,
    )
    assert target_user.password_hash == original_hash


def test_password_reset_submit_rejects_short_password(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, csrf_token = create_authenticated_administrator(
        db,
        client,
    )

    target_user = create_user(
        db,
    )
    original_hash = target_user.password_hash

    short_password = "x"

    response = client.post(
        f"/admin/users/{target_user.id}/reset-password",
        data={
            "new_password": short_password,
            "confirm_password": short_password,
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 422
    assert (
        f"Password must contain at least "
        f"{settings.password_min_length} characters."
        in response.text
    )

    db.refresh(
        target_user,
    )
    assert target_user.password_hash == original_hash


def test_password_reset_submit_rejects_password_over_72_utf8_bytes(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, csrf_token = create_authenticated_administrator(
        db,
        client,
    )

    target_user = create_user(
        db,
    )
    original_hash = target_user.password_hash

    oversized_password = "é" * 37

    assert len(
        oversized_password.encode("utf-8"),
    ) == 74

    response = client.post(
        f"/admin/users/{target_user.id}/reset-password",
        data={
            "new_password": oversized_password,
            "confirm_password": oversized_password,
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 422
    assert "Password cannot exceed 72 UTF-8 bytes." in response.text

    db.refresh(
        target_user,
    )
    assert target_user.password_hash == original_hash


def test_invalid_password_form_does_not_render_password_values(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, csrf_token = create_authenticated_administrator(
        db,
        client,
    )

    target_user = create_user(
        db,
    )

    submitted_password = "secret-value-that-must-not-be-rendered"

    response = client.post(
        f"/admin/users/{target_user.id}/reset-password",
        data={
            "new_password": submitted_password,
            "confirm_password": "different-password",
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 422
    assert submitted_password not in response.text
    assert "different-password" not in response.text


def test_invalid_password_form_preserves_submitted_csrf_token(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, csrf_token = create_authenticated_administrator(
        db,
        client,
    )

    target_user = create_user(
        db,
    )

    response = client.post(
        f"/admin/users/{target_user.id}/reset-password",
        data={
            "new_password": NEW_PASSWORD,
            "confirm_password": ANOTHER_NEW_PASSWORD,
            "csrf_token": f"  {csrf_token}  ",
        },
    )

    assert response.status_code == 422
    assert f'value="{csrf_token}"' in response.text


def test_invalid_password_does_not_create_audit_log(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, csrf_token = create_authenticated_administrator(
        db,
        client,
    )

    target_user = create_user(
        db,
    )

    response = client.post(
        f"/admin/users/{target_user.id}/reset-password",
        data={
            "new_password": NEW_PASSWORD,
            "confirm_password": ANOTHER_NEW_PASSWORD,
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 422
    assert get_password_reset_audit_logs(
        db,
        target_user_id=target_user.id,
    ) == []


def test_password_reset_submit_changes_password_hash(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, csrf_token = create_authenticated_administrator(
        db,
        client,
    )

    target_user = create_user(
        db,
        password=DEFAULT_TEST_PASSWORD,
    )
    original_hash = target_user.password_hash

    response = client.post(
        f"/admin/users/{target_user.id}/reset-password",
        data={
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 303

    db.refresh(
        target_user,
    )

    assert target_user.password_hash != original_hash
    assert verify_password(
        NEW_PASSWORD,
        target_user.password_hash,
    )
    assert not verify_password(
        DEFAULT_TEST_PASSWORD,
        target_user.password_hash,
    )


def test_password_reset_submit_redirects_to_user_list_with_success_message(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, csrf_token = create_authenticated_administrator(
        db,
        client,
    )

    target_user = create_user(
        db,
        username="reset-target",
    )

    response = client.post(
        f"/admin/users/{target_user.id}/reset-password",
        data={
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 303

    parsed_location = urlparse(
        response.headers["location"],
    )
    query_parameters = parse_qs(
        parsed_location.query,
    )

    assert parsed_location.path == "/admin/users"
    assert query_parameters["success"] == [
        "The password for reset-target was reset.",
    ]


def test_password_reset_revokes_all_target_user_sessions(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, administrator_csrf_token = (
        create_authenticated_administrator(
            db,
            client,
        )
    )

    target_user = create_user(
        db,
    )

    first_session, _, _ = create_auth_session(
        db,
        user=target_user,
    )
    second_session, _, _ = create_auth_session(
        db,
        user=target_user,
        remember_me=True,
    )

    response = client.post(
        f"/admin/users/{target_user.id}/reset-password",
        data={
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
            "csrf_token": administrator_csrf_token,
        },
    )

    assert response.status_code == 303

    db.refresh(
        first_session,
    )
    db.refresh(
        second_session,
    )

    assert first_session.is_revoked is True
    assert first_session.revoked_at is not None
    assert second_session.is_revoked is True
    assert second_session.revoked_at is not None


def test_password_reset_does_not_change_already_revoked_session_timestamp(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, administrator_csrf_token = (
        create_authenticated_administrator(
            db,
            client,
        )
    )

    target_user = create_user(
        db,
    )

    revoked_session, _, _ = create_revoked_auth_session(
        db,
        user=target_user,
    )
    original_revoked_at = revoked_session.revoked_at

    response = client.post(
        f"/admin/users/{target_user.id}/reset-password",
        data={
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
            "csrf_token": administrator_csrf_token,
        },
    )

    assert response.status_code == 303

    db.refresh(
        revoked_session,
    )

    assert revoked_session.is_revoked is True
    assert revoked_session.revoked_at == original_revoked_at


def test_password_reset_does_not_revoke_administrator_session(
    db: Session,
    client: TestClient,
) -> None:
    _, administrator_session, _, csrf_token = (
        create_authenticated_administrator(
            db,
            client,
        )
    )

    target_user = create_user(
        db,
    )

    response = client.post(
        f"/admin/users/{target_user.id}/reset-password",
        data={
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 303

    db.refresh(
        administrator_session,
    )

    assert administrator_session.is_revoked is False
    assert administrator_session.revoked_at is None
    assert administrator_session.is_valid is True


def test_administrator_can_reset_own_password(
    db: Session,
    client: TestClient,
) -> None:
    administrator, administrator_session, _, csrf_token = (
        create_authenticated_administrator(
            db,
            client,
        )
    )
    original_hash = administrator.password_hash

    response = client.post(
        f"/admin/users/{administrator.id}/reset-password",
        data={
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 303

    db.refresh(
        administrator,
    )
    db.refresh(
        administrator_session,
    )

    assert administrator.password_hash != original_hash
    assert verify_password(
        NEW_PASSWORD,
        administrator.password_hash,
    )

    # Resetting the administrator's own password intentionally revokes their
    # existing authenticated session.
    assert administrator_session.is_revoked is True
    assert administrator_session.revoked_at is not None


def test_password_reset_creates_audit_log(
    db: Session,
    client: TestClient,
) -> None:
    administrator, _, _, csrf_token = (
        create_authenticated_administrator(
            db,
            client,
        )
    )

    target_user = create_user(
        db,
        username="audit-target",
        display_name="Audit Target",
    )

    response = client.post(
        f"/admin/users/{target_user.id}/reset-password",
        data={
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 303

    audit_logs = get_password_reset_audit_logs(
        db,
        target_user_id=target_user.id,
    )

    assert len(audit_logs) == 1

    audit_log = audit_logs[0]

    assert audit_log.user_id == administrator.id
    assert audit_log.action == AuditAction.PASSWORD_RESET
    assert audit_log.entity_type == "user"
    assert audit_log.entity_id == target_user.id
    assert audit_log.summary == (
        f"{administrator.display_name} reset the password for "
        f"{target_user.display_name}."
    )


def test_password_reset_audit_log_contains_expected_metadata(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, csrf_token = create_authenticated_administrator(
        db,
        client,
    )

    target_user = create_user(
        db,
        username="metadata-target",
    )

    create_auth_session(
        db,
        user=target_user,
    )
    create_auth_session(
        db,
        user=target_user,
    )

    response = client.post(
        f"/admin/users/{target_user.id}/reset-password",
        data={
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 303

    audit_logs = get_password_reset_audit_logs(
        db,
        target_user_id=target_user.id,
    )

    assert len(audit_logs) == 1

    metadata = audit_logs[0].metadata_json

    assert metadata["username"] == "metadata-target"
    assert metadata["revoked_session_count"] == 2
    assert isinstance(
        metadata["password_reset_at"],
        str,
    )
    assert metadata["password_reset_at"]


def test_password_reset_audit_log_does_not_store_password(
    db: Session,
    client: TestClient,
) -> None:
    _, _, _, csrf_token = create_authenticated_administrator(
        db,
        client,
    )

    target_user = create_user(
        db,
    )

    response = client.post(
        f"/admin/users/{target_user.id}/reset-password",
        data={
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 303

    audit_logs = get_password_reset_audit_logs(
        db,
        target_user_id=target_user.id,
    )

    assert len(audit_logs) == 1

    audit_log = audit_logs[0]

    assert NEW_PASSWORD not in audit_log.summary
    assert NEW_PASSWORD not in str(
        audit_log.metadata_json,
    )


def test_password_reset_permission_error_redirects_to_user_list(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, _, csrf_token = create_authenticated_administrator(
        db,
        client,
    )

    target_user = create_user(
        db,
    )

    def deny_password_reset(
        *args: object,
        **kwargs: object,
    ) -> None:
        raise UserPermissionError(
            "Password reset denied.",
        )

    monkeypatch.setattr(
        UserService,
        "reset_password_by_user_id",
        deny_password_reset,
    )

    response = client.post(
        f"/admin/users/{target_user.id}/reset-password",
        data={
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 303

    parsed_location = urlparse(
        response.headers["location"],
    )
    query_parameters = parse_qs(
        parsed_location.query,
    )

    assert parsed_location.path == "/admin/users"
    assert query_parameters["error"] == [
        "You do not have permission to reset this password.",
    ]


def test_redirect_to_user_list_without_message() -> None:
    response = _redirect_to_user_list()

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/users"


def test_redirect_to_user_list_with_success_message() -> None:
    response = _redirect_to_user_list(
        success="Password reset.",
    )

    parsed_location = urlparse(
        response.headers["location"],
    )
    query_parameters = parse_qs(
        parsed_location.query,
    )

    assert response.status_code == 303
    assert parsed_location.path == "/admin/users"
    assert query_parameters == {
        "success": [
            "Password reset.",
        ],
    }


def test_redirect_to_user_list_with_error_message() -> None:
    response = _redirect_to_user_list(
        error="Unable to reset password.",
    )

    parsed_location = urlparse(
        response.headers["location"],
    )
    query_parameters = parse_qs(
        parsed_location.query,
    )

    assert response.status_code == 303
    assert parsed_location.path == "/admin/users"
    assert query_parameters == {
        "error": [
            "Unable to reset password.",
        ],
    }


def test_redirect_to_user_list_with_success_and_error() -> None:
    response = _redirect_to_user_list(
        success="Password reset.",
        error="Secondary warning.",
    )

    parsed_location = urlparse(
        response.headers["location"],
    )
    query_parameters = parse_qs(
        parsed_location.query,
    )

    assert response.status_code == 303
    assert parsed_location.path == "/admin/users"
    assert query_parameters == {
        "success": [
            "Password reset.",
        ],
        "error": [
            "Secondary warning.",
        ],
    }


def test_build_flash_messages_returns_success_message() -> None:
    messages = _build_flash_messages(
        success="Password reset.",
        error=None,
    )

    assert messages == [
        {
            "category": "success",
            "title": "Success",
            "message": "Password reset.",
        },
    ]


def test_build_flash_messages_returns_error_message() -> None:
    messages = _build_flash_messages(
        success=None,
        error="Password reset failed.",
    )

    assert messages == [
        {
            "category": "error",
            "title": "Unable to complete request",
            "message": "Password reset failed.",
        },
    ]


def test_build_flash_messages_returns_both_messages() -> None:
    messages = _build_flash_messages(
        success="Password reset.",
        error="Secondary warning.",
    )

    assert messages == [
        {
            "category": "success",
            "title": "Success",
            "message": "Password reset.",
        },
        {
            "category": "error",
            "title": "Unable to complete request",
            "message": "Secondary warning.",
        },
    ]


def test_build_flash_messages_returns_empty_list() -> None:
    messages = _build_flash_messages(
        success=None,
        error=None,
    )

    assert messages == []


@pytest.mark.parametrize(
    (
        "form_data",
        "field_name",
        "expected",
    ),
    [
        (
            {
                "csrf_token": "token",
            },
            "csrf_token",
            "token",
        ),
        (
            {
                "csrf_token": "  token  ",
            },
            "csrf_token",
            "token",
        ),
        (
            {
                "csrf_token": "",
            },
            "csrf_token",
            None,
        ),
        (
            {
                "csrf_token": "   ",
            },
            "csrf_token",
            None,
        ),
        (
            {},
            "csrf_token",
            None,
        ),
        (
            {
                "number": 123,
            },
            "number",
            "123",
        ),
    ],
)
def test_get_form_value(
    form_data: object,
    field_name: str,
    expected: str | None,
) -> None:
    assert _get_form_value(
        form_data,
        field_name,
    ) == expected


def test_get_form_value_returns_none_without_getter() -> None:
    assert _get_form_value(
        object(),
        "csrf_token",
    ) is None


def test_authenticated_csrf_cookie_name_uses_session_cookie_name() -> None:
    assert _get_authenticated_csrf_cookie_name() == (
        f"{settings.session_cookie_name}_csrf"
    )