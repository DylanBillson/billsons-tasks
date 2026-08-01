from pydantic import BaseModel, Field, field_validator


SECTION_NAME_MAX_LENGTH = 150
SECTION_DESCRIPTION_MAX_LENGTH = 5000


class SectionCreateRequest(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=SECTION_NAME_MAX_LENGTH,
    )

    description: str | None = Field(
        default=None,
        max_length=SECTION_DESCRIPTION_MAX_LENGTH,
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
                "Section name is required.",
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


class SectionUpdateRequest(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=SECTION_NAME_MAX_LENGTH,
    )

    description: str | None = Field(
        default=None,
        max_length=SECTION_DESCRIPTION_MAX_LENGTH,
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
                "Section name is required.",
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


class SectionMembershipCreateRequest(BaseModel):
    user_id: int = Field(
        gt=0,
    )