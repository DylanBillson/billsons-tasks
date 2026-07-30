from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


SettingValueType = Literal[
    "string",
    "integer",
    "boolean",
    "timezone",
]


class SettingBase(BaseModel):
    key: str = Field(
        min_length=1,
        max_length=100,
    )

    value: str

    value_type: SettingValueType = "string"

    is_public: bool = False

    description: str | None = None

    @field_validator("key")
    @classmethod
    def normalise_key(
        cls,
        value: str,
    ) -> str:
        return value.strip().lower()

    @field_validator("value")
    @classmethod
    def validate_value(
        cls,
        value: str,
    ) -> str:
        return value.strip()

    @field_validator("description")
    @classmethod
    def normalise_description(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = value.strip()

        return value or None


class SettingCreate(SettingBase):
    pass


class SettingValueUpdate(BaseModel):
    value: str

    @field_validator("value")
    @classmethod
    def normalise_value(
        cls,
        value: str,
    ) -> str:
        return value.strip()


class SettingDefinitionUpdate(BaseModel):
    value_type: SettingValueType

    is_public: bool

    description: str | None = None

    @field_validator("description")
    @classmethod
    def normalise_description(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = value.strip()

        return value or None


class SettingRead(SettingBase):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int


class SettingValueValidator:
    @staticmethod
    def validate(
        *,
        value: str,
        value_type: SettingValueType,
    ) -> str:
        value = value.strip()

        if value_type == "string":
            return value

        if value_type == "integer":
            try:
                int(value)
            except ValueError as exc:
                raise ValueError(
                    "Value must be a valid integer.",
                ) from exc

            return value

        if value_type == "boolean":
            normalised = value.lower()

            if normalised not in {
                "true",
                "false",
                "1",
                "0",
                "yes",
                "no",
                "on",
                "off",
            }:
                raise ValueError(
                    "Value must be a valid boolean.",
                )

            return normalised

        if value_type == "timezone":
            try:
                ZoneInfo(value)
            except ZoneInfoNotFoundError as exc:
                raise ValueError(
                    "Value must be a valid IANA timezone.",
                ) from exc

            return value

        raise ValueError(
            f"Unsupported setting value type: {value_type}",
        )