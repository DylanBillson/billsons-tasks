from datetime import datetime

from pydantic import BaseModel, Field


class UserAnonymisationPreview(BaseModel):
    user_id: int = Field(
        gt=0,
    )

    username: str
    display_name: str

    company_membership_count: int = Field(
        ge=0,
    )

    section_membership_count: int = Field(
        ge=0,
    )

    task_assignment_count: int = Field(
        ge=0,
    )

    active_session_count: int = Field(
        ge=0,
    )

    comment_count: int = Field(
        ge=0,
    )

    task_history_event_count: int = Field(
        ge=0,
    )


class UserAnonymisationResult(BaseModel):
    user_id: int = Field(
        gt=0,
    )

    anonymised_username: str
    anonymised_display_name: str
    anonymised_at: datetime

    removed_company_membership_count: int = Field(
        ge=0,
    )

    removed_section_membership_count: int = Field(
        ge=0,
    )

    removed_task_assignment_count: int = Field(
        ge=0,
    )

    revoked_session_count: int = Field(
        ge=0,
    )

    scrubbed_audit_log_count: int = Field(
        ge=0,
    )