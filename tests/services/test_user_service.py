from datetime import timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import AuditAction, GlobalRole
from app.core.security import verify_password
from app.core.timezone import utc_now
from app.models.audit_log import AuditLog
from app.models.session import AuthSession
from app.schemas.auth import PasswordResetRequest
from app.schemas.user import (
    UserCreateRequest,
    UserUpdateRequest,
)
from app.services.user_service import (
    AnonymisedUserProfileError,
    UserNotFoundError,
    UserPermissionError,
    UserSelfRoleChangeError,
    UsernameAlreadyExistsError,
    UserService,
    UserServiceError,
)
from tests.factories import (
    DEFAULT_TEST_PASSWORD,
    create_administrator,
    create_auth_session,
    create_revoked_auth_session,
    create_user,
)


def test_get_user_returns_existing_user(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    result = UserService.get_user(
        db,
        user_id=user.id,
    )

    assert result is user


def test_get_user_returns_none_for_missing_user(
    db: Session,
) -> None:
    result = UserService.get_user(
        db,
        user_id=999_999,
    )

    assert result is None


def test_require_user_returns_existing_user(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    result = UserService.require_user(
        db,
        user_id=user.id,
    )

    assert result is user


def test_require_user_raises_for_missing_user(
    db: Session,
) -> None:
    with pytest.raises(
        UserNotFoundError,
        match="User not found",
    ):
        UserService.require_user(
            db,
            user_id=999_999,
        )


def test_get_by_username_is_case_insensitive(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="example-user",
    )

    result = UserService.get_by_username(
        db,
        username="  EXAMPLE-USER  ",
    )

    assert result is user


def test_get_by_username_returns_none_for_missing_user(
    db: Session,
) -> None:
    result = UserService.get_by_username(
        db,
        username="missing-user",
    )

    assert result is None


def test_list_users_returns_all_users_in_display_name_order(
    db: Session,
) -> None:
    charlie = create_user(
        db,
        username="charlie",
        display_name="Charlie User",
    )
    alice = create_user(
        db,
        username="alice",
        display_name="Alice User",
    )
    bob = create_user(
        db,
        username="bob",
        display_name="Bob User",
        is_active=False,
    )

    result = UserService.list_users(
        db,
    )

    relevant_users = [
        user
        for user in result
        if user.id in {
            alice.id,
            bob.id,
            charlie.id,
        }
    ]

    assert relevant_users == [
        alice,
        bob,
        charlie,
    ]


def test_list_users_can_exclude_inactive_users(
    db: Session,
) -> None:
    active_user = create_user(
        db,
        is_active=True,
    )
    inactive_user = create_user(
        db,
        is_active=False,
    )

    result = UserService.list_users(
        db,
        include_inactive=False,
    )

    result_ids = {
        user.id
        for user in result
    }

    assert active_user.id in result_ids
    assert inactive_user.id not in result_ids


def test_list_users_can_exclude_anonymised_users(
    db: Session,
) -> None:
    normal_user = create_user(
        db,
    )
    anonymised_user = create_user(
        db,
        is_anonymised=True,
    )

    result = UserService.list_users(
        db,
        include_anonymised=False,
    )

    result_ids = {
        user.id
        for user in result
    }

    assert normal_user.id in result_ids
    assert anonymised_user.id not in result_ids


def test_reset_password_updates_password_and_revokes_sessions(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )
    target_user = create_user(
        db,
        password=DEFAULT_TEST_PASSWORD,
    )

    first_session, _, _ = create_auth_session(
        db,
        user=target_user,
    )
    second_session, _, _ = create_auth_session(
        db,
        user=target_user,
    )
    already_revoked_session, _, _ = create_revoked_auth_session(
        db,
        user=target_user,
    )

    old_password_hash = target_user.password_hash
    new_password = "New-Secure-Password-456!"

    result = UserService.reset_password(
        db,
        acting_user=administrator,
        target_user=target_user,
        password_reset=PasswordResetRequest(
            new_password=new_password,
            confirm_password=new_password,
        ),
        ip_address="192.0.2.10",
        user_agent="Test browser",
    )

    db.refresh(target_user)
    db.refresh(first_session)
    db.refresh(second_session)
    db.refresh(already_revoked_session)

    assert target_user.password_hash != old_password_hash
    assert verify_password(
        new_password,
        target_user.password_hash,
    )
    assert not verify_password(
        DEFAULT_TEST_PASSWORD,
        target_user.password_hash,
    )

    assert first_session.is_revoked is True
    assert first_session.revoked_at is not None

    assert second_session.is_revoked is True
    assert second_session.revoked_at is not None

    assert already_revoked_session.is_revoked is True

    assert result.user_id == target_user.id
    assert result.revoked_session_count == 2
    assert result.password_reset_at.tzinfo is not None


def test_reset_password_creates_audit_log(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        display_name="Admin User",
    )
    target_user = create_user(
        db,
        username="password-target",
        display_name="Password Target",
    )

    new_password = "Replacement-Password-789!"

    result = UserService.reset_password(
        db,
        acting_user=administrator,
        target_user=target_user,
        password_reset=PasswordResetRequest(
            new_password=new_password,
            confirm_password=new_password,
        ),
        ip_address="198.51.100.20",
        user_agent="User service test",
    )

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action
            == AuditAction.PASSWORD_RESET.value,
            AuditLog.entity_type == "user",
            AuditLog.entity_id == target_user.id,
        )
    )

    assert audit_log is not None
    assert audit_log.user_id == administrator.id
    assert audit_log.summary == (
        "Admin User reset the password for Password Target."
    )
    assert audit_log.ip_address == "198.51.100.20"
    assert audit_log.user_agent == "User service test"
    assert audit_log.metadata_json["username"] == "password-target"
    assert audit_log.metadata_json["revoked_session_count"] == 0
    assert (
        audit_log.metadata_json["password_reset_at"]
        == result.password_reset_at.isoformat()
    )


def test_reset_password_rejects_non_administrator(
    db: Session,
) -> None:
    acting_user = create_user(
        db,
    )
    target_user = create_user(
        db,
    )

    original_password_hash = target_user.password_hash
    new_password = "New-Secure-Password-456!"

    with pytest.raises(
        UserPermissionError,
        match="Administrator access is required",
    ):
        UserService.reset_password(
            db,
            acting_user=acting_user,
            target_user=target_user,
            password_reset=PasswordResetRequest(
                new_password=new_password,
                confirm_password=new_password,
            ),
        )

    assert target_user.password_hash == original_password_hash


def test_reset_password_rejects_inactive_administrator(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        is_active=False,
    )
    target_user = create_user(
        db,
    )

    new_password = "New-Secure-Password-456!"

    with pytest.raises(
        UserPermissionError,
        match="administrator account is not available",
    ):
        UserService.reset_password(
            db,
            acting_user=administrator,
            target_user=target_user,
            password_reset=PasswordResetRequest(
                new_password=new_password,
                confirm_password=new_password,
            ),
        )


def test_reset_password_rejects_anonymised_administrator(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        is_anonymised=True,
    )
    target_user = create_user(
        db,
    )

    new_password = "New-Secure-Password-456!"

    with pytest.raises(
        UserPermissionError,
        match="administrator account is not available",
    ):
        UserService.reset_password(
            db,
            acting_user=administrator,
            target_user=target_user,
            password_reset=PasswordResetRequest(
                new_password=new_password,
                confirm_password=new_password,
            ),
        )


def test_reset_password_rejects_anonymised_target(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )
    target_user = create_user(
        db,
        is_anonymised=True,
    )

    original_password_hash = target_user.password_hash
    new_password = "New-Secure-Password-456!"

    with pytest.raises(
        UserServiceError,
        match="anonymised user cannot be reset",
    ):
        UserService.reset_password(
            db,
            acting_user=administrator,
            target_user=target_user,
            password_reset=PasswordResetRequest(
                new_password=new_password,
                confirm_password=new_password,
            ),
        )

    assert target_user.password_hash == original_password_hash


def test_reset_password_rejects_mismatched_confirmation(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )
    target_user = create_user(
        db,
    )

    original_password_hash = target_user.password_hash

    with pytest.raises(ValueError):
        UserService.reset_password(
            db,
            acting_user=administrator,
            target_user=target_user,
            password_reset=PasswordResetRequest(
                new_password="New-Secure-Password-456!",
                confirm_password="Different-Password-789!",
            ),
        )

    assert target_user.password_hash == original_password_hash


def test_reset_password_does_not_commit_when_commit_is_false(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )
    target_user = create_user(
        db,
    )

    new_password = "New-Secure-Password-456!"

    with patch.object(
        db,
        "commit",
        wraps=db.commit,
    ) as commit_mock:
        result = UserService.reset_password(
            db,
            acting_user=administrator,
            target_user=target_user,
            password_reset=PasswordResetRequest(
                new_password=new_password,
                confirm_password=new_password,
            ),
            commit=False,
        )

    commit_mock.assert_not_called()

    assert result.user_id == target_user.id
    assert verify_password(
        new_password,
        target_user.password_hash,
    )


def test_reset_password_by_user_id_resets_password(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )
    target_user = create_user(
        db,
    )

    new_password = "Password-By-User-ID-456!"

    result = UserService.reset_password_by_user_id(
        db,
        actor=administrator,
        user_id=target_user.id,
        new_password=new_password,
    )

    db.refresh(target_user)

    assert result.user_id == target_user.id
    assert verify_password(
        new_password,
        target_user.password_hash,
    )


def test_reset_password_by_user_id_raises_for_missing_user(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    new_password = "Password-By-User-ID-456!"

    with pytest.raises(
        UserNotFoundError,
        match="User not found",
    ):
        UserService.reset_password_by_user_id(
            db,
            actor=administrator,
            user_id=999_999,
            new_password=new_password,
        )


def test_set_active_status_deactivates_user_and_revokes_sessions(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )
    target_user = create_user(
        db,
        is_active=True,
    )

    first_session, _, _ = create_auth_session(
        db,
        user=target_user,
    )
    second_session, _, _ = create_auth_session(
        db,
        user=target_user,
    )

    result = UserService.set_active_status(
        db,
        acting_user=administrator,
        target_user=target_user,
        is_active=False,
        ip_address="203.0.113.30",
        user_agent="Deactivation test",
    )

    db.refresh(target_user)
    db.refresh(first_session)
    db.refresh(second_session)

    assert result.user_id == target_user.id
    assert result.is_active is False
    assert result.revoked_session_count == 2

    assert target_user.is_active is False

    assert first_session.is_revoked is True
    assert second_session.is_revoked is True
    assert first_session.revoked_at is not None
    assert second_session.revoked_at is not None

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action
            == AuditAction.USER_DEACTIVATED.value,
            AuditLog.entity_type == "user",
            AuditLog.entity_id == target_user.id,
        )
    )

    assert audit_log is not None
    assert audit_log.user_id == administrator.id
    assert audit_log.metadata_json["is_active"] is False
    assert audit_log.metadata_json["revoked_session_count"] == 2
    assert audit_log.ip_address == "203.0.113.30"
    assert audit_log.user_agent == "Deactivation test"


def test_set_active_status_reactivates_user(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )
    target_user = create_user(
        db,
        is_active=False,
    )

    result = UserService.set_active_status(
        db,
        acting_user=administrator,
        target_user=target_user,
        is_active=True,
    )

    db.refresh(
        target_user,
    )

    assert result.user_id == target_user.id
    assert result.is_active is True
    assert result.revoked_session_count == 0

    assert target_user.is_active is True

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action
            == AuditAction.USER_REACTIVATED.value,
            AuditLog.entity_type == "user",
            AuditLog.entity_id == target_user.id,
        )
    )

    assert audit_log is not None
    assert audit_log.metadata_json["is_active"] is True
    assert audit_log.metadata_json["revoked_session_count"] == 0


def test_set_active_status_returns_without_audit_when_unchanged(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )
    target_user = create_user(
        db,
        is_active=True,
    )

    audit_count_before = len(
        db.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "user",
                AuditLog.entity_id == target_user.id,
            )
        ).all()
    )

    result = UserService.set_active_status(
        db,
        acting_user=administrator,
        target_user=target_user,
        is_active=True,
    )

    audit_count_after = len(
        db.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "user",
                AuditLog.entity_id == target_user.id,
            )
        ).all()
    )

    assert result.user_id == target_user.id
    assert result.is_active is True
    assert result.revoked_session_count == 0

    assert target_user.is_active is True
    assert audit_count_after == audit_count_before


def test_set_active_status_rejects_self_deactivation(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    with pytest.raises(
        UserServiceError,
        match="cannot deactivate your own account",
    ):
        UserService.set_active_status(
            db,
            acting_user=administrator,
            target_user=administrator,
            is_active=False,
        )

    assert administrator.is_active is True


def test_set_active_status_rejects_anonymised_target(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )
    target_user = create_user(
        db,
        is_anonymised=True,
    )

    with pytest.raises(
        UserServiceError,
        match="An anonymised user cannot be activated or deactivated",
    ):
        UserService.set_active_status(
            db,
            acting_user=administrator,
            target_user=target_user,
            is_active=False,
        )


def test_set_active_status_rejects_non_administrator(
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
        match="Administrator access is required",
    ):
        UserService.set_active_status(
            db,
            acting_user=acting_user,
            target_user=target_user,
            is_active=False,
        )

    assert target_user.is_active is True


def test_set_active_status_does_not_commit_when_commit_is_false(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )
    target_user = create_user(
        db,
        is_active=True,
    )

    with patch.object(
        db,
        "commit",
        wraps=db.commit,
    ) as commit_mock:
        result = UserService.set_active_status(
            db,
            acting_user=administrator,
            target_user=target_user,
            is_active=False,
            commit=False,
        )

    commit_mock.assert_not_called()

    assert result.user_id == target_user.id
    assert result.is_active is False
    assert result.revoked_session_count == 0

    assert target_user.is_active is False


def test_require_administrator_accepts_active_administrator(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    UserService._require_administrator(
        administrator,
    )


@pytest.mark.parametrize(
    (
        "global_role",
        "is_active",
        "is_anonymised",
        "expected_message",
    ),
    [
        (
            GlobalRole.USER.value,
            True,
            False,
            "Administrator access is required",
        ),
        (
            GlobalRole.ADMINISTRATOR.value,
            False,
            False,
            "administrator account is not available",
        ),
        (
            GlobalRole.ADMINISTRATOR.value,
            True,
            True,
            "administrator account is not available",
        ),
    ],
)
def test_require_administrator_rejects_unavailable_users(
    db: Session,
    global_role: str,
    is_active: bool,
    is_anonymised: bool,
    expected_message: str,
) -> None:
    user = create_user(
        db,
        global_role=global_role,
        is_active=is_active,
        is_anonymised=is_anonymised,
    )

    with pytest.raises(
        UserPermissionError,
        match=expected_message,
    ):
        UserService._require_administrator(
            user,
        )
def test_create_user_creates_active_standard_user(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        display_name="Creating Administrator",
    )

    password = "Created-User-Password-123!"

    user = UserService.create_user(
        db,
        acting_user=administrator,
        user_create=UserCreateRequest(
            username="  CREATED-USER  ",
            display_name="  Created User  ",
            password=password,
            confirm_password=password,
            global_role=GlobalRole.USER.value,
            is_active=True,
        ),
    )

    assert user.id is not None
    assert user.username == "created-user"
    assert user.display_name == "Created User"
    assert user.global_role == GlobalRole.USER.value
    assert user.is_active is True
    assert user.is_anonymised is False

    assert verify_password(
        password,
        user.password_hash,
    )


def test_create_user_can_create_inactive_administrator(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    password = "Inactive-Admin-Password-123!"

    user = UserService.create_user(
        db,
        acting_user=administrator,
        user_create=UserCreateRequest(
            username="inactive-new-admin",
            display_name="Inactive New Administrator",
            password=password,
            confirm_password=password,
            global_role=(
                GlobalRole.ADMINISTRATOR.value
            ),
            is_active=False,
        ),
    )

    assert user.global_role == (
        GlobalRole.ADMINISTRATOR.value
    )

    assert user.is_active is False


def test_create_user_records_audit_log_without_password(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        display_name="Audit Administrator",
    )

    password = "Never-Audit-This-Password-123!"

    user = UserService.create_user(
        db,
        acting_user=administrator,
        user_create=UserCreateRequest(
            username="audited-created-user",
            display_name="Audited Created User",
            password=password,
            confirm_password=password,
            global_role=GlobalRole.USER.value,
            is_active=True,
        ),
        ip_address="192.0.2.60",
        user_agent="User creation test",
    )

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action
            == AuditAction.USER_CREATED.value,
            AuditLog.entity_type == "user",
            AuditLog.entity_id == user.id,
        )
    )

    assert audit_log is not None
    assert audit_log.user_id == administrator.id
    assert audit_log.summary == (
        "Audit Administrator created the user "
        "Audited Created User."
    )

    assert audit_log.metadata_json == {
        "username": "audited-created-user",
        "display_name": "Audited Created User",
        "global_role": GlobalRole.USER.value,
        "is_active": True,
    }

    assert audit_log.ip_address == "192.0.2.60"
    assert audit_log.user_agent == "User creation test"

    audit_serialised = str(
        audit_log.metadata_json,
    )

    assert password not in audit_serialised
    assert "password" not in audit_serialised.lower()


def test_create_user_rejects_duplicate_username_case_insensitively(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    existing_user = create_user(
        db,
        username="duplicate-user",
    )

    password = "Duplicate-User-Password-123!"

    with pytest.raises(
        UsernameAlreadyExistsError,
        match="username already exists",
    ):
        UserService.create_user(
            db,
            acting_user=administrator,
            user_create=UserCreateRequest(
                username="DUPLICATE-USER",
                display_name="Duplicate User",
                password=password,
                confirm_password=password,
                global_role=GlobalRole.USER.value,
            ),
        )

    assert (
        UserService.get_by_username(
            db,
            username="duplicate-user",
        )
        is existing_user
    )


def test_create_user_rejects_non_administrator(
    db: Session,
) -> None:
    acting_user = create_user(
        db,
    )

    password = "Unauthorised-Create-Password-123!"

    with pytest.raises(
        UserPermissionError,
        match="Administrator access is required",
    ):
        UserService.create_user(
            db,
            acting_user=acting_user,
            user_create=UserCreateRequest(
                username="unauthorised-created-user",
                display_name="Unauthorised Created User",
                password=password,
                confirm_password=password,
                global_role=GlobalRole.USER.value,
            ),
        )

    assert UserService.get_by_username(
        db,
        username="unauthorised-created-user",
    ) is None


def test_create_user_rejects_inactive_administrator(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        is_active=False,
    )

    password = "Inactive-Actor-Password-123!"

    with pytest.raises(
        UserPermissionError,
        match="administrator account is not available",
    ):
        UserService.create_user(
            db,
            acting_user=administrator,
            user_create=UserCreateRequest(
                username="inactive-actor-created-user",
                display_name="Inactive Actor Created User",
                password=password,
                confirm_password=password,
                global_role=GlobalRole.USER.value,
            ),
        )


def test_create_user_validates_password_strength(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    with pytest.raises(ValueError):
        UserService.create_user(
            db,
            acting_user=administrator,
            user_create=UserCreateRequest(
                username="weak-password-user",
                display_name="Weak Password User",
                password="weak",
                confirm_password="weak",
                global_role=GlobalRole.USER.value,
            ),
        )

    assert UserService.get_by_username(
        db,
        username="weak-password-user",
    ) is None


def test_create_user_does_not_commit_when_commit_is_false(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    password = "No-Commit-User-Password-123!"

    with patch.object(
        db,
        "commit",
        wraps=db.commit,
    ) as commit_mock:
        user = UserService.create_user(
            db,
            acting_user=administrator,
            user_create=UserCreateRequest(
                username="no-commit-created-user",
                display_name="No Commit Created User",
                password=password,
                confirm_password=password,
                global_role=GlobalRole.USER.value,
            ),
            commit=False,
        )

    commit_mock.assert_not_called()

    assert user.id is not None
    assert user.username == "no-commit-created-user"
    assert verify_password(
        password,
        user.password_hash,
    )


def test_update_user_updates_profile_and_role(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target_user = create_user(
        db,
        username="old-profile-user",
        display_name="Old Profile User",
        global_role=GlobalRole.USER.value,
    )

    result = UserService.update_user(
        db,
        acting_user=administrator,
        target_user=target_user,
        user_update=UserUpdateRequest(
            username="NEW-PROFILE-USER",
            display_name="New Profile User",
            global_role=(
                GlobalRole.ADMINISTRATOR.value
            ),
        ),
    )

    assert result is target_user
    assert target_user.username == "new-profile-user"
    assert target_user.display_name == "New Profile User"
    assert target_user.global_role == (
        GlobalRole.ADMINISTRATOR.value
    )


def test_update_user_records_changed_fields_in_audit_log(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        display_name="Editing Administrator",
    )

    target_user = create_user(
        db,
        username="before-edit",
        display_name="Before Edit",
        global_role=GlobalRole.USER.value,
    )

    UserService.update_user(
        db,
        acting_user=administrator,
        target_user=target_user,
        user_update=UserUpdateRequest(
            username="after-edit",
            display_name="After Edit",
            global_role=(
                GlobalRole.ADMINISTRATOR.value
            ),
        ),
        ip_address="198.51.100.61",
        user_agent="User editing test",
    )

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action
            == AuditAction.USER_UPDATED.value,
            AuditLog.entity_type == "user",
            AuditLog.entity_id == target_user.id,
        )
    )

    assert audit_log is not None
    assert audit_log.user_id == administrator.id

    assert audit_log.metadata_json["changes"] == {
        "username": {
            "previous": "before-edit",
            "current": "after-edit",
        },
        "display_name": {
            "previous": "Before Edit",
            "current": "After Edit",
        },
        "global_role": {
            "previous": GlobalRole.USER.value,
            "current": (
                GlobalRole.ADMINISTRATOR.value
            ),
        },
    }

    assert audit_log.ip_address == "198.51.100.61"
    assert audit_log.user_agent == "User editing test"


def test_update_user_rejects_duplicate_username(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target_user = create_user(
        db,
        username="editable-target",
        display_name="Editable Target",
    )

    create_user(
        db,
        username="already-used",
    )

    with pytest.raises(
        UsernameAlreadyExistsError,
        match="username already exists",
    ):
        UserService.update_user(
            db,
            acting_user=administrator,
            target_user=target_user,
            user_update=UserUpdateRequest(
                username="ALREADY-USED",
                display_name="Editable Target",
                global_role=GlobalRole.USER.value,
            ),
        )

    assert target_user.username == "editable-target"


def test_update_user_allows_existing_username_for_same_user(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target_user = create_user(
        db,
        username="same-username",
        display_name="Old Display Name",
    )

    result = UserService.update_user(
        db,
        acting_user=administrator,
        target_user=target_user,
        user_update=UserUpdateRequest(
            username="SAME-USERNAME",
            display_name="New Display Name",
            global_role=GlobalRole.USER.value,
        ),
    )

    assert result is target_user
    assert target_user.username == "same-username"
    assert target_user.display_name == "New Display Name"


def test_update_user_rejects_anonymised_target(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target_user = create_user(
        db,
        is_anonymised=True,
    )

    with pytest.raises(
        AnonymisedUserProfileError,
        match="anonymised user cannot be edited",
    ):
        UserService.update_user(
            db,
            acting_user=administrator,
            target_user=target_user,
            user_update=UserUpdateRequest(
                username=target_user.username,
                display_name=target_user.display_name,
                global_role=GlobalRole.USER.value,
            ),
        )


def test_update_user_rejects_removing_own_administrator_role(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        username="self-edit-admin",
        display_name="Self Edit Administrator",
    )

    with pytest.raises(
        UserSelfRoleChangeError,
        match="remove your own administrator role",
    ):
        UserService.update_user(
            db,
            acting_user=administrator,
            target_user=administrator,
            user_update=UserUpdateRequest(
                username=administrator.username,
                display_name=administrator.display_name,
                global_role=GlobalRole.USER.value,
            ),
        )

    assert administrator.global_role == (
        GlobalRole.ADMINISTRATOR.value
    )


def test_update_user_allows_administrator_to_edit_own_name(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        username="self-name-admin",
        display_name="Old Administrator Name",
    )

    result = UserService.update_user(
        db,
        acting_user=administrator,
        target_user=administrator,
        user_update=UserUpdateRequest(
            username="self-name-admin",
            display_name="New Administrator Name",
            global_role=(
                GlobalRole.ADMINISTRATOR.value
            ),
        ),
    )

    assert result is administrator
    assert (
        administrator.display_name
        == "New Administrator Name"
    )


def test_update_user_with_no_changes_returns_without_audit(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target_user = create_user(
        db,
        username="unchanged-profile",
        display_name="Unchanged Profile",
        global_role=GlobalRole.USER.value,
    )

    audit_count_before = len(
        db.scalars(
            select(AuditLog).where(
                AuditLog.action
                == AuditAction.USER_UPDATED.value,
                AuditLog.entity_type == "user",
                AuditLog.entity_id == target_user.id,
            )
        ).all()
    )

    result = UserService.update_user(
        db,
        acting_user=administrator,
        target_user=target_user,
        user_update=UserUpdateRequest(
            username="UNCHANGED-PROFILE",
            display_name="Unchanged Profile",
            global_role=GlobalRole.USER.value,
        ),
    )

    audit_count_after = len(
        db.scalars(
            select(AuditLog).where(
                AuditLog.action
                == AuditAction.USER_UPDATED.value,
                AuditLog.entity_type == "user",
                AuditLog.entity_id == target_user.id,
            )
        ).all()
    )

    assert result is target_user
    assert audit_count_after == audit_count_before


def test_update_user_rejects_non_administrator(
    db: Session,
) -> None:
    acting_user = create_user(
        db,
    )

    target_user = create_user(
        db,
        username="protected-profile",
        display_name="Protected Profile",
    )

    with pytest.raises(
        UserPermissionError,
        match="Administrator access is required",
    ):
        UserService.update_user(
            db,
            acting_user=acting_user,
            target_user=target_user,
            user_update=UserUpdateRequest(
                username="changed-profile",
                display_name="Changed Profile",
                global_role=GlobalRole.USER.value,
            ),
        )

    assert target_user.username == "protected-profile"
    assert target_user.display_name == "Protected Profile"


def test_update_user_does_not_commit_when_commit_is_false(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target_user = create_user(
        db,
        username="no-commit-profile",
        display_name="No Commit Profile",
    )

    with patch.object(
        db,
        "commit",
        wraps=db.commit,
    ) as commit_mock:
        result = UserService.update_user(
            db,
            acting_user=administrator,
            target_user=target_user,
            user_update=UserUpdateRequest(
                username="updated-no-commit-profile",
                display_name="Updated No Commit Profile",
                global_role=GlobalRole.USER.value,
            ),
            commit=False,
        )

    commit_mock.assert_not_called()

    assert result is target_user

    assert (
        target_user.username
        == "updated-no-commit-profile"
    )

    assert (
        target_user.display_name
        == "Updated No Commit Profile"
    )