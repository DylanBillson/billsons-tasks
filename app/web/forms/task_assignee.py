from dataclasses import dataclass, field
from typing import Mapping

from pydantic import ValidationError

from app.models.task import Task
from app.schemas.task_assignee import (
    TaskAssigneeCreateRequest,
    TaskAssigneeReplaceRequest,
)
from app.web.forms.common import (
    FormErrors,
    apply_validation_errors,
    get_integer,
    get_integer_list,
    get_string,
)


@dataclass
class TaskAssigneeCreateForm:
    user_id: str = ""

    errors: FormErrors = field(
        default_factory=FormErrors,
    )

    @classmethod
    def from_form_data(
        cls,
        form_data: Mapping[str, object],
    ) -> "TaskAssigneeCreateForm":
        return cls(
            user_id=get_string(
                form_data,
                "user_id",
            ),
        )

    def validate(
        self,
    ) -> TaskAssigneeCreateRequest | None:
        self.errors = FormErrors()

        user_id = get_integer(
            {
                "user_id": self.user_id,
            },
            "user_id",
        )

        if user_id is None:
            self.errors.add_field_error(
                "user_id",
                "Please select a user.",
            )

            return None

        try:
            request = TaskAssigneeCreateRequest(
                user_id=user_id,
            )

        except ValidationError as exc:
            apply_validation_errors(
                errors=self.errors,
                exception=exc,
            )

            return None

        self.user_id = str(
            request.user_id,
        )

        return request


@dataclass
class TaskAssigneeReplaceForm:
    user_ids: list[int] = field(
        default_factory=list,
    )

    errors: FormErrors = field(
        default_factory=FormErrors,
    )

    @classmethod
    def from_form_data(
        cls,
        form_data: Mapping[str, object],
    ) -> "TaskAssigneeReplaceForm":
        return cls(
            user_ids=get_integer_list(
                form_data,
                "user_ids",
            ),
        )

    @classmethod
    def from_task(
        cls,
        task: Task,
    ) -> "TaskAssigneeReplaceForm":
        return cls(
            user_ids=[
                assignment.user_id
                for assignment in task.assignees
            ],
        )

    def validate(
        self,
    ) -> TaskAssigneeReplaceRequest | None:
        self.errors = FormErrors()

        try:
            request = TaskAssigneeReplaceRequest(
                user_ids=self.user_ids,
            )

        except ValidationError as exc:
            apply_validation_errors(
                errors=self.errors,
                exception=exc,
            )

            return None

        self.user_ids = list(
            request.user_ids,
        )

        return request