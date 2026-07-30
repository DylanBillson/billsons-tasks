from sqlalchemy import Boolean, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin


class ApplicationSetting(
    Base,
    IntegerPrimaryKeyMixin,
    TimestampMixin,
):
    __tablename__ = "application_settings"

    key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )

    value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    value_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="string",
        server_default=text("'string'"),
    )

    is_public: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<ApplicationSetting "
            f"id={self.id!r} "
            f"key={self.key!r} "
            f"value_type={self.value_type!r}>"
        )