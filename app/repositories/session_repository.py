from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.timezone import utc_now
from app.models.session import AuthSession


class SessionRepository:
    @staticmethod
    def get_by_id(
        db: Session,
        *,
        session_id: int,
    ) -> AuthSession | None:
        query = select(AuthSession).where(
            AuthSession.id == session_id,
        )

        return db.scalar(
            query,
        )

    @staticmethod
    def get_by_token_hash(
        db: Session,
        *,
        token_hash: str,
    ) -> AuthSession | None:
        query = select(AuthSession).where(
            AuthSession.token_hash == token_hash,
        )

        return db.scalar(
            query,
        )

    @staticmethod
    def get_active_by_token_hash(
        db: Session,
        *,
        token_hash: str,
        now: datetime | None = None,
    ) -> AuthSession | None:
        current_time = now or utc_now()

        query = select(AuthSession).where(
            AuthSession.token_hash == token_hash,
            AuthSession.is_revoked.is_(False),
            AuthSession.expires_at > current_time,
        )

        return db.scalar(
            query,
        )

    @staticmethod
    def list_for_user(
        db: Session,
        *,
        user_id: int,
        include_revoked: bool = True,
        include_expired: bool = True,
        now: datetime | None = None,
    ) -> list[AuthSession]:
        current_time = now or utc_now()

        query = select(AuthSession).where(
            AuthSession.user_id == user_id,
        )

        if not include_revoked:
            query = query.where(
                AuthSession.is_revoked.is_(False),
            )

        if not include_expired:
            query = query.where(
                AuthSession.expires_at > current_time,
            )

        query = query.order_by(
            AuthSession.last_seen_at.desc(),
            AuthSession.created_at.desc(),
            AuthSession.id.desc(),
        )

        return list(
            db.scalars(
                query,
            ).all(),
        )

    @staticmethod
    def create(
        db: Session,
        *,
        user_id: int,
        token_hash: str,
        csrf_token_hash: str,
        expires_at: datetime,
        last_seen_at: datetime,
        remember_me: bool = False,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthSession:
        auth_session = AuthSession(
            user_id=user_id,
            token_hash=token_hash,
            csrf_token_hash=csrf_token_hash,
            expires_at=expires_at,
            last_seen_at=last_seen_at,
            remember_me=remember_me,
            is_revoked=False,
            revoked_at=None,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        db.add(
            auth_session,
        )
        db.flush()

        return auth_session

    @staticmethod
    def update_last_seen(
        db: Session,
        *,
        auth_session: AuthSession,
        last_seen_at: datetime | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthSession:
        auth_session.last_seen_at = (
            last_seen_at
            or utc_now()
        )

        if ip_address is not None:
            auth_session.ip_address = ip_address

        if user_agent is not None:
            auth_session.user_agent = user_agent

        db.add(
            auth_session,
        )
        db.flush()

        return auth_session

    @staticmethod
    def update_csrf_token_hash(
        db: Session,
        *,
        auth_session: AuthSession,
        csrf_token_hash: str,
    ) -> AuthSession:
        auth_session.csrf_token_hash = csrf_token_hash

        db.add(
            auth_session,
        )
        db.flush()

        return auth_session

    @staticmethod
    def revoke(
        db: Session,
        *,
        auth_session: AuthSession,
        revoked_at: datetime | None = None,
    ) -> AuthSession:
        if auth_session.is_revoked:
            return auth_session

        auth_session.is_revoked = True
        auth_session.revoked_at = (
            revoked_at
            or utc_now()
        )

        db.add(
            auth_session,
        )
        db.flush()

        return auth_session

    @staticmethod
    def revoke_by_token_hash(
        db: Session,
        *,
        token_hash: str,
        revoked_at: datetime | None = None,
    ) -> int:
        resolved_revoked_at = (
            revoked_at
            or utc_now()
        )

        statement = (
            update(
                AuthSession,
            )
            .where(
                AuthSession.token_hash == token_hash,
                AuthSession.is_revoked.is_(False),
                AuthSession.expires_at
                > resolved_revoked_at,
            )
            .values(
                is_revoked=True,
                revoked_at=resolved_revoked_at,
            )
        )

        result = db.execute(
            statement,
        )

        return int(
            result.rowcount
            or 0,
        )

    @staticmethod
    def revoke_all_for_user(
        db: Session,
        *,
        user_id: int,
        exclude_session_id: int | None = None,
        revoked_at: datetime | None = None,
    ) -> int:
        resolved_revoked_at = (
            revoked_at
            or utc_now()
        )

        statement = (
            update(
                AuthSession,
            )
            .where(
                AuthSession.user_id == user_id,
                AuthSession.is_revoked.is_(False),
                AuthSession.expires_at
                > resolved_revoked_at,
            )
            .values(
                is_revoked=True,
                revoked_at=resolved_revoked_at,
            )
        )

        if exclude_session_id is not None:
            statement = statement.where(
                AuthSession.id
                != exclude_session_id,
            )

        result = db.execute(
            statement,
        )

        return int(
            result.rowcount
            or 0,
        )

    @staticmethod
    def delete_expired(
        db: Session,
        *,
        expired_before: datetime | None = None,
    ) -> int:
        cutoff = (
            expired_before
            or utc_now()
        )

        statement = delete(
            AuthSession,
        ).where(
            AuthSession.expires_at <= cutoff,
        )

        result = db.execute(
            statement,
        )

        return int(
            result.rowcount
            or 0,
        )

    @staticmethod
    def delete_revoked(
        db: Session,
        *,
        revoked_before: datetime,
    ) -> int:
        statement = delete(
            AuthSession,
        ).where(
            AuthSession.is_revoked.is_(True),
            AuthSession.revoked_at.is_not(None),
            AuthSession.revoked_at <= revoked_before,
        )

        result = db.execute(
            statement,
        )

        return int(
            result.rowcount
            or 0,
        )