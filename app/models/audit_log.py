from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class AuditLog(
    Base,
    IntegerPrimaryKeyMixin,
    TimestampMixin,
):
    __tablename__ = "audit_logs"

    __table_args__ = (
        Index(
            "ix_audit_logs_entity",
            "entity_type",
            "entity_id",
        ),
        Index(
            "ix_audit_logs_created_at",
            "created_at",
        ),
    )

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    entity_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    entity_id: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    user: Mapped["User | None"] = relationship(
        lazy="joined",
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog "
            f"id={self.id!r} "
            f"user_id={self.user_id!r} "
            f"action={self.action!r} "
            f"entity_type={self.entity_type!r} "
            f"entity_id={self.entity_id!r}>"
        )