from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class LiveUpdateScope(StrEnum):
    SECTION = "section"
    TASK = "task"


class SectionLiveUpdateSnapshot(BaseModel):
    model_config = ConfigDict(
        frozen=True,
    )

    section_id: int
    section_updated_at: datetime

    section_list_count: int
    latest_section_list_updated_at: datetime | None

    task_count: int
    latest_task_updated_at: datetime | None

    task_assignee_count: int
    latest_task_assignee_updated_at: datetime | None


class TaskLiveUpdateSnapshot(BaseModel):
    model_config = ConfigDict(
        frozen=True,
    )

    task_id: int
    task_updated_at: datetime

    section_list_id: int
    section_list_updated_at: datetime

    section_id: int
    section_updated_at: datetime

    comment_count: int
    latest_comment_updated_at: datetime | None

    history_event_count: int
    latest_history_event_created_at: datetime | None

    task_assignee_count: int
    latest_task_assignee_updated_at: datetime | None


class LiveUpdateRevision(BaseModel):
    model_config = ConfigDict(
        frozen=True,
    )

    scope: LiveUpdateScope
    resource_id: int
    revision: str