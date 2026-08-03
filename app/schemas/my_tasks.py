from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)


MyTaskStateFilter = Literal[
    "all",
    "open",
    "overdue",
    "due_today",
    "due_soon",
    "completed",
]


class MyTasksFilterOptions(BaseModel):
    state: MyTaskStateFilter = "open"

    company_id: int | None = Field(
        default=None,
        gt=0,
    )

    section_id: int | None = Field(
        default=None,
        gt=0,
    )

    search: str | None = Field(
        default=None,
        max_length=250,
    )

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


class MyTasksMetrics(BaseModel):
    all_count: int = Field(
        ge=0,
    )

    open_count: int = Field(
        ge=0,
    )

    overdue_count: int = Field(
        ge=0,
    )

    due_today_count: int = Field(
        ge=0,
    )

    due_soon_count: int = Field(
        ge=0,
    )

    completed_count: int = Field(
        ge=0,
    )


class MyTasksCompanyOption(BaseModel):
    id: int = Field(
        gt=0,
    )

    name: str


class MyTasksSectionOption(BaseModel):
    id: int = Field(
        gt=0,
    )

    company_id: int = Field(
        gt=0,
    )

    name: str

    company_name: str


class MyTaskSummary(BaseModel):
    id: int = Field(
        gt=0,
    )

    title: str

    description: str | None = None

    company_id: int = Field(
        gt=0,
    )

    company_name: str

    section_id: int = Field(
        gt=0,
    )

    section_name: str

    section_list_id: int = Field(
        gt=0,
    )

    section_list_name: str

    due_at: datetime | None = None

    completed_at: datetime | None = None

    updated_at: datetime

    state: str

    assignee_names: list[str] = Field(
        default_factory=list,
    )


class MyTasksData(BaseModel):
    generated_at: datetime

    filters: MyTasksFilterOptions

    metrics: MyTasksMetrics

    tasks: list[MyTaskSummary] = Field(
        default_factory=list,
    )

    companies: list[MyTasksCompanyOption] = Field(
        default_factory=list,
    )

    sections: list[MyTasksSectionOption] = Field(
        default_factory=list,
    )