from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import AuditAction
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    generate_csrf_token,
    generate_session_token,
    hash_password,
    hash_token,
    password_hash_needs_update,
    verify_password,
)
from app.core.timezone import utc_now
from app.models.session import AuthSession
from app.models.user import User
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, LoginResult
from app.services.audit_service import AuditService


DEFAULT_SESSION_HOURS = 12
DEFAULT_REMEMBER_ME_DAYS = 30
DEFAULT_LAST_SEEN_UPDATE_MINUTES = 5

MAX_IP_ADDRESS_LENGTH = 45
MAX_USER_AGENT_LENGTH = 512


class AuthenticationError(ValueError):
    """Base exception for authentication failures."""


class InvalidCredentialsError(AuthenticationError):
    """Raised when a username or password is invalid."""


class InvalidSessionError(AuthenticationError):
    """Raised when an authentication session cannot be used."""


class AuthService:
    @staticmethod
    def authenticate(
        db: Session,
        *,
        login: LoginRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> LoginResult:
        """
        Authenticate a user and create a database-backed session.

        Failed authentication uses a generic error message so callers cannot
        determine whether a username exists, is inactive or has an incorrect
        password.
        """
        normalised_ip_address = AuthService._normalise_ip_address(
            ip_address,
        )
        normalised_user_agent = AuthService._normalise_user_agent(
            user_agent,
        )

        user = UserRepository.get_by_username(
            db,
            username=login.username,
        )

        if user is None:
            verify_password(
                login.password,
                DUMMY_PASSWORD_HASH,
            )

            AuthService._record_failed_login(
                db,
                username=login.username,
                reason="unknown_username",
                ip_address=normalised_ip_address,
                user_agent=normalised_user_agent,
            )

            db.commit()

            raise InvalidCredentialsError(
                "Invalid username or password.",
            )

        password_is_valid = verify_password(
            login.password,
            user.password_hash,
        )

        if not password_is_valid:
            AuthService._record_failed_login(
                db,
                username=login.username,
                user=user,
                reason="invalid_password",
                ip_address=normalised_ip_address,
                user_agent=normalised_user_agent,
            )

            db.commit()

            raise InvalidCredentialsError(
                "Invalid username or password.",
            )

        if not user.can_authenticate:
            AuthService._record_failed_login(
                db,
                username=login.username,
                user=user,
                reason="account_unavailable",
                ip_address=normalised_ip_address,
                user_agent=normalised_user_agent,
            )

            db.commit()

            raise InvalidCredentialsError(
                "Invalid username or password.",
            )

        now = utc_now()

        session_token = generate_session_token()
        csrf_token = generate_csrf_token()

        expires_at = AuthService._calculate_expiry(
            now=now,
            remember_me=login.remember_me,
        )

        auth_session = SessionRepository.create(
            db,
            user_id=user.id,
            token_hash=hash_token(
                session_token,
            ),
            csrf_token_hash=hash_token(
                csrf_token,
            ),
            expires_at=expires_at,
            last_seen_at=now,
            remember_me=login.remember_me,
            ip_address=normalised_ip_address,
            user_agent=normalised_user_agent,
        )

        if password_hash_needs_update(
            user.password_hash,
        ):
            UserRepository.update_password_hash(
                db,
                user=user,
                password_hash=hash_password(
                    login.password,
                ),
            )

        AuditService.record(
            db,
            user=user,
            action=AuditAction.LOGIN,
            summary=f"{user.display_name} logged in.",
            entity_type="auth_session",
            entity_id=auth_session.id,
            metadata_json={
                "username": user.username,
                "remember_me": login.remember_me,
                "expires_at": expires_at.isoformat(),
            },
            ip_address=normalised_ip_address,
            user_agent=normalised_user_agent,
        )

        db.commit()
        db.refresh(auth_session)

        return LoginResult(
            user_id=user.id,
            session_id=auth_session.id,
            session_token=session_token,
            csrf_token=csrf_token,
            expires_at=auth_session.expires_at,
            remember_me=auth_session.remember_me,
        )

    @staticmethod
    def resolve_session(
        db: Session,
        *,
        session_token: str | None,
        update_last_seen: bool = True,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthSession | None:
        """
        Resolve a raw browser session token to an active authentication
        session.

        Invalid, expired, revoked and unavailable-user sessions return None.
        """
        if not session_token:
            return None

        auth_session = SessionRepository.get_active_by_token_hash(
            db,
            token_hash=hash_token(
                session_token,
            ),
        )

        if auth_session is None:
            return None

        if not auth_session.user.can_authenticate:
            SessionRepository.revoke(
                db,
                auth_session=auth_session,
            )

            db.commit()

            return None

        if update_last_seen and AuthService._should_update_last_seen(
            auth_session,
        ):
            SessionRepository.update_last_seen(
                db,
                auth_session=auth_session,
                ip_address=AuthService._normalise_ip_address(
                    ip_address,
                ),
                user_agent=AuthService._normalise_user_agent(
                    user_agent,
                ),
            )

            db.commit()
            db.refresh(auth_session)

        return auth_session

    @staticmethod
    def require_session(
        db: Session,
        *,
        session_token: str | None,
        update_last_seen: bool = True,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthSession:
        auth_session = AuthService.resolve_session(
            db,
            session_token=session_token,
            update_last_seen=update_last_seen,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if auth_session is None:
            raise InvalidSessionError(
                "Authentication is required.",
            )

        return auth_session

    @staticmethod
    def resolve_user(
        db: Session,
        *,
        session_token: str | None,
        update_last_seen: bool = True,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> User | None:
        auth_session = AuthService.resolve_session(
            db,
            session_token=session_token,
            update_last_seen=update_last_seen,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if auth_session is None:
            return None

        return auth_session.user

    @staticmethod
    def logout(
        db: Session,
        *,
        session_token: str | None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> bool:
        """
        Revoke the current session and record a logout event.

        The operation is idempotent. Missing or invalid tokens return False.
        """
        if not session_token:
            return False

        auth_session = SessionRepository.get_by_token_hash(
            db,
            token_hash=hash_token(
                session_token,
            ),
        )

        if auth_session is None:
            return False

        if auth_session.is_revoked:
            return False

        SessionRepository.revoke(
            db,
            auth_session=auth_session,
        )

        AuditService.record(
            db,
            user=auth_session.user,
            action=AuditAction.LOGOUT,
            summary=f"{auth_session.user.display_name} logged out.",
            entity_type="auth_session",
            entity_id=auth_session.id,
            metadata_json={
                "username": auth_session.user.username,
            },
            ip_address=AuthService._normalise_ip_address(
                ip_address,
            ),
            user_agent=AuthService._normalise_user_agent(
                user_agent,
            ),
        )

        db.commit()

        return True

    @staticmethod
    def revoke_all_sessions_for_user(
        db: Session,
        *,
        user: User,
        exclude_session_id: int | None = None,
        commit: bool = False,
    ) -> int:
        revoked_count = SessionRepository.revoke_all_for_user(
            db,
            user_id=user.id,
            exclude_session_id=exclude_session_id,
        )

        if commit:
            db.commit()

        return revoked_count

    @staticmethod
    def rotate_csrf_token(
        db: Session,
        *,
        auth_session: AuthSession,
        commit: bool = True,
    ) -> str:
        """
        Generate a replacement CSRF token for an existing session.

        Only the hash is persisted. The raw token is returned once to the
        caller.
        """
        csrf_token = generate_csrf_token()

        SessionRepository.update_csrf_token_hash(
            db,
            auth_session=auth_session,
            csrf_token_hash=hash_token(
                csrf_token,
            ),
        )

        if commit:
            db.commit()
            db.refresh(auth_session)

        return csrf_token

    @staticmethod
    def cleanup_expired_sessions(
        db: Session,
        *,
        expired_before: datetime | None = None,
        commit: bool = True,
    ) -> int:
        deleted_count = SessionRepository.delete_expired(
            db,
            expired_before=expired_before,
        )

        if commit:
            db.commit()

        return deleted_count

    @staticmethod
    def _record_failed_login(
        db: Session,
        *,
        username: str,
        reason: str,
        ip_address: str | None,
        user_agent: str | None,
        user: User | None = None,
    ) -> None:
        metadata = {
            "username": username.strip().lower(),
            "successful": False,
            "reason": reason,
        }

        if user is not None:
            AuditService.record(
                db,
                user=user,
                action=AuditAction.LOGIN_FAILED,
                summary="A login attempt was rejected.",
                entity_type="user",
                entity_id=user.id,
                metadata_json=metadata,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            return

        AuditService.record_system_event(
            db,
            action=AuditAction.LOGIN_FAILED,
            summary="A login attempt was rejected.",
            entity_type="authentication",
            metadata_json=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @staticmethod
    def _calculate_expiry(
        *,
        now: datetime,
        remember_me: bool,
    ) -> datetime:
        if remember_me:
            remember_me_days = getattr(
                settings,
                "remember_me_duration_days",
                DEFAULT_REMEMBER_ME_DAYS,
            )

            return now + timedelta(
                days=remember_me_days,
            )

        session_hours = getattr(
            settings,
            "session_duration_hours",
            DEFAULT_SESSION_HOURS,
        )

        return now + timedelta(
            hours=session_hours,
        )

    @staticmethod
    def _should_update_last_seen(
        auth_session: AuthSession,
    ) -> bool:
        update_interval_minutes = getattr(
            settings,
            "session_last_seen_update_minutes",
            DEFAULT_LAST_SEEN_UPDATE_MINUTES,
        )

        next_update_at = auth_session.last_seen_at + timedelta(
            minutes=update_interval_minutes,
        )

        return utc_now() >= next_update_at

    @staticmethod
    def _normalise_ip_address(
        ip_address: str | None,
    ) -> str | None:
        if ip_address is None:
            return None

        normalised = ip_address.strip()

        if not normalised:
            return None

        return normalised[:MAX_IP_ADDRESS_LENGTH]

    @staticmethod
    def _normalise_user_agent(
        user_agent: str | None,
    ) -> str | None:
        if user_agent is None:
            return None

        normalised = user_agent.strip()

        if not normalised:
            return None

        return normalised[:MAX_USER_AGENT_LENGTH]