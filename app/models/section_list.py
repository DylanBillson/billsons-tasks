from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.section import Section
    from app.models.task import Task


class SectionList(
    Base,
    IntegerPrimaryKeyMixin,
    TimestampMixin,
):
    __tablename__ = "section_lists"

    __table_args__ = (
        UniqueConstraint(
            "section_id",
            "name",
            name="uq_section_lists_section_id_name",
        ),
        CheckConstraint(
            "sort_position >= 0",
            name="sort_position_non_negative",
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

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    sort_position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1000,
        server_default=text("1000"),
        index=True,
    )

    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    section: Mapped["Section"] = relationship(
        back_populates="lists",
        lazy="joined",
    )

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="section_list",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=(
            "Task.sort_position.asc(), "
            "Task.id.asc()"
        ),
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<SectionList "
            f"id={self.id!r} "
            f"section_id={self.section_id!r} "
            f"name={self.name!r} "
            f"sort_position={self.sort_position!r} "
            f"is_archived={self.is_archived!r}>"
        )