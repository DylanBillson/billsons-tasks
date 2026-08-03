from dataclasses import dataclass, field
from typing import Mapping

from pydantic import ValidationError

from app.schemas.my_tasks import (
    MyTasksFilterOptions,
)
from app.web.forms.common import (
    FormErrors,
    apply_validation_errors,
    get_integer,
    get_string,
)


VALID_MY_TASK_STATES = {
    "all",
    "open",
    "overdue",
    "due_today",
    "due_soon",
    "completed",
}


@dataclass
class MyTasksFilterForm:
    state: str = "open"
    company_id: str = ""
    section_id: str = ""
    search: str = ""

    errors: FormErrors = field(
        default_factory=FormErrors,
    )

    @classmethod
    def from_query_params(
        cls,
        query_params: Mapping[str, object],
    ) -> "MyTasksFilterForm":
        return cls(
            state=(
                get_string(
                    query_params,
                    "state",
                )
                or "open"
            ),
            company_id=get_string(
                query_params,
                "company_id",
            ),
            section_id=get_string(
                query_params,
                "section_id",
            ),
            search=get_string(
                query_params,
                "search",
            ),
        )

    def validate(
        self,
    ) -> MyTasksFilterOptions | None:
        self.errors = FormErrors()

        state = (
            self.state.strip().lower()
            or "open"
        )

        if state not in VALID_MY_TASK_STATES:
            self.errors.add_field_error(
                "state",
                "Please select a valid task state.",
            )

        company_id = self._parse_optional_positive_id(
            field_name="company_id",
            value=self.company_id,
            message="Please select a valid company.",
        )

        section_id = self._parse_optional_positive_id(
            field_name="section_id",
            value=self.section_id,
            message="Please select a valid section.",
        )

        if self.errors.has_errors:
            return None

        try:
            filters = MyTasksFilterOptions(
                state=state,
                company_id=company_id,
                section_id=section_id,
                search=self.search,
            )

        except ValidationError as exc:
            apply_validation_errors(
                errors=self.errors,
                exception=exc,
            )

            return None

        self.state = filters.state

        self.company_id = (
            str(
                filters.company_id,
            )
            if filters.company_id is not None
            else ""
        )

        self.section_id = (
            str(
                filters.section_id,
            )
            if filters.section_id is not None
            else ""
        )

        self.search = filters.search or ""

        return filters

    @property
    def is_active(
        self,
    ) -> bool:
        return any(
            (
                self.state != "open",
                bool(
                    self.company_id,
                ),
                bool(
                    self.section_id,
                ),
                bool(
                    self.search,
                ),
            ),
        )

    def _parse_optional_positive_id(
        self,
        *,
        field_name: str,
        value: str,
        message: str,
    ) -> int | None:
        if not value.strip():
            return None

        parsed = get_integer(
            {
                field_name: value,
            },
            field_name,
        )

        if parsed is None or parsed <= 0:
            self.errors.add_field_error(
                field_name,
                message,
            )

            return None

        return parsed