from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class TaskAssigneeCreateRequest(BaseModel):
    user_id: int = Field(
        gt=0,
    )


class TaskAssigneeReplaceRequest(BaseModel):
    user_ids: list[int] = Field(
        default_factory=list,
        max_length=500,
    )

    @field_validator("user_ids")
    @classmethod
    def validate_user_ids(
        cls,
        value: list[int],
    ) -> list[int]:
        if any(user_id <= 0 for user_id in value):
            raise ValueError(
                "Assignee user IDs must be positive integers.",
            )

        if len(value) != len(set(value)):
            raise ValueError(
                "Each user may be assigned only once.",
            )

        return value


class TaskAssigneeResult(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    task_id: int
    user_id: int