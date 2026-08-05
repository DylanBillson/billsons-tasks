from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


UserGlobalRole = Literal[
    "user",
    "administrator",
]


class UserCreateRequest(BaseModel):
    username: str = Field(
        min_length=1,
        max_length=100,
    )

    display_name: str = Field(
        min_length=1,
        max_length=150,
    )

    password: str = Field(
        min_length=1,
        max_length=128,
    )

    confirm_password: str = Field(
        min_length=1,
        max_length=128,
    )

    global_role: UserGlobalRole = "user"

    is_active: bool = True

    @field_validator("username")
    @classmethod
    def normalise_username(
        cls,
        value: str,
    ) -> str:
        username = value.strip().lower()

        if not username:
            raise ValueError(
                "Username is required.",
            )

        if any(
            character.isspace()
            for character in username
        ):
            raise ValueError(
                "Username cannot contain spaces.",
            )

        return username

    @field_validator("display_name")
    @classmethod
    def normalise_display_name(
        cls,
        value: str,
    ) -> str:
        display_name = value.strip()

        if not display_name:
            raise ValueError(
                "Display name is required.",
            )

        return display_name

    @model_validator(mode="after")
    def validate_password_confirmation(
        self,
    ) -> "UserCreateRequest":
        if self.password != self.confirm_password:
            raise ValueError(
                "The passwords do not match.",
            )

        return self


class UserUpdateRequest(BaseModel):
    username: str = Field(
        min_length=1,
        max_length=100,
    )

    display_name: str = Field(
        min_length=1,
        max_length=150,
    )

    global_role: UserGlobalRole = "user"

    @field_validator("username")
    @classmethod
    def normalise_username(
        cls,
        value: str,
    ) -> str:
        username = value.strip().lower()

        if not username:
            raise ValueError(
                "Username is required.",
            )

        if any(
            character.isspace()
            for character in username
        ):
            raise ValueError(
                "Username cannot contain spaces.",
            )

        return username

    @field_validator("display_name")
    @classmethod
    def normalise_display_name(
        cls,
        value: str,
    ) -> str:
        display_name = value.strip()

        if not display_name:
            raise ValueError(
                "Display name is required.",
            )

        return display_name


class UserResult(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    username: str
    display_name: str
    global_role: str
    is_active: bool
    is_anonymised: bool