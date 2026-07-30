from datetime import timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import AuditAction
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    hash_token,
    verify_password,
    verify_token_hash,
)
from app.core.timezone import utc_now
from app.models.audit_log import AuditLog
from app.models.session import AuthSession
from app.schemas.auth import LoginRequest
from app.services.auth_service import (
    MAX_IP_ADDRESS_LENGTH,
    MAX_USER_AGENT_LENGTH,
    AuthService,
    InvalidCredentialsError,
    InvalidSessionError,
)
from tests.factories import (
    DEFAULT_TEST_PASSWORD,
    create_auth_session,
    create_expired_auth_session,
    create_revoked_auth_session,
    create_user,
)


def get_audit_logs(
    db: Session,
    *,
    action: AuditAction,
) -> list[AuditLog]:
    return list(
        db.scalars(
            select(AuditLog)
            .where(
                AuditLog.action == action.value,
            )
            .order_by(
                AuditLog.id,
            )
        ).all()
    )


def test_authenticate_creates_session_for_valid_credentials(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="valid-login-user",
        password=DEFAULT_TEST_PASSWORD,
    )

    result = AuthService.authenticate(
        db,
        login=LoginRequest(
            username="valid-login-user",
            password=DEFAULT_TEST_PASSWORD,
        ),
        ip_address="192.0.2.10",
        user_agent="Authentication test browser",
    )

    auth_session = db.get(
        AuthSession,
        result.session_id,
    )

    assert auth_session is not None
    assert result.user_id == user.id
    assert result.session_id == auth_session.id
    assert result.remember_me is False

    assert result.session_token
    assert result.csrf_token
    assert result.session_token != result.csrf_token

    assert auth_session.user_id == user.id
    assert auth_session.token_hash == hash_token(
        result.session_token,
    )
    assert auth_session.csrf_token_hash == hash_token(
        result.csrf_token,
    )
    assert auth_session.remember_me is False
    assert auth_session.is_revoked is False
    assert auth_session.revoked_at is None
    assert auth_session.ip_address == "192.0.2.10"
    assert auth_session.user_agent == (
        "Authentication test browser"
    )
    assert auth_session.expires_at == result.expires_at


def test_authenticate_uses_generated_session_and_csrf_tokens(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="generated-token-user",
        password=DEFAULT_TEST_PASSWORD,
    )

    session_token = "fixed-session-token"
    csrf_token = "fixed-csrf-token"

    with (
        patch(
            "app.services.auth_service.generate_session_token",
            return_value=session_token,
        ),
        patch(
            "app.services.auth_service.generate_csrf_token",
            return_value=csrf_token,
        ),
    ):
        result = AuthService.authenticate(
            db,
            login=LoginRequest(
                username=user.username,
                password=DEFAULT_TEST_PASSWORD,
            ),
        )

    auth_session = db.get(
        AuthSession,
        result.session_id,
    )

    assert auth_session is not None
    assert result.session_token == session_token
    assert result.csrf_token == csrf_token
    assert auth_session.token_hash == hash_token(
        session_token,
    )
    assert auth_session.csrf_token_hash == hash_token(
        csrf_token,
    )
    assert auth_session.token_hash != session_token
    assert auth_session.csrf_token_hash != csrf_token


def test_authenticate_normalises_username_through_login_schema(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="normalised-login",
        password=DEFAULT_TEST_PASSWORD,
    )

    result = AuthService.authenticate(
        db,
        login=LoginRequest(
            username="  NORMALISED-LOGIN  ",
            password=DEFAULT_TEST_PASSWORD,
        ),
    )

    assert result.user_id == user.id


def test_authenticate_creates_standard_session_expiry(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="standard-session-user",
        password=DEFAULT_TEST_PASSWORD,
    )
    now = utc_now()

    with patch(
        "app.services.auth_service.utc_now",
        return_value=now,
    ):
        result = AuthService.authenticate(
            db,
            login=LoginRequest(
                username=user.username,
                password=DEFAULT_TEST_PASSWORD,
                remember_me=False,
            ),
        )

    expected_expiry = now + timedelta(
        hours=settings.session_duration_hours,
    )

    assert result.remember_me is False
    assert result.expires_at == expected_expiry


def test_authenticate_creates_remember_me_session_expiry(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="remember-me-user",
        password=DEFAULT_TEST_PASSWORD,
    )
    now = utc_now()

    with patch(
        "app.services.auth_service.utc_now",
        return_value=now,
    ):
        result = AuthService.authenticate(
            db,
            login=LoginRequest(
                username=user.username,
                password=DEFAULT_TEST_PASSWORD,
                remember_me=True,
            ),
        )

    expected_expiry = now + timedelta(
        days=settings.remember_me_duration_days,
    )

    auth_session = db.get(
        AuthSession,
        result.session_id,
    )

    assert auth_session is not None
    assert result.remember_me is True
    assert auth_session.remember_me is True
    assert result.expires_at == expected_expiry


def test_authenticate_records_successful_login_audit_log(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="audited-login-user",
        display_name="Audited Login User",
        password=DEFAULT_TEST_PASSWORD,
    )

    result = AuthService.authenticate(
        db,
        login=LoginRequest(
            username=user.username,
            password=DEFAULT_TEST_PASSWORD,
            remember_me=True,
        ),
        ip_address="198.51.100.20",
        user_agent="Audit login test",
    )

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action == AuditAction.LOGIN.value,
            AuditLog.entity_type == "auth_session",
            AuditLog.entity_id == result.session_id,
        )
    )

    assert audit_log is not None
    assert audit_log.user_id == user.id
    assert audit_log.summary == (
        "Audited Login User logged in."
    )
    assert audit_log.metadata_json["username"] == (
        "audited-login-user"
    )
    assert audit_log.metadata_json["remember_me"] is True
    assert audit_log.metadata_json["expires_at"] == (
        result.expires_at.isoformat()
    )
    assert audit_log.ip_address == "198.51.100.20"
    assert audit_log.user_agent == "Audit login test"


def test_authenticate_normalises_ip_address_and_user_agent(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="normalised-client-user",
        password=DEFAULT_TEST_PASSWORD,
    )

    result = AuthService.authenticate(
        db,
        login=LoginRequest(
            username=user.username,
            password=DEFAULT_TEST_PASSWORD,
        ),
        ip_address="  203.0.113.50  ",
        user_agent="  Test user agent  ",
    )

    auth_session = db.get(
        AuthSession,
        result.session_id,
    )

    assert auth_session is not None
    assert auth_session.ip_address == "203.0.113.50"
    assert auth_session.user_agent == "Test user agent"


def test_authenticate_converts_blank_client_details_to_none(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="blank-client-details-user",
        password=DEFAULT_TEST_PASSWORD,
    )

    result = AuthService.authenticate(
        db,
        login=LoginRequest(
            username=user.username,
            password=DEFAULT_TEST_PASSWORD,
        ),
        ip_address="   ",
        user_agent="   ",
    )

    auth_session = db.get(
        AuthSession,
        result.session_id,
    )

    assert auth_session is not None
    assert auth_session.ip_address is None
    assert auth_session.user_agent is None


def test_authenticate_truncates_long_client_details(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="long-client-details-user",
        password=DEFAULT_TEST_PASSWORD,
    )

    long_ip_address = "1" * (
        MAX_IP_ADDRESS_LENGTH + 20
    )
    long_user_agent = "a" * (
        MAX_USER_AGENT_LENGTH + 100
    )

    result = AuthService.authenticate(
        db,
        login=LoginRequest(
            username=user.username,
            password=DEFAULT_TEST_PASSWORD,
        ),
        ip_address=long_ip_address,
        user_agent=long_user_agent,
    )

    auth_session = db.get(
        AuthSession,
        result.session_id,
    )

    assert auth_session is not None
    assert auth_session.ip_address == (
        long_ip_address[:MAX_IP_ADDRESS_LENGTH]
    )
    assert auth_session.user_agent == (
        long_user_agent[:MAX_USER_AGENT_LENGTH]
    )


def test_authenticate_rehashes_password_when_update_is_needed(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="password-rehash-user",
        password=DEFAULT_TEST_PASSWORD,
    )
    original_password_hash = user.password_hash

    with patch(
        "app.services.auth_service.password_hash_needs_update",
        return_value=True,
    ):
        AuthService.authenticate(
            db,
            login=LoginRequest(
                username=user.username,
                password=DEFAULT_TEST_PASSWORD,
            ),
        )

    db.refresh(user)

    assert user.password_hash != original_password_hash
    assert verify_password(
        DEFAULT_TEST_PASSWORD,
        user.password_hash,
    )


def test_authenticate_does_not_rehash_current_password_hash(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="current-password-hash-user",
        password=DEFAULT_TEST_PASSWORD,
    )
    original_password_hash = user.password_hash

    with (
        patch(
            "app.services.auth_service.password_hash_needs_update",
            return_value=False,
        ),
        patch(
            "app.services.auth_service.hash_password",
        ) as hash_password_mock,
    ):
        AuthService.authenticate(
            db,
            login=LoginRequest(
                username=user.username,
                password=DEFAULT_TEST_PASSWORD,
            ),
        )

    hash_password_mock.assert_not_called()

    db.refresh(user)

    assert user.password_hash == original_password_hash


def test_authenticate_rejects_unknown_username(
    db: Session,
) -> None:
    with pytest.raises(
        InvalidCredentialsError,
        match="Invalid username or password",
    ):
        AuthService.authenticate(
            db,
            login=LoginRequest(
                username="unknown-login-user",
                password=DEFAULT_TEST_PASSWORD,
            ),
        )


def test_authenticate_uses_dummy_hash_for_unknown_username(
    db: Session,
) -> None:
    with patch(
        "app.services.auth_service.verify_password",
        return_value=False,
    ) as verify_password_mock:
        with pytest.raises(InvalidCredentialsError):
            AuthService.authenticate(
                db,
                login=LoginRequest(
                    username="unknown-timing-user",
                    password="supplied-password",
                ),
            )

    verify_password_mock.assert_called_once_with(
        "supplied-password",
        DUMMY_PASSWORD_HASH,
    )


def test_authenticate_records_unknown_username_failure(
    db: Session,
) -> None:
    with pytest.raises(InvalidCredentialsError):
        AuthService.authenticate(
            db,
            login=LoginRequest(
                username="  UNKNOWN-AUDIT-USER  ",
                password=DEFAULT_TEST_PASSWORD,
            ),
            ip_address="  192.0.2.55  ",
            user_agent="  Failed login browser  ",
        )

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action
            == AuditAction.LOGIN_FAILED.value,
            AuditLog.entity_type == "authentication",
        )
    )

    assert audit_log is not None
    assert audit_log.user_id is None
    assert audit_log.entity_id is None
    assert audit_log.summary == (
        "A login attempt was rejected."
    )
    assert audit_log.metadata_json == {
        "username": "unknown-audit-user",
        "successful": False,
        "reason": "unknown_username",
    }
    assert audit_log.ip_address == "192.0.2.55"
    assert audit_log.user_agent == "Failed login browser"


def test_authenticate_rejects_invalid_password(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="invalid-password-user",
        password=DEFAULT_TEST_PASSWORD,
    )

    with pytest.raises(
        InvalidCredentialsError,
        match="Invalid username or password",
    ):
        AuthService.authenticate(
            db,
            login=LoginRequest(
                username=user.username,
                password="Incorrect-password-123!",
            ),
        )


def test_authenticate_records_invalid_password_failure(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="invalid-password-audit-user",
        password=DEFAULT_TEST_PASSWORD,
    )

    with pytest.raises(InvalidCredentialsError):
        AuthService.authenticate(
            db,
            login=LoginRequest(
                username=user.username,
                password="Incorrect-password-123!",
            ),
        )

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action
            == AuditAction.LOGIN_FAILED.value,
            AuditLog.entity_type == "user",
            AuditLog.entity_id == user.id,
        )
    )

    assert audit_log is not None
    assert audit_log.user_id == user.id
    assert audit_log.metadata_json == {
        "username": user.username,
        "successful": False,
        "reason": "invalid_password",
    }


@pytest.mark.parametrize(
    (
        "is_active",
        "is_anonymised",
    ),
    [
        (
            False,
            False,
        ),
        (
            True,
            True,
        ),
    ],
)
def test_authenticate_rejects_unavailable_account(
    db: Session,
    is_active: bool,
    is_anonymised: bool,
) -> None:
    user = create_user(
        db,
        password=DEFAULT_TEST_PASSWORD,
        is_active=is_active,
        is_anonymised=is_anonymised,
    )

    with pytest.raises(
        InvalidCredentialsError,
        match="Invalid username or password",
    ):
        AuthService.authenticate(
            db,
            login=LoginRequest(
                username=user.username,
                password=DEFAULT_TEST_PASSWORD,
            ),
        )

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action
            == AuditAction.LOGIN_FAILED.value,
            AuditLog.entity_type == "user",
            AuditLog.entity_id == user.id,
        )
    )

    assert audit_log is not None
    assert audit_log.metadata_json["reason"] == (
        "account_unavailable"
    )


def test_failed_authentication_does_not_create_session(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="no-session-on-failure",
        password=DEFAULT_TEST_PASSWORD,
    )

    session_count_before = db.scalar(
        select(func.count(AuthSession.id))
    )

    with pytest.raises(InvalidCredentialsError):
        AuthService.authenticate(
            db,
            login=LoginRequest(
                username=user.username,
                password="Incorrect-password-123!",
            ),
        )

    session_count_after = db.scalar(
        select(func.count(AuthSession.id))
    )

    assert session_count_after == session_count_before


def test_resolve_session_returns_none_for_missing_token(
    db: Session,
) -> None:
    assert AuthService.resolve_session(
        db,
        session_token=None,
    ) is None

    assert AuthService.resolve_session(
        db,
        session_token="",
    ) is None


def test_resolve_session_returns_none_for_unknown_token(
    db: Session,
) -> None:
    result = AuthService.resolve_session(
        db,
        session_token="unknown-session-token",
    )

    assert result is None


def test_resolve_session_returns_active_session(
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    auth_session, session_token, _ = create_auth_session(
        db,
        user=user,
    )

    result = AuthService.resolve_session(
        db,
        session_token=session_token,
        update_last_seen=False,
    )

    assert result is auth_session
    assert result.user is user


def test_resolve_session_returns_none_for_expired_session(
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    auth_session, session_token, _ = (
        create_expired_auth_session(
            db,
            user=user,
        )
    )

    result = AuthService.resolve_session(
        db,
        session_token=session_token,
    )

    assert result is None
    assert auth_session.is_revoked is False


def test_resolve_session_returns_none_for_revoked_session(
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    auth_session, session_token, _ = (
        create_revoked_auth_session(
            db,
            user=user,
        )
    )

    result = AuthService.resolve_session(
        db,
        session_token=session_token,
    )

    assert result is None
    assert auth_session.is_revoked is True


def test_resolve_session_revokes_session_for_inactive_user(
    db: Session,
) -> None:
    user = create_user(
        db,
        is_active=True,
    )
    auth_session, session_token, _ = create_auth_session(
        db,
        user=user,
    )

    user.is_active = False
    db.add(user)
    db.flush()

    result = AuthService.resolve_session(
        db,
        session_token=session_token,
    )

    db.refresh(auth_session)

    assert result is None
    assert auth_session.is_revoked is True
    assert auth_session.revoked_at is not None


def test_resolve_session_revokes_session_for_anonymised_user(
    db: Session,
) -> None:
    user = create_user(
        db,
        is_anonymised=False,
    )
    auth_session, session_token, _ = create_auth_session(
        db,
        user=user,
    )

    user.is_anonymised = True
    user.anonymised_at = utc_now()
    db.add(user)
    db.flush()

    result = AuthService.resolve_session(
        db,
        session_token=session_token,
    )

    db.refresh(auth_session)

    assert result is None
    assert auth_session.is_revoked is True


def test_resolve_session_updates_last_seen_when_due(
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    auth_session, session_token, _ = create_auth_session(
        db,
        user=user,
    )

    now = utc_now()
    original_last_seen = now - timedelta(
        minutes=(
            settings.session_last_seen_update_minutes
            + 1
        ),
    )

    auth_session.last_seen_at = original_last_seen
    db.add(auth_session)
    db.flush()

    with (
        patch(
            "app.services.auth_service.utc_now",
            return_value=now,
        ),
        patch(
            "app.repositories.session_repository.utc_now",
            return_value=now,
        ),
    ):
        result = AuthService.resolve_session(
            db,
            session_token=session_token,
            ip_address="  203.0.113.70  ",
            user_agent="  Updated session browser  ",
        )

    assert result is auth_session
    assert auth_session.last_seen_at == now
    assert auth_session.ip_address == "203.0.113.70"
    assert auth_session.user_agent == (
        "Updated session browser"
    )


def test_resolve_session_does_not_update_last_seen_before_interval(
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    auth_session, session_token, _ = create_auth_session(
        db,
        user=user,
    )

    now = utc_now()
    original_last_seen = now - timedelta(
        minutes=max(
            settings.session_last_seen_update_minutes - 1,
            0,
        ),
    )

    auth_session.last_seen_at = original_last_seen
    auth_session.ip_address = "192.0.2.80"
    auth_session.user_agent = "Original browser"
    db.add(auth_session)
    db.flush()

    with patch(
        "app.services.auth_service.utc_now",
        return_value=now,
    ):
        result = AuthService.resolve_session(
            db,
            session_token=session_token,
            ip_address="203.0.113.80",
            user_agent="Replacement browser",
        )

    assert result is auth_session
    assert auth_session.last_seen_at == original_last_seen
    assert auth_session.ip_address == "192.0.2.80"
    assert auth_session.user_agent == "Original browser"


def test_resolve_session_respects_update_last_seen_false(
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    auth_session, session_token, _ = create_auth_session(
        db,
        user=user,
    )

    old_last_seen = utc_now() - timedelta(
        days=1,
    )
    auth_session.last_seen_at = old_last_seen
    db.add(auth_session)
    db.flush()

    result = AuthService.resolve_session(
        db,
        session_token=session_token,
        update_last_seen=False,
        ip_address="203.0.113.90",
        user_agent="Should not be stored",
    )

    assert result is auth_session
    assert auth_session.last_seen_at == old_last_seen
    assert auth_session.ip_address != "203.0.113.90"
    assert auth_session.user_agent != (
        "Should not be stored"
    )


def test_require_session_returns_active_session(
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    auth_session, session_token, _ = create_auth_session(
        db,
        user=user,
    )

    result = AuthService.require_session(
        db,
        session_token=session_token,
        update_last_seen=False,
    )

    assert result is auth_session


@pytest.mark.parametrize(
    "session_token",
    [
        None,
        "",
        "invalid-session-token",
    ],
)
def test_require_session_rejects_invalid_session(
    db: Session,
    session_token: str | None,
) -> None:
    with pytest.raises(
        InvalidSessionError,
        match="Authentication is required",
    ):
        AuthService.require_session(
            db,
            session_token=session_token,
        )


def test_resolve_user_returns_session_user(
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    _, session_token, _ = create_auth_session(
        db,
        user=user,
    )

    result = AuthService.resolve_user(
        db,
        session_token=session_token,
        update_last_seen=False,
    )

    assert result is user


def test_resolve_user_returns_none_for_invalid_session(
    db: Session,
) -> None:
    result = AuthService.resolve_user(
        db,
        session_token="invalid-user-session",
    )

    assert result is None


def test_logout_revokes_active_session(
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    auth_session, session_token, _ = create_auth_session(
        db,
        user=user,
    )

    result = AuthService.logout(
        db,
        session_token=session_token,
    )

    db.refresh(auth_session)

    assert result is True
    assert auth_session.is_revoked is True
    assert auth_session.revoked_at is not None


def test_logout_records_audit_log(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="logout-audit-user",
        display_name="Logout Audit User",
    )
    auth_session, session_token, _ = create_auth_session(
        db,
        user=user,
    )

    result = AuthService.logout(
        db,
        session_token=session_token,
        ip_address="  198.51.100.100  ",
        user_agent="  Logout browser  ",
    )

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action == AuditAction.LOGOUT.value,
            AuditLog.entity_type == "auth_session",
            AuditLog.entity_id == auth_session.id,
        )
    )

    assert result is True
    assert audit_log is not None
    assert audit_log.user_id == user.id
    assert audit_log.summary == (
        "Logout Audit User logged out."
    )
    assert audit_log.metadata_json == {
        "username": "logout-audit-user",
    }
    assert audit_log.ip_address == "198.51.100.100"
    assert audit_log.user_agent == "Logout browser"


@pytest.mark.parametrize(
    "session_token",
    [
        None,
        "",
        "unknown-logout-token",
    ],
)
def test_logout_returns_false_for_missing_or_unknown_token(
    db: Session,
    session_token: str | None,
) -> None:
    result = AuthService.logout(
        db,
        session_token=session_token,
    )

    assert result is False


def test_logout_returns_false_for_already_revoked_session(
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    auth_session, session_token, _ = (
        create_revoked_auth_session(
            db,
            user=user,
        )
    )
    original_revoked_at = auth_session.revoked_at

    result = AuthService.logout(
        db,
        session_token=session_token,
    )

    assert result is False
    assert auth_session.revoked_at == original_revoked_at

    audit_logs = get_audit_logs(
        db,
        action=AuditAction.LOGOUT,
    )

    assert not any(
        audit_log.entity_id == auth_session.id
        for audit_log in audit_logs
    )


def test_logout_is_idempotent(
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    auth_session, session_token, _ = create_auth_session(
        db,
        user=user,
    )

    first_result = AuthService.logout(
        db,
        session_token=session_token,
    )
    second_result = AuthService.logout(
        db,
        session_token=session_token,
    )

    matching_logs = list(
        db.scalars(
            select(AuditLog).where(
                AuditLog.action == AuditAction.LOGOUT.value,
                AuditLog.entity_type == "auth_session",
                AuditLog.entity_id == auth_session.id,
            )
        ).all()
    )

    assert first_result is True
    assert second_result is False
    assert len(matching_logs) == 1


def test_revoke_all_sessions_for_user_revokes_all_sessions(
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    first_session, _, _ = create_auth_session(
        db,
        user=user,
    )
    second_session, _, _ = create_auth_session(
        db,
        user=user,
    )
    already_revoked, _, _ = create_revoked_auth_session(
        db,
        user=user,
    )

    revoked_count = AuthService.revoke_all_sessions_for_user(
        db,
        user=user,
    )

    db.refresh(first_session)
    db.refresh(second_session)
    db.refresh(already_revoked)

    assert revoked_count == 2
    assert first_session.is_revoked is True
    assert second_session.is_revoked is True
    assert already_revoked.is_revoked is True


def test_revoke_all_sessions_for_user_can_exclude_session(
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    retained_session, _, _ = create_auth_session(
        db,
        user=user,
    )
    revoked_session, _, _ = create_auth_session(
        db,
        user=user,
    )

    revoked_count = AuthService.revoke_all_sessions_for_user(
        db,
        user=user,
        exclude_session_id=retained_session.id,
    )

    db.refresh(retained_session)
    db.refresh(revoked_session)

    assert revoked_count == 1
    assert retained_session.is_revoked is False
    assert revoked_session.is_revoked is True


def test_revoke_all_sessions_for_user_does_not_affect_other_users(
    db: Session,
) -> None:
    target_user = create_user(
        db,
    )
    other_user = create_user(
        db,
    )

    target_session, _, _ = create_auth_session(
        db,
        user=target_user,
    )
    other_session, _, _ = create_auth_session(
        db,
        user=other_user,
    )

    revoked_count = AuthService.revoke_all_sessions_for_user(
        db,
        user=target_user,
    )

    db.refresh(target_session)
    db.refresh(other_session)

    assert revoked_count == 1
    assert target_session.is_revoked is True
    assert other_session.is_revoked is False


def test_revoke_all_sessions_for_user_commits_when_requested(
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    create_auth_session(
        db,
        user=user,
    )

    with patch.object(
        db,
        "commit",
        wraps=db.commit,
    ) as commit_mock:
        AuthService.revoke_all_sessions_for_user(
            db,
            user=user,
            commit=True,
        )

    commit_mock.assert_called_once_with()


def test_revoke_all_sessions_for_user_does_not_commit_by_default(
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    create_auth_session(
        db,
        user=user,
    )

    with patch.object(
        db,
        "commit",
        wraps=db.commit,
    ) as commit_mock:
        AuthService.revoke_all_sessions_for_user(
            db,
            user=user,
        )

    commit_mock.assert_not_called()


def test_rotate_csrf_token_replaces_stored_hash(
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    auth_session, _, original_csrf_token = (
        create_auth_session(
            db,
            user=user,
        )
    )
    original_csrf_hash = auth_session.csrf_token_hash

    replacement_token = AuthService.rotate_csrf_token(
        db,
        auth_session=auth_session,
    )

    db.refresh(auth_session)

    assert replacement_token
    assert replacement_token != original_csrf_token
    assert auth_session.csrf_token_hash != (
        original_csrf_hash
    )
    assert verify_token_hash(
        replacement_token,
        auth_session.csrf_token_hash,
    )
    assert not verify_token_hash(
        original_csrf_token,
        auth_session.csrf_token_hash,
    )


def test_rotate_csrf_token_uses_generated_token(
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    auth_session, _, _ = create_auth_session(
        db,
        user=user,
    )
    generated_token = "replacement-csrf-token"

    with patch(
        "app.services.auth_service.generate_csrf_token",
        return_value=generated_token,
    ):
        result = AuthService.rotate_csrf_token(
            db,
            auth_session=auth_session,
        )

    assert result == generated_token
    assert auth_session.csrf_token_hash == hash_token(
        generated_token,
    )


def test_rotate_csrf_token_does_not_commit_when_disabled(
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    auth_session, _, _ = create_auth_session(
        db,
        user=user,
    )

    with patch.object(
        db,
        "commit",
        wraps=db.commit,
    ) as commit_mock:
        token = AuthService.rotate_csrf_token(
            db,
            auth_session=auth_session,
            commit=False,
        )

    commit_mock.assert_not_called()

    assert verify_token_hash(
        token,
        auth_session.csrf_token_hash,
    )


def test_cleanup_expired_sessions_deletes_expired_sessions(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    expired_session, _, _ = create_expired_auth_session(
        db,
        user=user,
    )
    active_session, _, _ = create_auth_session(
        db,
        user=user,
    )

    expired_session_id = expired_session.id
    active_session_id = active_session.id

    deleted_count = AuthService.cleanup_expired_sessions(
        db,
    )

    assert deleted_count == 1
    assert db.get(
        AuthSession,
        expired_session_id,
    ) is None
    assert db.get(
        AuthSession,
        active_session_id,
    ) is not None


def test_cleanup_expired_sessions_uses_explicit_cutoff(
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    now = utc_now()

    old_expired_session, _, _ = create_auth_session(
        db,
        user=user,
    )
    recently_expired_session, _, _ = create_auth_session(
        db,
        user=user,
    )
    active_session, _, _ = create_auth_session(
        db,
        user=user,
    )

    old_expired_session.expires_at = now - timedelta(
        days=10,
    )
    recently_expired_session.expires_at = now - timedelta(
        days=1,
    )
    active_session.expires_at = now + timedelta(
        days=1,
    )
    db.flush()

    cutoff = now - timedelta(
        days=5,
    )

    deleted_count = AuthService.cleanup_expired_sessions(
        db,
        expired_before=cutoff,
    )

    assert deleted_count == 1
    assert db.get(
        AuthSession,
        old_expired_session.id,
    ) is None
    assert db.get(
        AuthSession,
        recently_expired_session.id,
    ) is not None
    assert db.get(
        AuthSession,
        active_session.id,
    ) is not None


def test_cleanup_expired_sessions_does_not_commit_when_disabled(
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    create_expired_auth_session(
        db,
        user=user,
    )

    with patch.object(
        db,
        "commit",
        wraps=db.commit,
    ) as commit_mock:
        deleted_count = (
            AuthService.cleanup_expired_sessions(
                db,
                commit=False,
            )
        )

    commit_mock.assert_not_called()
    assert deleted_count == 1


def test_calculate_expiry_uses_session_duration(
) -> None:
    now = utc_now()

    result = AuthService._calculate_expiry(
        now=now,
        remember_me=False,
    )

    assert result == now + timedelta(
        hours=settings.session_duration_hours,
    )


def test_calculate_expiry_uses_remember_me_duration(
) -> None:
    now = utc_now()

    result = AuthService._calculate_expiry(
        now=now,
        remember_me=True,
    )

    assert result == now + timedelta(
        days=settings.remember_me_duration_days,
    )


def test_should_update_last_seen_returns_true_when_due(
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    auth_session, _, _ = create_auth_session(
        db,
        user=user,
    )
    now = utc_now()

    auth_session.last_seen_at = now - timedelta(
        minutes=settings.session_last_seen_update_minutes,
    )

    with patch(
        "app.services.auth_service.utc_now",
        return_value=now,
    ):
        result = AuthService._should_update_last_seen(
            auth_session,
        )

    assert result is True


def test_should_update_last_seen_returns_false_before_due(
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    auth_session, _, _ = create_auth_session(
        db,
        user=user,
    )
    now = utc_now()

    auth_session.last_seen_at = now - timedelta(
        minutes=max(
            settings.session_last_seen_update_minutes - 1,
            0,
        ),
    )

    with patch(
        "app.services.auth_service.utc_now",
        return_value=now,
    ):
        result = AuthService._should_update_last_seen(
            auth_session,
        )

    assert result is False


@pytest.mark.parametrize(
    (
        "supplied_value",
        "expected_value",
    ),
    [
        (
            None,
            None,
        ),
        (
            "",
            None,
        ),
        (
            "   ",
            None,
        ),
        (
            "  192.0.2.1  ",
            "192.0.2.1",
        ),
        (
            "2001:db8::1",
            "2001:db8::1",
        ),
    ],
)
def test_normalise_ip_address(
    supplied_value: str | None,
    expected_value: str | None,
) -> None:
    result = AuthService._normalise_ip_address(
        supplied_value,
    )

    assert result == expected_value


def test_normalise_ip_address_truncates_long_value(
) -> None:
    supplied_value = "x" * (
        MAX_IP_ADDRESS_LENGTH + 20
    )

    result = AuthService._normalise_ip_address(
        supplied_value,
    )

    assert result == supplied_value[
        :MAX_IP_ADDRESS_LENGTH
    ]
    assert len(result) == MAX_IP_ADDRESS_LENGTH


@pytest.mark.parametrize(
    (
        "supplied_value",
        "expected_value",
    ),
    [
        (
            None,
            None,
        ),
        (
            "",
            None,
        ),
        (
            "   ",
            None,
        ),
        (
            "  Mozilla/5.0  ",
            "Mozilla/5.0",
        ),
    ],
)
def test_normalise_user_agent(
    supplied_value: str | None,
    expected_value: str | None,
) -> None:
    result = AuthService._normalise_user_agent(
        supplied_value,
    )

    assert result == expected_value


def test_normalise_user_agent_truncates_long_value(
) -> None:
    supplied_value = "x" * (
        MAX_USER_AGENT_LENGTH + 100
    )

    result = AuthService._normalise_user_agent(
        supplied_value,
    )

    assert result == supplied_value[
        :MAX_USER_AGENT_LENGTH
    ]
    assert len(result) == MAX_USER_AGENT_LENGTH


def test_record_failed_login_records_user_event(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="direct-failed-login-user",
    )

    AuthService._record_failed_login(
        db,
        username="  DIRECT-FAILED-LOGIN-USER  ",
        reason="test_reason",
        ip_address="192.0.2.200",
        user_agent="Direct helper test",
        user=user,
    )

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action
            == AuditAction.LOGIN_FAILED.value,
            AuditLog.entity_type == "user",
            AuditLog.entity_id == user.id,
        )
    )

    assert audit_log is not None
    assert audit_log.user_id == user.id
    assert audit_log.metadata_json == {
        "username": "direct-failed-login-user",
        "successful": False,
        "reason": "test_reason",
    }


def test_record_failed_login_records_system_event(
    db: Session,
) -> None:
    AuthService._record_failed_login(
        db,
        username="  SYSTEM-FAILED-LOGIN  ",
        reason="test_system_reason",
        ip_address=None,
        user_agent=None,
    )

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action
            == AuditAction.LOGIN_FAILED.value,
            AuditLog.entity_type == "authentication",
        )
    )

    assert audit_log is not None
    assert audit_log.user_id is None
    assert audit_log.entity_id is None
    assert audit_log.metadata_json == {
        "username": "system-failed-login",
        "successful": False,
        "reason": "test_system_reason",
    }