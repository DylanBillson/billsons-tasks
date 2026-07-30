from sqlalchemy.orm import Session

from app.core.constants import AuditAction, GlobalRole
from app.core.security import hash_password, validate_password
from app.core.timezone import utc_now
from app.models.user import User
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import PasswordResetRequest, PasswordResetResult
from app.services.audit_service import AuditService


class UserServiceError(ValueError):
    """Base exception for user-service failures."""


class UserNotFoundError(UserServiceError):
    """Raised when a requested user does not exist."""


class UserPermissionError(UserServiceError):
    """Raised when a user is not permitted to perform an operation."""


class UsernameAlreadyExistsError(UserServiceError):
    """Raised when a username is already assigned to another user."""


class UserService:
    @staticmethod
    def get_user(
        db: Session,
        *,
        user_id: int,
    ) -> User | None:
        return UserRepository.get_by_id(
            db,
            user_id=user_id,
        )

    @staticmethod
    def require_user(
        db: Session,
        *,
        user_id: int,
    ) -> User:
        user = UserService.get_user(
            db,
            user_id=user_id,
        )

        if user is None:
            raise UserNotFoundError(
                "User not found.",
            )

        return user

    @staticmethod
    def get_by_username(
        db: Session,
        *,
        username: str,
    ) -> User | None:
        return UserRepository.get_by_username(
            db,
            username=username,
        )

    @staticmethod
    def list_users(
        db: Session,
        *,
        include_inactive: bool = True,
        include_anonymised: bool = True,
    ) -> list[User]:
        return UserRepository.list_all(
            db,
            include_inactive=include_inactive,
            include_anonymised=include_anonymised,
        )

    @staticmethod
    def reset_password(
        db: Session,
        *,
        acting_user: User,
        target_user: User,
        password_reset: PasswordResetRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> PasswordResetResult:
        """
        Reset a user's password as an administrator.

        All existing authentication sessions belonging to the target user are
        revoked so that the previous password cannot leave existing browser
        sessions active.
        """
        UserService._require_administrator(
            acting_user,
        )

        if target_user.is_anonymised:
            raise UserServiceError(
                "The password of an anonymised user cannot be reset.",
            )

        validate_password(
            password_reset.new_password,
            confirmation=password_reset.confirm_password,
        )

        password_hash = hash_password(
            password_reset.new_password,
        )

        UserRepository.update_password_hash(
            db,
            user=target_user,
            password_hash=password_hash,
        )

        password_reset_at = utc_now()

        revoked_session_count = (
            SessionRepository.revoke_all_for_user(
                db,
                user_id=target_user.id,
                revoked_at=password_reset_at,
            )
        )

        AuditService.record(
            db,
            user=acting_user,
            action=AuditAction.PASSWORD_RESET,
            summary=(
                f"{acting_user.display_name} reset the password for "
                f"{target_user.display_name}."
            ),
            entity_type="user",
            entity_id=target_user.id,
            metadata_json={
                "username": target_user.username,
                "revoked_session_count": revoked_session_count,
                "password_reset_at": password_reset_at.isoformat(),
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()
            db.refresh(target_user)

        return PasswordResetResult(
            user_id=target_user.id,
            revoked_session_count=revoked_session_count,
            password_reset_at=password_reset_at,
        )

    @staticmethod
    def reset_password_by_user_id(
        db: Session,
        *,
        acting_user: User,
        target_user_id: int,
        password_reset: PasswordResetRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> PasswordResetResult:
        """
        Retrieve a target user by ID and reset their password.

        This is convenient for administrator routes that receive the target
        user ID from the URL.
        """
        target_user = UserService.require_user(
            db,
            user_id=target_user_id,
        )

        return UserService.reset_password(
            db,
            acting_user=acting_user,
            target_user=target_user,
            password_reset=password_reset,
            ip_address=ip_address,
            user_agent=user_agent,
            commit=commit,
        )

    @staticmethod
    def set_active_status(
        db: Session,
        *,
        acting_user: User,
        target_user: User,
        is_active: bool,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> User:
        """
        Activate or deactivate a user.

        Deactivation immediately revokes all of the target user's active
        authentication sessions.
        """
        UserService._require_administrator(
            acting_user,
        )

        if target_user.is_anonymised:
            raise UserServiceError(
                "An anonymised user cannot be activated or deactivated.",
            )

        if acting_user.id == target_user.id and not is_active:
            raise UserServiceError(
                "You cannot deactivate your own account.",
            )

        if target_user.is_active == is_active:
            return target_user

        UserRepository.update_profile(
            db,
            user=target_user,
            is_active=is_active,
        )

        revoked_session_count = 0

        if not is_active:
            revoked_session_count = (
                SessionRepository.revoke_all_for_user(
                    db,
                    user_id=target_user.id,
                )
            )

        action = (
            AuditAction.USER_REACTIVATED
            if is_active
            else AuditAction.USER_DEACTIVATED
        )

        status = (
            "reactivated"
            if is_active
            else "deactivated"
        )

        AuditService.record(
            db,
            user=acting_user,
            action=action,
            summary=(
                f"{acting_user.display_name} {status} "
                f"{target_user.display_name}."
            ),
            entity_type="user",
            entity_id=target_user.id,
            metadata_json={
                "username": target_user.username,
                "is_active": is_active,
                "revoked_session_count": revoked_session_count,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()
            db.refresh(target_user)

        return target_user

    @staticmethod
    def _require_administrator(
        user: User,
    ) -> None:
        if (
            user.global_role
            != GlobalRole.ADMINISTRATOR.value
        ):
            raise UserPermissionError(
                "Administrator access is required.",
            )

        if not user.can_authenticate:
            raise UserPermissionError(
                "The administrator account is not available.",
            )