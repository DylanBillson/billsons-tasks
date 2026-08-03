from datetime import datetime
from typing import Any

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)


class AuditLogFilterOptions(BaseModel):
    search: str | None = Field(
        default=None,
        max_length=250,
    )

    user_id: int | None = Field(
        default=None,
        gt=0,
    )

    action: str | None = Field(
        default=None,
        max_length=100,
    )

    entity_type: str | None = Field(
        default=None,
        max_length=100,
    )

    entity_id: int | None = Field(
        default=None,
        gt=0,
    )

    created_from: datetime | None = None
    created_to: datetime | None = None

    page: int = Field(
        default=1,
        ge=1,
    )

    page_size: int = Field(
        default=25,
        ge=1,
        le=100,
    )

    @field_validator(
        "search",
        "action",
        "entity_type",
    )
    @classmethod
    def normalise_optional_string(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        normalised = value.strip()

        return normalised or None

    @model_validator(
        mode="after",
    )
    def validate_date_range(
        self,
    ) -> "AuditLogFilterOptions":
        if (
            self.created_from is not None
            and self.created_to is not None
            and self.created_from >= self.created_to
        ):
            raise ValueError(
                "The start date must be before the end date.",
            )

        return self


class AuditLogUserSummary(BaseModel):
    id: int = Field(
        gt=0,
    )

    username: str
    display_name: str

    is_active: bool
    is_anonymised: bool


class AuditLogSummary(BaseModel):
    id: int = Field(
        gt=0,
    )

    action: str
    summary: str

    user: AuditLogUserSummary | None = None

    entity_type: str | None = None
    entity_id: int | None = None

    ip_address: str | None = None
    user_agent: str | None = None

    created_at: datetime


class AuditLogDetail(AuditLogSummary):
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
    )


class AuditLogPage(BaseModel):
    filters: AuditLogFilterOptions

    logs: list[AuditLogSummary] = Field(
        default_factory=list,
    )

    total_items: int = Field(
        ge=0,
    )

    total_pages: int = Field(
        ge=1,
    )

    current_page: int = Field(
        ge=1,
    )

    page_size: int = Field(
        ge=1,
        le=100,
    )


class AuditLogFilterChoices(BaseModel):
    actions: list[str] = Field(
        default_factory=list,
    )

    entity_types: list[str] = Field(
        default_factory=list,
    )