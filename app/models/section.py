from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.section_list import SectionList
    from app.models.section_membership import SectionMembership
    from app.models.user import User


class Section(
    Base,
    IntegerPrimaryKeyMixin,
    TimestampMixin,
):
    __tablename__ = "sections"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "name",
            name="uq_sections_company_id_name",
        ),
    )

    company_id: Mapped[int] = mapped_column(
        ForeignKey(
            "companies.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    company: Mapped["Company"] = relationship(
        back_populates="sections",
        lazy="joined",
    )

    created_by: Mapped["User"] = relationship(
        back_populates="created_sections",
        foreign_keys=[
            created_by_user_id,
        ],
        lazy="joined",
    )

    memberships: Mapped[list["SectionMembership"]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="select",
    )

    lists: Mapped[list["SectionList"]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=(
            "SectionList.sort_position.asc(), "
            "SectionList.id.asc()"
        ),
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<Section "
            f"id={self.id!r} "
            f"company_id={self.company_id!r} "
            f"created_by_user_id={self.created_by_user_id!r} "
            f"name={self.name!r} "
            f"is_archived={self.is_archived!r}>"
        )