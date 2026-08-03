from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


TaskStateFilter = Literal[
    "all",
    "open",
    "completed",
    "overdue",
    "deleted",
]


class TaskCreateRequest(BaseModel):
    section_list_id: int = Field(
        gt=0,
    )

    title: str = Field(
        min_length=1,
        max_length=250,
    )

    description: str | None = Field(
        default=None,
        max_length=20000,
    )

    due_at: datetime | None = None

    assignee_user_ids: list[int] = Field(
        default_factory=list,
        max_length=500,
    )

    @field_validator("title")
    @classmethod
    def normalise_title(
        cls,
        value: str,
    ) -> str:
        title = value.strip()

        if not title:
            raise ValueError(
                "Task title is required.",
            )

        return title

    @field_validator("description")
    @classmethod
    def normalise_description(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        description = value.strip()

        return description or None

    @field_validator("due_at")
    @classmethod
    def require_timezone_aware_due_at(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "Due date and time must include a timezone.",
            )

        return value

    @field_validator("assignee_user_ids")
    @classmethod
    def validate_assignee_user_ids(
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


class TaskUpdateRequest(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=250,
    )

    description: str | None = Field(
        default=None,
        max_length=20000,
    )

    due_at: datetime | None = None

    @field_validator("title")
    @classmethod
    def normalise_title(
        cls,
        value: str,
    ) -> str:
        title = value.strip()

        if not title:
            raise ValueError(
                "Task title is required.",
            )

        return title

    @field_validator("description")
    @classmethod
    def normalise_description(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        description = value.strip()

        return description or None

    @field_validator("due_at")
    @classmethod
    def require_timezone_aware_due_at(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "Due date and time must include a timezone.",
            )

        return value


class TaskMoveRequest(BaseModel):
    destination_list_id: int = Field(
        gt=0,
    )

    sort_position: int = Field(
        ge=0,
    )


class TaskPositionUpdate(BaseModel):
    task_id: int = Field(
        gt=0,
    )

    section_list_id: int = Field(
        gt=0,
    )

    sort_position: int = Field(
        ge=0,
    )


class TaskReorderRequest(BaseModel):
    items: list[TaskPositionUpdate] = Field(
        min_length=1,
        max_length=2000,
    )

    @field_validator("items")
    @classmethod
    def require_unique_task_ids(
        cls,
        value: list[TaskPositionUpdate],
    ) -> list[TaskPositionUpdate]:
        task_ids = [
            item.task_id
            for item in value
        ]

        if len(task_ids) != len(set(task_ids)):
            raise ValueError(
                "Each task may appear only once in a reorder request.",
            )

        return value


class TaskCompletionRequest(BaseModel):
    is_completed: bool


class TaskFilterOptions(BaseModel):
    state: TaskStateFilter = "all"

    section_list_id: int | None = Field(
        default=None,
        gt=0,
    )

    assignee_user_id: int | None = Field(
        default=None,
        gt=0,
    )

    search: str | None = Field(
        default=None,
        max_length=250,
    )

    due_from: datetime | None = None
    due_to: datetime | None = None

    @field_validator("search")
    @classmethod
    def normalise_search(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        search = value.strip()

        return search or None

    @field_validator(
        "due_from",
        "due_to",
    )
    @classmethod
    def require_timezone_aware_filter_dates(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "Filter dates must include a timezone.",
            )

        return value

    @model_validator(mode="after")
    def validate_due_range(
        self,
    ) -> "TaskFilterOptions":
        if (
            self.due_from is not None
            and self.due_to is not None
            and self.due_from > self.due_to
        ):
            raise ValueError(
                "The due-from date cannot be after the due-to date.",
            )

        return self


class TaskResult(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    section_list_id: int
    created_by_user_id: int
    title: str
    description: str | None
    due_at: datetime | None
    completed_at: datetime | None
    completed_by_user_id: int | None
    sort_position: int
    deleted_at: datetime | None
    deleted_by_user_id: int | None


class TaskMutationResult(BaseModel):
    task_id: int
    section_list_id: int
    sort_position: int
    state: str