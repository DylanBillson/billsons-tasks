from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


class AuditRepository:
    @staticmethod
    def get_by_id(
        db: Session,
        audit_log_id: int,
    ) -> AuditLog | None:
        return db.get(
            AuditLog,
            audit_log_id,
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

        db.add(audit_log)
        db.flush()

        return audit_log

    @staticmethod
    def list_logs(
        db: Session,
        *,
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
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            created_from=created_from,
            created_to=created_to,
        )

        query = (
            query.order_by(
                AuditLog.created_at.desc(),
                AuditLog.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        return list(
            db.scalars(query).all(),
        )

    @staticmethod
    def count_logs(
        db: Session,
        *,
        user_id: int | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> int:
        filtered_query = AuditRepository._build_filtered_query(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            created_from=created_from,
            created_to=created_to,
        )

        count_query = select(
            func.count(),
        ).select_from(
            filtered_query.order_by(None).subquery(),
        )

        return int(
            db.scalar(count_query) or 0,
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
            select(AuditLog)
            .where(
                AuditLog.entity_type == entity_type,
                AuditLog.entity_id == entity_id,
            )
            .order_by(
                AuditLog.created_at.desc(),
                AuditLog.id.desc(),
            )
            .limit(limit)
        )

        return list(
            db.scalars(query).all(),
        )

    @staticmethod
    def _build_filtered_query(
        *,
        user_id: int | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> Select[tuple[AuditLog]]:
        query = select(AuditLog)

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
                AuditLog.created_at <= created_to,
            )

        return query