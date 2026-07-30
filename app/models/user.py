from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import GlobalRole
from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin


class User(
    Base,
    IntegerPrimaryKeyMixin,
    TimestampMixin,
):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )

    display_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    global_role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=GlobalRole.USER,
        server_default=text("'user'"),
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    is_anonymised: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    anonymised_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<User "
            f"id={self.id!r} "
            f"username={self.username!r} "
            f"global_role={self.global_role!r}>"
        )

    @property
    def is_administrator(self) -> bool:
        return self.global_role == GlobalRole.ADMINISTRATOR

    @property
    def can_authenticate(self) -> bool:
        return self.is_active and not self.is_anonymised