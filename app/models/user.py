from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import GlobalRole
from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.company_membership import CompanyMembership
    from app.models.section import Section
    from app.models.section_membership import SectionMembership


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
        default=GlobalRole.USER.value,
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

    company_memberships: Mapped[list["CompanyMembership"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    section_memberships: Mapped[list["SectionMembership"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    created_sections: Mapped[list["Section"]] = relationship(
        back_populates="created_by",
        foreign_keys="Section.created_by_user_id",
        lazy="selectin",
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
        return (
            self.global_role
            == GlobalRole.ADMINISTRATOR.value
        )

    @property
    def can_authenticate(self) -> bool:
        return (
            self.is_active
            and not self.is_anonymised
        )