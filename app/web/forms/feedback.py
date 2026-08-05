from dataclasses import dataclass, field
from typing import Mapping

from pydantic import ValidationError

from app.schemas.feedback import (
    FeedbackSubmission,
)
from app.web.forms.common import (
    FormErrors,
    get_string,
)


@dataclass
class FeedbackForm:
    message: str = ""
    page_url: str = ""

    errors: FormErrors = field(
        default_factory=FormErrors,
    )

    @classmethod
    def from_form_data(
        cls,
        form_data: Mapping[str, object],
    ) -> "FeedbackForm":
        return cls(
            message=get_string(
                form_data,
                "message",
            ),
            page_url=get_string(
                form_data,
                "page_url",
            ),
        )

    def validate(
        self,
    ) -> FeedbackSubmission | None:
        self.errors = FormErrors()

        try:
            submission = FeedbackSubmission(
                message=self.message,
                page_url=self.page_url,
            )

        except ValidationError as exc:
            for error in exc.errors():
                location = error.get(
                    "loc",
                    (),
                )

                field_name = (
                    str(
                        location[0],
                    )
                    if location
                    else None
                )

                message = self._message_for_error(
                    field_name=field_name,
                    error_type=str(
                        error.get(
                            "type",
                            "",
                        ),
                    ),
                )

                if field_name in {
                    "message",
                    "page_url",
                }:
                    self.errors.add_field_error(
                        field_name,
                        message,
                    )

                else:
                    self.errors.add_form_error(
                        message,
                    )

            return None

        self.message = submission.message
        self.page_url = submission.page_url

        return submission

    @staticmethod
    def _message_for_error(
        *,
        field_name: str | None,
        error_type: str,
    ) -> str:
        if field_name == "message":
            if error_type == "string_too_long":
                return (
                    "Feedback must be 5,000 characters "
                    "or fewer."
                )

            return "Please enter a feedback message."

        if field_name == "page_url":
            if error_type == "string_too_long":
                return "The page address is too long."

            return (
                "The page you were viewing could not "
                "be identified."
            )

        return (
            "The feedback form contains invalid "
            "information."
        )