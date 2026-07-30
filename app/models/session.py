from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class AuthSession(
    Base,
    IntegerPrimaryKeyMixin,
    TimestampMixin,
):
    __tablename__ = "auth_sessions"

    __table_args__ = (
        Index(
            "ix_auth_sessions_token_hash",
            "token_hash",
            unique=True,
        ),
        Index(
            "ix_auth_sessions_user_expires_at",
            "user_id",
            "expires_at",
        ),
        Index(
            "ix_auth_sessions_expires_at",
            "expires_at",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    csrf_token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    remember_me: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        server_default="false",
    )

    is_revoked: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        server_default="false",
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    user_agent: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )

    user: Mapped["User"] = relationship(
        lazy="joined",
    )

    @property
    def is_expired(self) -> bool:
        from app.core.timezone import utc_now

        return self.expires_at <= utc_now()

    @property
    def is_valid(self) -> bool:
        return not self.is_revoked and not self.is_expired

    def __repr__(self) -> str:
        return (
            f"<AuthSession "
            f"id={self.id!r} "
            f"user_id={self.user_id!r} "
            f"expires_at={self.expires_at!r} "
            f"remember_me={self.remember_me!r} "
            f"is_revoked={self.is_revoked!r}>"
        )