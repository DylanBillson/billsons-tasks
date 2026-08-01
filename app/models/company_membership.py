from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import CompanyRole
from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.user import User


class CompanyMembership(
    Base,
    IntegerPrimaryKeyMixin,
    TimestampMixin,
):
    __tablename__ = "company_memberships"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "user_id",
            name="uq_company_memberships_company_id_user_id",
        ),
        CheckConstraint(
            "role IN ('manager', 'employee')",
            name="company_membership_role",
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

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=CompanyRole.EMPLOYEE.value,
        server_default=text("'employee'"),
        index=True,
    )

    company: Mapped["Company"] = relationship(
        back_populates="memberships",
        lazy="joined",
    )

    user: Mapped["User"] = relationship(
        back_populates="company_memberships",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return (
            f"<CompanyMembership "
            f"id={self.id!r} "
            f"company_id={self.company_id!r} "
            f"user_id={self.user_id!r} "
            f"role={self.role!r}>"
        )

    @property
    def is_manager(self) -> bool:
        return self.role == CompanyRole.MANAGER.value

    @property
    def is_employee(self) -> bool:
        return self.role == CompanyRole.EMPLOYEE.value