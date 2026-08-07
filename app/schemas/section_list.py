from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

LiveUpdateRevisionToken = str

class SectionListCreateRequest(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=150,
    )

    description: str | None = Field(
        default=None,
        max_length=5000,
    )

    @field_validator("name")
    @classmethod
    def normalise_name(
        cls,
        value: str,
    ) -> str:
        name = value.strip()

        if not name:
            raise ValueError(
                "List name is required.",
            )

        return name

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


class SectionListUpdateRequest(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=150,
    )

    description: str | None = Field(
        default=None,
        max_length=5000,
    )

    @field_validator("name")
    @classmethod
    def normalise_name(
        cls,
        value: str,
    ) -> str:
        name = value.strip()

        if not name:
            raise ValueError(
                "List name is required.",
            )

        return name

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


class SectionListPositionUpdate(BaseModel):
    list_id: int = Field(
        gt=0,
    )

    sort_position: int = Field(
        ge=0,
    )


class SectionListReorderRequest(BaseModel):
    items: list[SectionListPositionUpdate] = Field(
        min_length=1,
        max_length=500,
    )

    known_revision: LiveUpdateRevisionToken | None = Field(
        default=None,
        min_length=1,
        max_length=64,
    )

    @field_validator("items")
    @classmethod
    def require_unique_list_ids(
        cls,
        value: list[SectionListPositionUpdate],
    ) -> list[SectionListPositionUpdate]:
        list_ids = [
            item.list_id
            for item in value
        ]

        if len(list_ids) != len(set(list_ids)):
            raise ValueError(
                "Each list may appear only once in a reorder request.",
            )

        return value


class SectionListResult(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    section_id: int
    name: str
    description: str | None
    sort_position: int
    is_archived: bool