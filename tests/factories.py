"""
Reusable database factories for tests.

These helpers create real SQLAlchemy model instances in the test database.
They flush changes so generated primary keys are immediately available, but
they do not commit. Transaction ownership remains with the calling test and
the shared ``db`` fixture.
"""

from collections.abc import Mapping
from datetime import datetime, timedelta
from itertools import count
from typing import Any

from sqlalchemy.orm import Session

from app.core.constants import AuditAction, GlobalRole
from app.core.security import (
    generate_csrf_token,
    generate_session_token,
    hash_password,
    hash_token,
)
from app.core.timezone import utc_now
from app.models.audit_log import AuditLog
from app.models.session import AuthSession
from app.models.user import User
from app.services.audit_service import AuditService


DEFAULT_TEST_PASSWORD = "Correct-Horse-Battery-Staple-123!"

_user_counter = count(
    start=1,
)


def _next_user_number() -> int:
    """
    Return a process-local unique number for generated usernames.
    """
    return next(
        _user_counter,
    )


def create_user(
    db: Session,
    *,
    username: str | None = None,
    display_name: str | None = None,
    password: str = DEFAULT_TEST_PASSWORD,
    password_hash: str | None = None,
    global_role: str | GlobalRole = GlobalRole.USER,
    is_active: bool = True,
    is_anonymised: bool = False,
    anonymised_at: datetime | None = None,
) -> User:
    """
    Create and flush a User.

    ``password_hash`` may be supplied when a test needs a deliberately old,
    malformed or otherwise specialised hash. When omitted, ``password`` is
    securely hashed using the application's normal password helper.
    """
    user_number = _next_user_number()

    resolved_username = (
        username
        if username is not None
        else f"test-user-{user_number}"
    )
    resolved_display_name = (
        display_name
        if display_name is not None
        else f"Test User {user_number}"
    )
    resolved_global_role = (
        global_role.value
        if isinstance(
            global_role,
            GlobalRole,
        )
        else global_role
    )

    if is_anonymised and anonymised_at is None:
        anonymised_at = utc_now()

    user = User(
        username=resolved_username,
        display_name=resolved_display_name,
        password_hash=(
            password_hash
            if password_hash is not None
            else hash_password(
                password,
            )
        ),
        global_role=resolved_global_role,
        is_active=is_active,
        is_anonymised=is_anonymised,
        anonymised_at=anonymised_at,
    )

    db.add(
        user,
    )
    db.flush()
    db.refresh(
        user,
    )

    return user


def create_administrator(
    db: Session,
    *,
    username: str | None = None,
    display_name: str | None = None,
    password: str = DEFAULT_TEST_PASSWORD,
    password_hash: str | None = None,
    is_active: bool = True,
    is_anonymised: bool = False,
    anonymised_at: datetime | None = None,
) -> User:
    """
    Create and flush an administrator user.
    """
    return create_user(
        db,
        username=username,
        display_name=display_name,
        password=password,
        password_hash=password_hash,
        global_role=GlobalRole.ADMINISTRATOR,
        is_active=is_active,
        is_anonymised=is_anonymised,
        anonymised_at=anonymised_at,
    )


def create_auth_session(
    db: Session,
    *,
    user: User,
    session_token: str | None = None,
    csrf_token: str | None = None,
    expires_at: datetime | None = None,
    last_seen_at: datetime | None = None,
    remember_me: bool = False,
    is_revoked: bool = False,
    revoked_at: datetime | None = None,
    ip_address: str | None = "127.0.0.1",
    user_agent: str | None = "Billsons Tasks pytest",
) -> tuple[AuthSession, str, str]:
    """
    Create and flush an authentication session.

    Returns:

    ``(auth_session, raw_session_token, raw_csrf_token)``

    The model stores only token hashes, while tests commonly need the raw
    values when calling AuthService methods.
    """
    now = utc_now()

    resolved_session_token = (
        session_token
        if session_token is not None
        else generate_session_token()
    )
    resolved_csrf_token = (
        csrf_token
        if csrf_token is not None
        else generate_csrf_token()
    )

    if last_seen_at is None:
        last_seen_at = now

    if expires_at is None:
        expires_at = now + timedelta(
            hours=12,
        )

    if is_revoked and revoked_at is None:
        revoked_at = now

    auth_session = AuthSession(
        user_id=user.id,
        token_hash=hash_token(
            resolved_session_token,
        ),
        csrf_token_hash=hash_token(
            resolved_csrf_token,
        ),
        expires_at=expires_at,
        last_seen_at=last_seen_at,
        remember_me=remember_me,
        is_revoked=is_revoked,
        revoked_at=revoked_at,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    db.add(
        auth_session,
    )
    db.flush()
    db.refresh(
        auth_session,
    )

    return (
        auth_session,
        resolved_session_token,
        resolved_csrf_token,
    )


def create_expired_auth_session(
    db: Session,
    *,
    user: User,
    expired_at: datetime | None = None,
    session_token: str | None = None,
    csrf_token: str | None = None,
    remember_me: bool = False,
    ip_address: str | None = "127.0.0.1",
    user_agent: str | None = "Billsons Tasks pytest",
) -> tuple[AuthSession, str, str]:
    """
    Create an authentication session whose expiry is in the past.
    """
    if expired_at is None:
        expired_at = utc_now() - timedelta(
            minutes=1,
        )

    return create_auth_session(
        db,
        user=user,
        session_token=session_token,
        csrf_token=csrf_token,
        expires_at=expired_at,
        last_seen_at=expired_at - timedelta(
            minutes=5,
        ),
        remember_me=remember_me,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def create_revoked_auth_session(
    db: Session,
    *,
    user: User,
    revoked_at: datetime | None = None,
    session_token: str | None = None,
    csrf_token: str | None = None,
    expires_at: datetime | None = None,
    remember_me: bool = False,
    ip_address: str | None = "127.0.0.1",
    user_agent: str | None = "Billsons Tasks pytest",
) -> tuple[AuthSession, str, str]:
    """
    Create a revoked authentication session.
    """
    return create_auth_session(
        db,
        user=user,
        session_token=session_token,
        csrf_token=csrf_token,
        expires_at=expires_at,
        remember_me=remember_me,
        is_revoked=True,
        revoked_at=revoked_at,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def create_audit_log(
    db: Session,
    *,
    action: str | AuditAction = AuditAction.LOGIN,
    summary: str = "Test audit event.",
    user: User | None = None,
    user_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    metadata_json: Mapping[str, Any] | None = None,
    ip_address: str | None = "127.0.0.1",
    user_agent: str | None = "Billsons Tasks pytest",
) -> AuditLog:
    """
    Create and flush an audit log through AuditService.

    Using the service rather than directly constructing AuditLog keeps test
    records aligned with the application's normal normalisation, metadata
    sanitisation and repository behaviour.
    """
    audit_log = AuditService.record(
        db,
        action=action,
        summary=summary,
        user=user,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=(
            dict(
                metadata_json,
            )
            if metadata_json is not None
            else None
        ),
        ip_address=ip_address,
        user_agent=user_agent,
        commit=False,
    )

    db.flush()
    db.refresh(
        audit_log,
    )

    return audit_log