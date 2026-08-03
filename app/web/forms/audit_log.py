from dataclasses import dataclass, field
from datetime import (
    date,
    datetime,
    time,
    timedelta,
    timezone,
)
from typing import Mapping
from zoneinfo import (
    ZoneInfo,
    ZoneInfoNotFoundError,
)

from app.schemas.audit_log import (
    AuditLogFilterOptions,
)
from app.web.forms.common import FormErrors


DEFAULT_AUDIT_PAGE_SIZE = 25
MAX_AUDIT_PAGE_SIZE = 100


@dataclass
class AuditLogFilterForm:
    search: str = ""
    user_id: str = ""
    action: str = ""
    entity_type: str = ""
    entity_id: str = ""

    created_from: str = ""
    created_to: str = ""

    page: str = "1"
    page_size: str = str(
        DEFAULT_AUDIT_PAGE_SIZE,
    )

    errors: FormErrors = field(
        default_factory=FormErrors,
    )

    @classmethod
    def from_query_params(
        cls,
        query_params: Mapping[str, object],
    ) -> "AuditLogFilterForm":
        return cls(
            search=cls._get_string(
                query_params,
                "search",
            ),
            user_id=cls._get_string(
                query_params,
                "user_id",
            ),
            action=cls._get_string(
                query_params,
                "action",
            ),
            entity_type=cls._get_string(
                query_params,
                "entity_type",
            ),
            entity_id=cls._get_string(
                query_params,
                "entity_id",
            ),
            created_from=cls._get_string(
                query_params,
                "created_from",
            ),
            created_to=cls._get_string(
                query_params,
                "created_to",
            ),
            page=(
                cls._get_string(
                    query_params,
                    "page",
                )
                or "1"
            ),
            page_size=(
                cls._get_string(
                    query_params,
                    "page_size",
                )
                or str(
                    DEFAULT_AUDIT_PAGE_SIZE,
                )
            ),
        )

    def validate(
        self,
        *,
        timezone_name: str,
    ) -> AuditLogFilterOptions | None:
        self.errors = FormErrors()

        try:
            local_timezone = ZoneInfo(
                timezone_name,
            )

        except ZoneInfoNotFoundError:
            self.errors.add_form_error(
                "The configured application timezone is invalid.",
            )

            return None

        user_id = self._parse_optional_id(
            field_name="user_id",
            value=self.user_id,
            message="Please select a valid user.",
        )

        entity_id = self._parse_optional_id(
            field_name="entity_id",
            value=self.entity_id,
            message="Please enter a valid entity ID.",
        )

        page = self._parse_positive_integer(
            field_name="page",
            value=self.page,
            default=1,
            maximum=None,
            message="Please enter a valid page number.",
        )

        page_size = self._parse_positive_integer(
            field_name="page_size",
            value=self.page_size,
            default=DEFAULT_AUDIT_PAGE_SIZE,
            maximum=MAX_AUDIT_PAGE_SIZE,
            message=(
                "Results per page must be between "
                f"1 and {MAX_AUDIT_PAGE_SIZE}."
            ),
        )

        created_from_date = self._parse_optional_date(
            field_name="created_from",
            value=self.created_from,
            message="Please enter a valid start date.",
        )

        created_to_date = self._parse_optional_date(
            field_name="created_to",
            value=self.created_to,
            message="Please enter a valid end date.",
        )

        if (
            created_from_date is not None
            and created_to_date is not None
            and created_from_date
            > created_to_date
        ):
            self.errors.add_field_error(
                "created_to",
                (
                    "The end date must be on or "
                    "after the start date."
                ),
            )

        if self.errors.has_errors:
            return None

        created_from = (
            datetime.combine(
                created_from_date,
                time.min,
                tzinfo=local_timezone,
            ).astimezone(
                timezone.utc,
            )
            if created_from_date is not None
            else None
        )

        created_to = (
            datetime.combine(
                created_to_date
                + timedelta(
                    days=1,
                ),
                time.min,
                tzinfo=local_timezone,
            ).astimezone(
                timezone.utc,
            )
            if created_to_date is not None
            else None
        )

        self.search = self.search.strip()
        self.action = self.action.strip()
        self.entity_type = (
            self.entity_type.strip()
        )

        self.user_id = (
            str(
                user_id,
            )
            if user_id is not None
            else ""
        )

        self.entity_id = (
            str(
                entity_id,
            )
            if entity_id is not None
            else ""
        )

        self.page = str(
            page,
        )

        self.page_size = str(
            page_size,
        )

        try:
            return AuditLogFilterOptions(
                search=self.search or None,
                user_id=user_id,
                action=self.action or None,
                entity_type=(
                    self.entity_type
                    or None
                ),
                entity_id=entity_id,
                created_from=created_from,
                created_to=created_to,
                page=page,
                page_size=page_size,
            )

        except ValueError as exc:
            self.errors.add_form_error(
                str(
                    exc,
                ),
            )

            return None

    @property
    def is_active(
        self,
    ) -> bool:
        return any(
            (
                bool(
                    self.search,
                ),
                bool(
                    self.user_id,
                ),
                bool(
                    self.action,
                ),
                bool(
                    self.entity_type,
                ),
                bool(
                    self.entity_id,
                ),
                bool(
                    self.created_from,
                ),
                bool(
                    self.created_to,
                ),
            ),
        )

    @staticmethod
    def _get_string(
        values: Mapping[str, object],
        key: str,
    ) -> str:
        value = values.get(
            key,
            "",
        )

        if value is None:
            return ""

        return str(
            value,
        ).strip()

    def _parse_optional_id(
        self,
        *,
        field_name: str,
        value: str,
        message: str,
    ) -> int | None:
        if not value.strip():
            return None

        try:
            parsed = int(
                value,
            )

        except ValueError:
            parsed = 0

        if parsed < 1:
            self.errors.add_field_error(
                field_name,
                message,
            )

            return None

        return parsed

    def _parse_positive_integer(
        self,
        *,
        field_name: str,
        value: str,
        default: int,
        maximum: int | None,
        message: str,
    ) -> int:
        if not value.strip():
            return default

        try:
            parsed = int(
                value,
            )

        except ValueError:
            parsed = 0

        if (
            parsed < 1
            or (
                maximum is not None
                and parsed > maximum
            )
        ):
            self.errors.add_field_error(
                field_name,
                message,
            )

            return default

        return parsed

    def _parse_optional_date(
        self,
        *,
        field_name: str,
        value: str,
        message: str,
    ) -> date | None:
        if not value.strip():
            return None

        try:
            return date.fromisoformat(
                value,
            )

        except ValueError:
            self.errors.add_field_error(
                field_name,
                message,
            )

            return None