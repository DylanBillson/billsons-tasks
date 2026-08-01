from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.section import Section
    from app.models.user import User


class SectionMembership(
    Base,
    IntegerPrimaryKeyMixin,
    TimestampMixin,
):
    __tablename__ = "section_memberships"

    __table_args__ = (
        UniqueConstraint(
            "section_id",
            "user_id",
            name="uq_section_memberships_section_id_user_id",
        ),
    )

    section_id: Mapped[int] = mapped_column(
        ForeignKey(
            "sections.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    section: Mapped["Section"] = relationship(
        back_populates="memberships",
        lazy="joined",
    )

    user: Mapped["User"] = relationship(
        back_populates="section_memberships",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return (
            f"<SectionMembership "
            f"id={self.id!r} "
            f"section_id={self.section_id!r} "
            f"user_id={self.user_id!r}>"
        )