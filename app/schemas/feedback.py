from datetime import datetime

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)


FEEDBACK_MESSAGE_MIN_LENGTH = 1
FEEDBACK_MESSAGE_MAX_LENGTH = 5_000
FEEDBACK_PAGE_URL_MAX_LENGTH = 2_000


class FeedbackSubmission(BaseModel):
    message: str = Field(
        min_length=FEEDBACK_MESSAGE_MIN_LENGTH,
        max_length=FEEDBACK_MESSAGE_MAX_LENGTH,
    )

    page_url: str = Field(
        min_length=1,
        max_length=FEEDBACK_PAGE_URL_MAX_LENGTH,
    )

    @field_validator(
        "message",
        "page_url",
    )
    @classmethod
    def strip_required_values(
        cls,
        value: str,
    ) -> str:
        normalised = value.strip()

        if not normalised:
            raise ValueError(
                "This field is required.",
            )

        return normalised


class FeedbackDeliveryResult(BaseModel):
    issue_number: str = Field(
        pattern=r"^\d{6}$",
    )

    sent_at: datetime
    recipient: str