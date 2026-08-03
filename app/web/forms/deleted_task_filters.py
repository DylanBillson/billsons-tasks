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

from app.web.forms.common import FormErrors


DEFAULT_DELETED_TASK_PAGE_SIZE = 25
MAX_DELETED_TASK_PAGE_SIZE = 100


@dataclass(frozen=True)
class DeletedTaskFilters:
    search: str | None = None
    company_id: int | None = None
    section_id: int | None = None
    deleted_by_user_id: int | None = None
    deleted_from: datetime | None = None
    deleted_to: datetime | None = None
    page: int = 1
    page_size: int = DEFAULT_DELETED_TASK_PAGE_SIZE


@dataclass
class DeletedTaskFilterForm:
    search: str = ""
    company_id: str = ""
    section_id: str = ""
    deleted_by_user_id: str = ""
    deleted_from: str = ""
    deleted_to: str = ""
    page: str = "1"
    page_size: str = str(
        DEFAULT_DELETED_TASK_PAGE_SIZE,
    )

    errors: FormErrors = field(
        default_factory=FormErrors,
    )

    @classmethod
    def from_query_params(
        cls,
        query_params: Mapping[str, object],
    ) -> "DeletedTaskFilterForm":
        return cls(
            search=cls._get_string(
                query_params,
                "search",
            ),
            company_id=cls._get_string(
                query_params,
                "company_id",
            ),
            section_id=cls._get_string(
                query_params,
                "section_id",
            ),
            deleted_by_user_id=cls._get_string(
                query_params,
                "deleted_by_user_id",
            ),
            deleted_from=cls._get_string(
                query_params,
                "deleted_from",
            ),
            deleted_to=cls._get_string(
                query_params,
                "deleted_to",
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
                    DEFAULT_DELETED_TASK_PAGE_SIZE,
                )
            ),
        )

    def validate(
        self,
        *,
        timezone_name: str,
    ) -> DeletedTaskFilters | None:
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

        company_id = self._parse_optional_id(
            field_name="company_id",
            value=self.company_id,
            message="Please select a valid company.",
        )

        section_id = self._parse_optional_id(
            field_name="section_id",
            value=self.section_id,
            message="Please select a valid section.",
        )

        deleted_by_user_id = self._parse_optional_id(
            field_name="deleted_by_user_id",
            value=self.deleted_by_user_id,
            message="Please select a valid user.",
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
            default=DEFAULT_DELETED_TASK_PAGE_SIZE,
            maximum=MAX_DELETED_TASK_PAGE_SIZE,
            message=(
                "Results per page must be between "
                f"1 and {MAX_DELETED_TASK_PAGE_SIZE}."
            ),
        )

        deleted_from_date = self._parse_optional_date(
            field_name="deleted_from",
            value=self.deleted_from,
            message="Please enter a valid deletion start date.",
        )

        deleted_to_date = self._parse_optional_date(
            field_name="deleted_to",
            value=self.deleted_to,
            message="Please enter a valid deletion end date.",
        )

        if (
            deleted_from_date is not None
            and deleted_to_date is not None
            and deleted_from_date > deleted_to_date
        ):
            self.errors.add_field_error(
                "deleted_to",
                (
                    "The deletion end date must be on "
                    "or after the start date."
                ),
            )

        if self.errors.has_errors:
            return None

        deleted_from = (
            datetime.combine(
                deleted_from_date,
                time.min,
                tzinfo=local_timezone,
            ).astimezone(
                timezone.utc,
            )
            if deleted_from_date is not None
            else None
        )

        deleted_to = (
            datetime.combine(
                deleted_to_date
                + timedelta(
                    days=1,
                ),
                time.min,
                tzinfo=local_timezone,
            ).astimezone(
                timezone.utc,
            )
            if deleted_to_date is not None
            else None
        )

        normalised_search = (
            self.search.strip()
            or None
        )

        self.search = normalised_search or ""
        self.company_id = (
            str(
                company_id,
            )
            if company_id is not None
            else ""
        )
        self.section_id = (
            str(
                section_id,
            )
            if section_id is not None
            else ""
        )
        self.deleted_by_user_id = (
            str(
                deleted_by_user_id,
            )
            if deleted_by_user_id is not None
            else ""
        )
        self.page = str(
            page,
        )
        self.page_size = str(
            page_size,
        )

        return DeletedTaskFilters(
            search=normalised_search,
            company_id=company_id,
            section_id=section_id,
            deleted_by_user_id=deleted_by_user_id,
            deleted_from=deleted_from,
            deleted_to=deleted_to,
            page=page,
            page_size=page_size,
        )

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
                    self.company_id,
                ),
                bool(
                    self.section_id,
                ),
                bool(
                    self.deleted_by_user_id,
                ),
                bool(
                    self.deleted_from,
                ),
                bool(
                    self.deleted_to,
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