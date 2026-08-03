import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import AuditAction
from app.core.timezone import utc_now
from app.models.audit_log import AuditLog
from app.models.session import AuthSession
from app.services.user_service import (
    AnonymisedUserStatusError,
    UserPermissionError,
    UserSelfDeactivationError,
    UserService,
)
from tests.factories import (
    create_administrator,
    create_auth_session,
    create_expired_auth_session,
    create_user,
)


def test_administrator_deactivates_user(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    user = create_user(
        db,
    )

    result = UserService.set_active_status(
        db,
        acting_user=administrator,
        target_user=user,
        is_active=False,
        commit=False,
    )

    assert user.is_active is False
    assert result.user_id == user.id
    assert result.is_active is False


def test_deactivation_revokes_all_active_sessions(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

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

    result = UserService.set_active_status(
        db,
        acting_user=administrator,
        target_user=user,
        is_active=False,
        commit=False,
    )

    db.refresh(
        first_session,
    )

    db.refresh(
        second_session,
    )

    assert result.revoked_session_count == 2

    assert first_session.is_revoked is True
    assert second_session.is_revoked is True

    assert first_session.revoked_at is not None
    assert second_session.revoked_at is not None


def test_deactivation_does_not_count_expired_session(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    user = create_user(
        db,
    )

    create_auth_session(
        db,
        user=user,
    )

    expired_session, _, _ = (
        create_expired_auth_session(
            db,
            user=user,
        )
    )

    result = UserService.set_active_status(
        db,
        acting_user=administrator,
        target_user=user,
        is_active=False,
        commit=False,
    )

    assert result.revoked_session_count == 1

    db.refresh(
        expired_session,
    )

    assert expired_session.expires_at < utc_now()


def test_deactivation_preserves_administrator_session(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    administrator_session, _, _ = (
        create_auth_session(
            db,
            user=administrator,
        )
    )

    user = create_user(
        db,
    )

    create_auth_session(
        db,
        user=user,
    )

    UserService.set_active_status(
        db,
        acting_user=administrator,
        target_user=user,
        is_active=False,
        commit=False,
    )

    db.refresh(
        administrator_session,
    )

    assert administrator_session.is_revoked is False
    assert administrator_session.revoked_at is None


def test_deactivation_records_audit_log(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    user = create_user(
        db,
        username="audit-deactivation-user",
        display_name="Audit Deactivation User",
    )

    create_auth_session(
        db,
        user=user,
    )

    UserService.set_active_status(
        db,
        acting_user=administrator,
        target_user=user,
        is_active=False,
        ip_address="192.0.2.90",
        user_agent="pytest user deactivation",
        commit=False,
    )

    audit_log = db.scalar(
        select(
            AuditLog,
        ).where(
            AuditLog.action
            == AuditAction.USER_DEACTIVATED.value,
            AuditLog.entity_type
            == "user",
            AuditLog.entity_id
            == user.id,
        ),
    )

    assert audit_log is not None
    assert audit_log.user_id == administrator.id

    assert audit_log.metadata_json[
        "username"
    ] == user.username

    assert audit_log.metadata_json[
        "is_active"
    ] is False

    assert audit_log.metadata_json[
        "revoked_session_count"
    ] == 1

    assert audit_log.ip_address == "192.0.2.90"

    assert audit_log.user_agent == (
        "pytest user deactivation"
    )


def test_non_administrator_cannot_deactivate_user(
    db: Session,
) -> None:
    acting_user = create_user(
        db,
    )

    target_user = create_user(
        db,
    )

    with pytest.raises(
        UserPermissionError,
        match="Administrator access",
    ):
        UserService.set_active_status(
            db,
            acting_user=acting_user,
            target_user=target_user,
            is_active=False,
            commit=False,
        )

    assert target_user.is_active is True


def test_administrator_cannot_deactivate_self(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    with pytest.raises(
        UserSelfDeactivationError,
        match="own account",
    ):
        UserService.set_active_status(
            db,
            acting_user=administrator,
            target_user=administrator,
            is_active=False,
            commit=False,
        )

    assert administrator.is_active is True


def test_anonymised_user_cannot_be_deactivated(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    user = create_user(
        db,
        is_active=False,
        is_anonymised=True,
    )

    with pytest.raises(
        AnonymisedUserStatusError,
    ):
        UserService.set_active_status(
            db,
            acting_user=administrator,
            target_user=user,
            is_active=False,
            commit=False,
        )


def test_reactivation_does_not_restore_revoked_sessions(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    user = create_user(
        db,
    )

    auth_session, _, _ = create_auth_session(
        db,
        user=user,
    )

    UserService.set_active_status(
        db,
        acting_user=administrator,
        target_user=user,
        is_active=False,
        commit=False,
    )

    result = UserService.set_active_status(
        db,
        acting_user=administrator,
        target_user=user,
        is_active=True,
        commit=False,
    )

    db.refresh(
        auth_session,
    )

    assert result.is_active is True
    assert result.revoked_session_count == 0
    assert user.is_active is True
    assert auth_session.is_revoked is True


def test_idempotent_deactivation_does_not_create_second_audit_event(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    user = create_user(
        db,
        is_active=False,
    )

    result = UserService.set_active_status(
        db,
        acting_user=administrator,
        target_user=user,
        is_active=False,
        commit=False,
    )

    audit_logs = list(
        db.scalars(
            select(
                AuditLog,
            ).where(
                AuditLog.action
                == AuditAction.USER_DEACTIVATED.value,
                AuditLog.entity_type
                == "user",
                AuditLog.entity_id
                == user.id,
            ),
        ).all(),
    )

    assert result.is_active is False
    assert result.revoked_session_count == 0
    assert audit_logs == []