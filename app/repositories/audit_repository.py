from datetime import datetime
from typing import Any

from sqlalchemy import (
    Select,
    func,
    or_,
    select,
)
from sqlalchemy.orm import (
    Session,
    joinedload,
)

from app.models.audit_log import AuditLog
from app.models.user import User


class AuditRepository:
    @staticmethod
    def get_by_id(
        db: Session,
        audit_log_id: int,
    ) -> AuditLog | None:
        query = (
            select(
                AuditLog,
            )
            .options(
                joinedload(
                    AuditLog.user,
                ),
            )
            .where(
                AuditLog.id == audit_log_id,
            )
        )

        return db.scalar(
            query,
        )

    @staticmethod
    def create(
        db: Session,
        *,
        action: str,
        summary: str,
        user_id: int | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        metadata_json: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary,
            metadata_json=metadata_json or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        db.add(
            audit_log,
        )
        db.flush()

        return audit_log

    @staticmethod
    def list_logs(
        db: Session,
        *,
        search: str | None = None,
        user_id: int | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        query = AuditRepository._build_filtered_query(
            search=search,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            created_from=created_from,
            created_to=created_to,
        )

        query = (
            query
            .options(
                joinedload(
                    AuditLog.user,
                ),
            )
            .order_by(
                AuditLog.created_at.desc(),
                AuditLog.id.desc(),
            )
            .limit(
                limit,
            )
            .offset(
                offset,
            )
        )

        return list(
            db.scalars(
                query,
            ).unique().all(),
        )

    @staticmethod
    def count_logs(
        db: Session,
        *,
        search: str | None = None,
        user_id: int | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> int:
        filtered_query = (
            AuditRepository._build_filtered_query(
                search=search,
                user_id=user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                created_from=created_from,
                created_to=created_to,
            )
        )

        count_query = select(
            func.count(),
        ).select_from(
            filtered_query
            .order_by(
                None,
            )
            .subquery(),
        )

        return int(
            db.scalar(
                count_query,
            )
            or 0,
        )

    @staticmethod
    def list_for_entity(
        db: Session,
        *,
        entity_type: str,
        entity_id: int,
        limit: int = 100,
    ) -> list[AuditLog]:
        query = (
            select(
                AuditLog,
            )
            .options(
                joinedload(
                    AuditLog.user,
                ),
            )
            .where(
                AuditLog.entity_type == entity_type,
                AuditLog.entity_id == entity_id,
            )
            .order_by(
                AuditLog.created_at.desc(),
                AuditLog.id.desc(),
            )
            .limit(
                limit,
            )
        )

        return list(
            db.scalars(
                query,
            ).unique().all(),
        )

    @staticmethod
    def list_actions(
        db: Session,
    ) -> list[str]:
        query = (
            select(
                AuditLog.action,
            )
            .where(
                AuditLog.action.is_not(None),
                AuditLog.action != "",
            )
            .distinct()
            .order_by(
                AuditLog.action.asc(),
            )
        )

        return list(
            db.scalars(
                query,
            ).all(),
        )

    @staticmethod
    def list_entity_types(
        db: Session,
    ) -> list[str]:
        query = (
            select(
                AuditLog.entity_type,
            )
            .where(
                AuditLog.entity_type.is_not(None),
                AuditLog.entity_type != "",
            )
            .distinct()
            .order_by(
                AuditLog.entity_type.asc(),
            )
        )

        return [
            entity_type
            for entity_type in db.scalars(
                query,
            ).all()
            if entity_type is not None
        ]

    @staticmethod
    def _build_filtered_query(
        *,
        search: str | None = None,
        user_id: int | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> Select[tuple[AuditLog]]:
        query = (
            select(
                AuditLog,
            )
            .outerjoin(
                User,
                User.id == AuditLog.user_id,
            )
        )

        if search is not None:
            pattern = (
                f"%{search.strip()}%"
            )

            query = query.where(
                or_(
                    AuditLog.summary.ilike(
                        pattern,
                    ),
                    AuditLog.action.ilike(
                        pattern,
                    ),
                    AuditLog.entity_type.ilike(
                        pattern,
                    ),
                    AuditLog.ip_address.ilike(
                        pattern,
                    ),
                    User.username.ilike(
                        pattern,
                    ),
                    User.display_name.ilike(
                        pattern,
                    ),
                ),
            )

        if user_id is not None:
            query = query.where(
                AuditLog.user_id == user_id,
            )

        if action is not None:
            query = query.where(
                AuditLog.action == action,
            )

        if entity_type is not None:
            query = query.where(
                AuditLog.entity_type == entity_type,
            )

        if entity_id is not None:
            query = query.where(
                AuditLog.entity_id == entity_id,
            )

        if created_from is not None:
            query = query.where(
                AuditLog.created_at >= created_from,
            )

        if created_to is not None:
            query = query.where(
                AuditLog.created_at < created_to,
            )

        return query