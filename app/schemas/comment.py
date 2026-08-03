from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class TaskCommentCreateRequest(BaseModel):
    body: str = Field(
        min_length=1,
        max_length=10000,
    )

    @field_validator("body")
    @classmethod
    def normalise_body(
        cls,
        value: str,
    ) -> str:
        body = value.strip()

        if not body:
            raise ValueError(
                "Comment is required.",
            )

        return body


class TaskCommentResult(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    task_id: int
    user_id: int | None
    body: str
    deleted_at: datetime | None
    deleted_by_user_id: int | None
    created_at: datetime
    updated_at: datetime