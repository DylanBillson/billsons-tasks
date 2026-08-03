from dataclasses import dataclass, field
from typing import Mapping

from pydantic import ValidationError

from app.schemas.comment import TaskCommentCreateRequest
from app.web.forms.common import (
    FormErrors,
    apply_validation_errors,
    get_string,
)


@dataclass
class TaskCommentForm:
    body: str = ""

    errors: FormErrors = field(
        default_factory=FormErrors,
    )

    @classmethod
    def from_form_data(
        cls,
        form_data: Mapping[str, object],
    ) -> "TaskCommentForm":
        return cls(
            body=get_string(
                form_data,
                "body",
            ),
        )

    def validate(
        self,
    ) -> TaskCommentCreateRequest | None:
        self.errors = FormErrors()

        try:
            request = TaskCommentCreateRequest(
                body=self.body,
            )

        except ValidationError as exc:
            apply_validation_errors(
                errors=self.errors,
                exception=exc,
            )

            return None

        self.body = request.body

        return request