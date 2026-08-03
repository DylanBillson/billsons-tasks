from datetime import datetime

from pydantic import BaseModel, Field


class DashboardMetrics(BaseModel):
    company_count: int = Field(
        ge=0,
    )

    section_count: int = Field(
        ge=0,
    )

    active_user_count: int | None = Field(
        default=None,
        ge=0,
    )

    open_task_count: int = Field(
        ge=0,
    )

    overdue_task_count: int = Field(
        ge=0,
    )

    completed_task_count: int = Field(
        ge=0,
    )

    deleted_task_count: int = Field(
        ge=0,
    )


class DashboardTaskSummary(BaseModel):
    id: int = Field(
        gt=0,
    )

    title: str

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

    updated_at: datetime

    state: str

    assignee_names: list[str] = Field(
        default_factory=list,
    )


class DashboardCompanySummary(BaseModel):
    id: int = Field(
        gt=0,
    )

    name: str

    section_count: int = Field(
        ge=0,
    )

    open_task_count: int = Field(
        ge=0,
    )

    overdue_task_count: int = Field(
        ge=0,
    )

    completed_task_count: int = Field(
        ge=0,
    )


class DashboardData(BaseModel):
    generated_at: datetime

    is_administrator_view: bool

    metrics: DashboardMetrics

    companies: list[DashboardCompanySummary] = Field(
        default_factory=list,
    )

    due_soon_tasks: list[DashboardTaskSummary] = Field(
        default_factory=list,
    )

    recent_tasks: list[DashboardTaskSummary] = Field(
        default_factory=list,
    )