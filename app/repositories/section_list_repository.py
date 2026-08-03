from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.section import Section
from app.models.section_list import SectionList


class SectionListRepository:
    @staticmethod
    def get_by_id(
        db: Session,
        *,
        section_list_id: int,
    ) -> SectionList | None:
        query = (
            select(SectionList)
            .options(
                joinedload(
                    SectionList.section,
                ).joinedload(
                    Section.company,
                ),
                joinedload(
                    SectionList.section,
                ).joinedload(
                    Section.created_by,
                ),
                selectinload(
                    SectionList.tasks,
                ),
            )
            .where(
                SectionList.id == section_list_id,
            )
        )

        return db.scalar(
            query,
        )

    @staticmethod
    def get_by_section_and_name(
        db: Session,
        *,
        section_id: int,
        name: str,
    ) -> SectionList | None:
        query = (
            select(SectionList)
            .where(
                SectionList.section_id == section_id,
                SectionList.name == name,
            )
        )

        return db.scalar(
            query,
        )

    @staticmethod
    def list_for_section(
        db: Session,
        *,
        section_id: int,
        include_archived: bool = False,
        include_tasks: bool = False,
    ) -> list[SectionList]:
        query = (
            select(SectionList)
            .options(
                joinedload(
                    SectionList.section,
                ),
            )
            .where(
                SectionList.section_id == section_id,
            )
        )

        if include_tasks:
            query = query.options(
                selectinload(
                    SectionList.tasks,
                ),
            )

        if not include_archived:
            query = query.where(
                SectionList.is_archived.is_(False),
            )

        query = query.order_by(
            SectionList.sort_position.asc(),
            SectionList.id.asc(),
        )

        return list(
            db.scalars(
                query,
            ).unique().all(),
        )

    @staticmethod
    def get_max_sort_position(
        db: Session,
        *,
        section_id: int,
    ) -> int | None:
        query = (
            select(
                func.max(
                    SectionList.sort_position,
                ),
            )
            .where(
                SectionList.section_id == section_id,
            )
        )

        result = db.scalar(
            query,
        )

        if result is None:
            return None

        return int(
            result,
        )

    @staticmethod
    def get_next_sort_position(
        db: Session,
        *,
        section_id: int,
        increment: int = 1000,
    ) -> int:
        maximum = SectionListRepository.get_max_sort_position(
            db,
            section_id=section_id,
        )

        if maximum is None:
            return increment

        return maximum + increment

    @staticmethod
    def create(
        db: Session,
        *,
        section_id: int,
        name: str,
        description: str | None = None,
        sort_position: int | None = None,
    ) -> SectionList:
        resolved_sort_position = (
            sort_position
            if sort_position is not None
            else SectionListRepository.get_next_sort_position(
                db,
                section_id=section_id,
            )
        )

        section_list = SectionList(
            section_id=section_id,
            name=name,
            description=description,
            sort_position=resolved_sort_position,
        )

        db.add(
            section_list,
        )
        db.flush()

        return section_list

    @staticmethod
    def update(
        db: Session,
        *,
        section_list: SectionList,
        name: str,
        description: str | None,
    ) -> SectionList:
        section_list.name = name
        section_list.description = description

        db.flush()

        return section_list

    @staticmethod
    def set_archived(
        db: Session,
        *,
        section_list: SectionList,
        is_archived: bool,
    ) -> SectionList:
        section_list.is_archived = is_archived

        db.flush()

        return section_list

    @staticmethod
    def update_sort_position(
        db: Session,
        *,
        section_list: SectionList,
        sort_position: int,
    ) -> SectionList:
        section_list.sort_position = sort_position

        db.flush()

        return section_list

    @staticmethod
    def update_sort_positions(
        db: Session,
        *,
        positions: dict[int, int],
    ) -> None:
        if not positions:
            return

        section_lists = list(
            db.scalars(
                select(SectionList).where(
                    SectionList.id.in_(
                        positions,
                    ),
                ),
            ).all(),
        )

        for section_list in section_lists:
            section_list.sort_position = positions[
                section_list.id
            ]

        db.flush()

    @staticmethod
    def delete(
        db: Session,
        *,
        section_list: SectionList,
    ) -> None:
        db.delete(
            section_list,
        )
        db.flush()