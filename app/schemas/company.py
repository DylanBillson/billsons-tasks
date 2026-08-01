from pydantic import BaseModel, Field, field_validator

from app.core.constants import CompanyRole


COMPANY_NAME_MAX_LENGTH = 150
COMPANY_DESCRIPTION_MAX_LENGTH = 5000


class CompanyCreateRequest(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=COMPANY_NAME_MAX_LENGTH,
    )

    description: str | None = Field(
        default=None,
        max_length=COMPANY_DESCRIPTION_MAX_LENGTH,
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
                "Company name is required.",
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


class CompanyUpdateRequest(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=COMPANY_NAME_MAX_LENGTH,
    )

    description: str | None = Field(
        default=None,
        max_length=COMPANY_DESCRIPTION_MAX_LENGTH,
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
                "Company name is required.",
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


class CompanyMembershipCreateRequest(BaseModel):
    user_id: int = Field(
        gt=0,
    )

    role: CompanyRole = CompanyRole.EMPLOYEE


class CompanyMembershipUpdateRequest(BaseModel):
    role: CompanyRole