from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Sequence

from pydantic import ValidationError

from app.models.task import Task
from app.schemas.task import (
    TaskCreateRequest,
    TaskFilterOptions,
    TaskUpdateRequest,
)
from app.web.forms.common import (
    FormErrors,
    apply_validation_errors,
    format_datetime_local,
    get_integer,
    get_integer_list,
    get_string,
    parse_datetime_local,
)


VALID_TASK_STATES = {
    "all",
    "open",
    "completed",
    "overdue",
    "deleted",
}


@dataclass
class TaskForm:
    section_list_id: str = ""
    title: str = ""
    description: str = ""
    due_at: str = ""
    assignee_user_ids: list[int] = field(
        default_factory=list,
    )

    errors: FormErrors = field(
        default_factory=FormErrors,
    )

    @classmethod
    def from_form_data(
        cls,
        form_data: Mapping[str, object],
        *,
        timezone_name: str = "Europe/London",
    ) -> "TaskForm":
        del timezone_name

        return cls(
            section_list_id=get_string(
                form_data,
                "section_list_id",
            ),
            title=get_string(
                form_data,
                "title",
            ),
            description=get_string(
                form_data,
                "description",
            ),
            due_at=get_string(
                form_data,
                "due_at",
            ),
            assignee_user_ids=get_integer_list(
                form_data,
                "assignee_user_ids",
            ),
        )

    @classmethod
    def from_task(
        cls,
        task: Task,
        *,
        timezone_name: str = "Europe/London",
    ) -> "TaskForm":
        return cls(
            section_list_id=str(
                task.section_list_id,
            ),
            title=task.title,
            description=task.description or "",
            due_at=format_datetime_local(
                task.due_at,
                timezone_name=timezone_name,
            ),
            assignee_user_ids=[
                assignment.user_id
                for assignment in task.assignees
            ],
        )

    def validate_create(
        self,
        *,
        timezone_name: str = "Europe/London",
    ) -> TaskCreateRequest | None:
        self.errors = FormErrors()

        section_list_id = self._parse_section_list_id()

        due_at = self._parse_due_at(
            timezone_name=timezone_name,
        )

        if self.errors.has_errors:
            return None

        try:
            request = TaskCreateRequest(
                section_list_id=section_list_id,
                title=self.title,
                description=self.description,
                due_at=due_at,
                assignee_user_ids=(
                    self.assignee_user_ids
                ),
            )

        except ValidationError as exc:
            apply_validation_errors(
                errors=self.errors,
                exception=exc,
            )

            return None

        self._apply_create_values(
            request,
            timezone_name=timezone_name,
        )

        return request

    def validate_update(
        self,
        *,
        timezone_name: str = "Europe/London",
    ) -> TaskUpdateRequest | None:
        self.errors = FormErrors()

        due_at = self._parse_due_at(
            timezone_name=timezone_name,
        )

        if self.errors.has_errors:
            return None

        try:
            request = TaskUpdateRequest(
                title=self.title,
                description=self.description,
                due_at=due_at,
            )

        except ValidationError as exc:
            apply_validation_errors(
                errors=self.errors,
                exception=exc,
            )

            return None

        self._apply_update_values(
            request,
            timezone_name=timezone_name,
        )

        return request

    def _parse_section_list_id(
        self,
    ) -> int:
        section_list_id = get_integer(
            {
                "section_list_id": self.section_list_id,
            },
            "section_list_id",
        )

        if section_list_id is None:
            self.errors.add_field_error(
                "section_list_id",
                "Please select a list.",
            )

            return 0

        if section_list_id <= 0:
            self.errors.add_field_error(
                "section_list_id",
                "Please select a valid list.",
            )

            return 0

        return section_list_id

    def _parse_due_at(
        self,
        *,
        timezone_name: str,
    ) -> datetime | None:
        if not self.due_at.strip():
            return None

        try:
            return parse_datetime_local(
                self.due_at,
                timezone_name=timezone_name,
            )

        except ValueError as exc:
            self.errors.add_field_error(
                "due_at",
                str(exc),
            )

            return None

    def _apply_create_values(
        self,
        request: TaskCreateRequest,
        *,
        timezone_name: str,
    ) -> None:
        self.section_list_id = str(
            request.section_list_id,
        )
        self.title = request.title
        self.description = request.description or ""
        self.due_at = format_datetime_local(
            request.due_at,
            timezone_name=timezone_name,
        )
        self.assignee_user_ids = list(
            request.assignee_user_ids,
        )

    def _apply_update_values(
        self,
        request: TaskUpdateRequest,
        *,
        timezone_name: str,
    ) -> None:
        self.title = request.title
        self.description = request.description or ""
        self.due_at = format_datetime_local(
            request.due_at,
            timezone_name=timezone_name,
        )


@dataclass
class TaskFilterForm:
    state: str = "all"
    section_list_id: str = ""
    assignee_user_id: str = ""
    search: str = ""
    due_from: str = ""
    due_to: str = ""

    errors: FormErrors = field(
        default_factory=FormErrors,
    )

    @classmethod
    def from_query_params(
        cls,
        query_params: Mapping[str, object],
    ) -> "TaskFilterForm":
        return cls(
            state=get_string(
                query_params,
                "state",
            )
            or "all",
            section_list_id=get_string(
                query_params,
                "section_list_id",
            ),
            assignee_user_id=get_string(
                query_params,
                "assignee_user_id",
            ),
            search=get_string(
                query_params,
                "search",
            ),
            due_from=get_string(
                query_params,
                "due_from",
            ),
            due_to=get_string(
                query_params,
                "due_to",
            ),
        )

    def validate(
        self,
        *,
        timezone_name: str = "Europe/London",
    ) -> TaskFilterOptions | None:
        self.errors = FormErrors()

        state = self.state.strip().lower() or "all"

        if state not in VALID_TASK_STATES:
            self.errors.add_field_error(
                "state",
                "Please select a valid task state.",
            )

        section_list_id = self._parse_optional_positive_id(
            field_name="section_list_id",
            value=self.section_list_id,
            message="Please select a valid list.",
        )

        assignee_user_id = self._parse_optional_positive_id(
            field_name="assignee_user_id",
            value=self.assignee_user_id,
            message="Please select a valid assignee.",
        )

        due_from = self._parse_optional_datetime(
            field_name="due_from",
            value=self.due_from,
            timezone_name=timezone_name,
        )

        due_to = self._parse_optional_datetime(
            field_name="due_to",
            value=self.due_to,
            timezone_name=timezone_name,
        )

        if self.errors.has_errors:
            return None

        try:
            filters = TaskFilterOptions(
                state=state,
                section_list_id=section_list_id,
                assignee_user_id=assignee_user_id,
                search=self.search,
                due_from=due_from,
                due_to=due_to,
            )

        except ValidationError as exc:
            apply_validation_errors(
                errors=self.errors,
                exception=exc,
            )

            return None

        self.state = filters.state
        self.section_list_id = (
            str(filters.section_list_id)
            if filters.section_list_id is not None
            else ""
        )
        self.assignee_user_id = (
            str(filters.assignee_user_id)
            if filters.assignee_user_id is not None
            else ""
        )
        self.search = filters.search or ""
        self.due_from = format_datetime_local(
            filters.due_from,
            timezone_name=timezone_name,
        )
        self.due_to = format_datetime_local(
            filters.due_to,
            timezone_name=timezone_name,
        )

        return filters

    @property
    def is_active(
        self,
    ) -> bool:
        return any(
            (
                self.state != "all",
                bool(self.section_list_id),
                bool(self.assignee_user_id),
                bool(self.search),
                bool(self.due_from),
                bool(self.due_to),
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

    def _parse_optional_datetime(
        self,
        *,
        field_name: str,
        value: str,
        timezone_name: str,
    ) -> datetime | None:
        if not value.strip():
            return None

        try:
            return parse_datetime_local(
                value,
                timezone_name=timezone_name,
            )

        except ValueError as exc:
            self.errors.add_field_error(
                field_name,
                str(exc),
            )

            return None


def normalise_selected_ids(
    values: Sequence[int],
) -> list[int]:
    return list(
        dict.fromkeys(
            value
            for value in values
            if value > 0
        ),
    )