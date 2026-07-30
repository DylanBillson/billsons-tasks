from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import AuditAction, GlobalRole
from app.core.security import hash_token, verify_password
from app.core.timezone import utc_now
from app.models.audit_log import AuditLog
from app.models.session import AuthSession
from app.models.user import User
from tests.factories import (
    DEFAULT_TEST_PASSWORD,
    create_administrator,
    create_audit_log,
    create_auth_session,
    create_expired_auth_session,
    create_revoked_auth_session,
    create_user,
)


def test_create_user(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    assert user.id is not None
    assert user.username.startswith(
        "test-user-",
    )
    assert user.display_name.startswith(
        "Test User ",
    )
    assert user.global_role == GlobalRole.USER
    assert user.is_active is True
    assert user.is_anonymised is False
    assert user.can_authenticate is True
    assert verify_password(
        DEFAULT_TEST_PASSWORD,
        user.password_hash,
    )

    persisted_user = db.scalar(
        select(User).where(
            User.id == user.id,
        ),
    )

    assert persisted_user is user


def test_create_user_accepts_custom_values(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="custom-user",
        display_name="Custom User",
        password="Custom-Password-123!",
        is_active=False,
    )

    assert user.username == "custom-user"
    assert user.display_name == "Custom User"
    assert user.is_active is False
    assert user.can_authenticate is False
    assert verify_password(
        "Custom-Password-123!",
        user.password_hash,
    )


def test_create_anonymised_user_sets_anonymised_at(
    db: Session,
) -> None:
    user = create_user(
        db,
        is_anonymised=True,
    )

    assert user.is_anonymised is True
    assert user.anonymised_at is not None
    assert user.can_authenticate is False


def test_create_administrator(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    assert administrator.global_role == GlobalRole.ADMINISTRATOR
    assert administrator.is_administrator is True


def test_create_auth_session(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    auth_session, session_token, csrf_token = create_auth_session(
        db,
        user=user,
        remember_me=True,
    )

    assert auth_session.id is not None
    assert auth_session.user_id == user.id
    assert auth_session.user is user
    assert auth_session.token_hash == hash_token(
        session_token,
    )
    assert auth_session.csrf_token_hash == hash_token(
        csrf_token,
    )
    assert auth_session.remember_me is True
    assert auth_session.is_revoked is False
    assert auth_session.is_valid is True

    persisted_session = db.scalar(
        select(AuthSession).where(
            AuthSession.id == auth_session.id,
        ),
    )

    assert persisted_session is auth_session


def test_create_expired_auth_session(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    auth_session, _, _ = create_expired_auth_session(
        db,
        user=user,
    )

    assert auth_session.expires_at < utc_now()
    assert auth_session.is_expired is True
    assert auth_session.is_valid is False


def test_create_revoked_auth_session(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    auth_session, _, _ = create_revoked_auth_session(
        db,
        user=user,
    )

    assert auth_session.is_revoked is True
    assert auth_session.revoked_at is not None
    assert auth_session.is_valid is False


def test_create_auth_session_accepts_explicit_tokens(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    auth_session, session_token, csrf_token = create_auth_session(
        db,
        user=user,
        session_token="known-session-token",
        csrf_token="known-csrf-token",
        expires_at=utc_now() + timedelta(
            days=1,
        ),
    )

    assert session_token == "known-session-token"
    assert csrf_token == "known-csrf-token"
    assert auth_session.token_hash == hash_token(
        "known-session-token",
    )
    assert auth_session.csrf_token_hash == hash_token(
        "known-csrf-token",
    )


def test_create_audit_log_for_user(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    audit_log = create_audit_log(
        db,
        action=AuditAction.LOGIN,
        summary="Test user logged in.",
        user=user,
        entity_type="user",
        entity_id=user.id,
        metadata_json={
            "username": user.username,
        },
    )

    assert audit_log.id is not None
    assert audit_log.user_id == user.id
    assert audit_log.action == AuditAction.LOGIN
    assert audit_log.summary == "Test user logged in."
    assert audit_log.entity_type == "user"
    assert audit_log.entity_id == user.id
    assert audit_log.metadata_json == {
        "username": user.username,
    }

    persisted_log = db.scalar(
        select(AuditLog).where(
            AuditLog.id == audit_log.id,
        ),
    )

    assert persisted_log is audit_log


def test_create_audit_log_redacts_sensitive_metadata(
    db: Session,
) -> None:
    audit_log = create_audit_log(
        db,
        metadata_json={
            "password": "must-not-be-stored",
            "safe_value": "visible",
        },
    )

    assert audit_log.metadata_json == {
        "password": "[REDACTED]",
        "safe_value": "visible",
    }