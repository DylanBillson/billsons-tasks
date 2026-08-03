from datetime import datetime
from math import ceil
from typing import Any

from sqlalchemy.orm import Session

from app.core.constants import AuditAction
from app.models.audit_log import AuditLog
from app.models.user import User
from app.repositories.audit_repository import AuditRepository
from app.schemas.audit_log import (
    AuditLogDetail,
    AuditLogFilterChoices,
    AuditLogFilterOptions,
    AuditLogPage,
    AuditLogSummary,
    AuditLogUserSummary,
)


class AuditServiceError(ValueError):
    """Base exception for audit-service failures."""


class AuditLogNotFoundError(LookupError):
    """Raised when an audit log entry cannot be found."""


class AuditLogPermissionError(AuditServiceError):
    """Raised when a user cannot access audit information."""


class AuditLogFilterError(AuditServiceError):
    """Raised when audit-log filters are invalid."""


class AuditService:
    @staticmethod
    def record(
        db: Session,
        *,
        action: str | AuditAction,
        summary: str,
        user: User | None = None,
        user_id: int | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        metadata_json: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = False,
    ) -> AuditLog:
        """
        Create an audit log entry.

        The caller controls whether the transaction is committed, allowing
        audit entries to participate in the same transaction as the action
        they describe.
        """
        resolved_user_id = (
            user.id
            if user is not None
            else user_id
        )

        audit_log = AuditRepository.create(
            db,
            action=AuditService.normalise_action(
                action,
            ),
            summary=AuditService.normalise_summary(
                summary,
            ),
            user_id=resolved_user_id,
            entity_type=(
                AuditService.normalise_optional_string(
                    entity_type,
                )
            ),
            entity_id=entity_id,
            metadata_json=AuditService.sanitise_metadata(
                metadata_json or {},
            ),
            ip_address=AuditService.normalise_ip_address(
                ip_address,
            ),
            user_agent=AuditService.normalise_user_agent(
                user_agent,
            ),
        )

        if commit:
            db.commit()
            db.refresh(
                audit_log,
            )

        return audit_log

    @staticmethod
    def record_system_event(
        db: Session,
        *,
        action: str | AuditAction,
        summary: str,
        entity_type: str | None = None,
        entity_id: int | None = None,
        metadata_json: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = False,
    ) -> AuditLog:
        return AuditService.record(
            db,
            action=action,
            summary=summary,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=metadata_json,
            ip_address=ip_address,
            user_agent=user_agent,
            commit=commit,
        )

    @staticmethod
    def get_log(
        db: Session,
        *,
        audit_log_id: int,
    ) -> AuditLog | None:
        return AuditRepository.get_by_id(
            db,
            audit_log_id,
        )

    @staticmethod
    def require_log(
        db: Session,
        *,
        audit_log_id: int,
    ) -> AuditLog:
        audit_log = AuditService.get_log(
            db,
            audit_log_id=audit_log_id,
        )

        if audit_log is None:
            raise AuditLogNotFoundError(
                f"Audit log '{audit_log_id}' was not found.",
            )

        return audit_log

    @staticmethod
    def get_log_detail(
        db: Session,
        *,
        actor: User,
        audit_log_id: int,
    ) -> AuditLogDetail:
        AuditService.require_administrator(
            actor,
        )

        audit_log = AuditService.require_log(
            db,
            audit_log_id=audit_log_id,
        )

        return AuditService.build_detail(
            audit_log,
        )

    @staticmethod
    def get_log_page(
        db: Session,
        *,
        actor: User,
        filters: AuditLogFilterOptions | None = None,
    ) -> AuditLogPage:
        AuditService.require_administrator(
            actor,
        )

        resolved_filters = (
            filters
            if filters is not None
            else AuditLogFilterOptions()
        )

        if (
            resolved_filters.created_from is not None
            and resolved_filters.created_to is not None
            and resolved_filters.created_from
            >= resolved_filters.created_to
        ):
            raise AuditLogFilterError(
                "The start date must be before the end date.",
            )

        total_items = AuditRepository.count_logs(
            db,
            search=resolved_filters.search,
            user_id=resolved_filters.user_id,
            action=resolved_filters.action,
            entity_type=resolved_filters.entity_type,
            entity_id=resolved_filters.entity_id,
            created_from=resolved_filters.created_from,
            created_to=resolved_filters.created_to,
        )

        total_pages = max(
            1,
            ceil(
                total_items
                / resolved_filters.page_size,
            ),
        )

        logs = AuditRepository.list_logs(
            db,
            search=resolved_filters.search,
            user_id=resolved_filters.user_id,
            action=resolved_filters.action,
            entity_type=resolved_filters.entity_type,
            entity_id=resolved_filters.entity_id,
            created_from=resolved_filters.created_from,
            created_to=resolved_filters.created_to,
            limit=resolved_filters.page_size,
            offset=(
                resolved_filters.page - 1
            )
            * resolved_filters.page_size,
        )

        return AuditLogPage(
            filters=resolved_filters,
            logs=[
                AuditService.build_summary(
                    audit_log,
                )
                for audit_log in logs
            ],
            total_items=total_items,
            total_pages=total_pages,
            current_page=resolved_filters.page,
            page_size=resolved_filters.page_size,
        )

    @staticmethod
    def get_filter_choices(
        db: Session,
        *,
        actor: User,
    ) -> AuditLogFilterChoices:
        AuditService.require_administrator(
            actor,
        )

        return AuditLogFilterChoices(
            actions=AuditRepository.list_actions(
                db,
            ),
            entity_types=(
                AuditRepository.list_entity_types(
                    db,
                )
            ),
        )

    @staticmethod
    def list_logs(
        db: Session,
        *,
        user_id: int | None = None,
        action: str | AuditAction | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        return AuditRepository.list_logs(
            db,
            search=AuditService.normalise_optional_string(
                search,
            ),
            user_id=user_id,
            action=(
                AuditService.normalise_action(
                    action,
                )
                if action is not None
                else None
            ),
            entity_type=(
                AuditService.normalise_optional_string(
                    entity_type,
                )
            ),
            entity_id=entity_id,
            created_from=created_from,
            created_to=created_to,
            limit=AuditService.normalise_limit(
                limit,
            ),
            offset=AuditService.normalise_offset(
                offset,
            ),
        )

    @staticmethod
    def count_logs(
        db: Session,
        *,
        user_id: int | None = None,
        action: str | AuditAction | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        search: str | None = None,
    ) -> int:
        return AuditRepository.count_logs(
            db,
            search=AuditService.normalise_optional_string(
                search,
            ),
            user_id=user_id,
            action=(
                AuditService.normalise_action(
                    action,
                )
                if action is not None
                else None
            ),
            entity_type=(
                AuditService.normalise_optional_string(
                    entity_type,
                )
            ),
            entity_id=entity_id,
            created_from=created_from,
            created_to=created_to,
        )

    @staticmethod
    def list_for_entity(
        db: Session,
        *,
        entity_type: str,
        entity_id: int,
        limit: int = 100,
    ) -> list[AuditLog]:
        return AuditRepository.list_for_entity(
            db,
            entity_type=(
                AuditService.normalise_required_string(
                    entity_type,
                    field_name="entity_type",
                )
            ),
            entity_id=entity_id,
            limit=AuditService.normalise_limit(
                limit,
            ),
        )

    @staticmethod
    def build_summary(
        audit_log: AuditLog,
    ) -> AuditLogSummary:
        return AuditLogSummary(
            id=audit_log.id,
            action=audit_log.action,
            summary=audit_log.summary,
            user=(
                AuditService.build_user_summary(
                    audit_log.user,
                )
                if audit_log.user is not None
                else None
            ),
            entity_type=audit_log.entity_type,
            entity_id=audit_log.entity_id,
            ip_address=audit_log.ip_address,
            user_agent=audit_log.user_agent,
            created_at=audit_log.created_at,
        )

    @staticmethod
    def build_detail(
        audit_log: AuditLog,
    ) -> AuditLogDetail:
        summary = AuditService.build_summary(
            audit_log,
        )

        return AuditLogDetail(
            **summary.model_dump(),
            metadata_json=(
                audit_log.metadata_json
                or {}
            ),
        )

    @staticmethod
    def build_user_summary(
        user: User,
    ) -> AuditLogUserSummary:
        return AuditLogUserSummary(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            is_active=user.is_active,
            is_anonymised=user.is_anonymised,
        )

    @staticmethod
    def require_administrator(
        actor: User,
    ) -> None:
        if not actor.is_administrator:
            raise AuditLogPermissionError(
                "Administrator access is required.",
            )

        if not actor.can_authenticate:
            raise AuditLogPermissionError(
                "The administrator account is not available.",
            )

    @staticmethod
    def sanitise_metadata(
        metadata_json: dict[str, Any],
    ) -> dict[str, Any]:
        sensitive_keys = {
            "password",
            "password_hash",
            "new_password",
            "current_password",
            "confirm_password",
            "session_token",
            "session_token_hash",
            "csrf_token",
            "csrf_token_hash",
            "login_csrf_token",
            "token",
            "token_hash",
            "access_token",
            "refresh_token",
            "authorization",
            "cookie",
            "set_cookie",
            "secret",
            "secret_key",
            "app_secret_key",
            "app_encryption_key",
            "postgres_password",
            "database_url",
            "credentials",
            "comment_content",
            "deleted_comment_content",
        }

        def sanitise_value(
            value: Any,
        ) -> Any:
            if isinstance(
                value,
                dict,
            ):
                cleaned: dict[str, Any] = {}

                for key, nested_value in value.items():
                    key_string = str(
                        key,
                    )

                    if (
                        key_string.casefold()
                        in sensitive_keys
                    ):
                        cleaned[key_string] = (
                            "[REDACTED]"
                        )
                    else:
                        cleaned[key_string] = (
                            sanitise_value(
                                nested_value,
                            )
                        )

                return cleaned

            if isinstance(
                value,
                list | tuple | set,
            ):
                return [
                    sanitise_value(
                        item,
                    )
                    for item in value
                ]

            if isinstance(
                value,
                datetime,
            ):
                return value.isoformat()

            if isinstance(
                value,
                AuditAction,
            ):
                return value.value

            if isinstance(
                value,
                User,
            ):
                return {
                    "id": value.id,
                    "display_name": (
                        value.display_name
                    ),
                }

            if (
                value is None
                or isinstance(
                    value,
                    str | int | float | bool,
                )
            ):
                return value

            return str(
                value,
            )

        sanitised = sanitise_value(
            metadata_json,
        )

        return dict(
            sanitised,
        )

    @staticmethod
    def normalise_action(
        action: str | AuditAction,
    ) -> str:
        if isinstance(
            action,
            AuditAction,
        ):
            return action.value

        return (
            AuditService.normalise_required_string(
                action,
                field_name="action",
            )
        )

    @staticmethod
    def normalise_summary(
        summary: str,
    ) -> str:
        return (
            AuditService.normalise_required_string(
                summary,
                field_name="summary",
            )
        )

    @staticmethod
    def normalise_required_string(
        value: str,
        *,
        field_name: str,
    ) -> str:
        normalised = value.strip()

        if not normalised:
            raise ValueError(
                f"{field_name} cannot be empty.",
            )

        return normalised

    @staticmethod
    def normalise_optional_string(
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        normalised = value.strip()

        return normalised or None

    @staticmethod
    def normalise_ip_address(
        ip_address: str | None,
    ) -> str | None:
        if ip_address is None:
            return None

        value = ip_address.strip()

        return value[:45] or None

    @staticmethod
    def normalise_user_agent(
        user_agent: str | None,
    ) -> str | None:
        if user_agent is None:
            return None

        value = user_agent.strip()

        return value or None

    @staticmethod
    def normalise_limit(
        limit: int,
    ) -> int:
        return max(
            1,
            min(
                limit,
                500,
            ),
        )

    @staticmethod
    def normalise_offset(
        offset: int,
    ) -> int:
        return max(
            offset,
            0,
        )