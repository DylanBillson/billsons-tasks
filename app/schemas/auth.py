from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.security import PasswordValidationError, validate_password


class LoginRequest(BaseModel):
    username: str = Field(
        min_length=1,
        max_length=100,
    )
    password: str = Field(
        min_length=1,
        max_length=1024,
    )
    remember_me: bool = False

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

        return username


class LoginResult(BaseModel):
    user_id: int
    session_id: int
    session_token: str
    csrf_token: str
    expires_at: datetime
    remember_me: bool


class AuthenticatedSession(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    session_id: int
    user_id: int
    expires_at: datetime
    last_seen_at: datetime
    remember_me: bool


class PasswordResetRequest(BaseModel):
    new_password: str = Field(
        min_length=1,
        max_length=1024,
    )
    confirm_password: str = Field(
        min_length=1,
        max_length=1024,
    )

    @model_validator(mode="after")
    def validate_new_password(
        self,
    ) -> "PasswordResetRequest":
        try:
            validate_password(
                self.new_password,
                confirmation=self.confirm_password,
            )
        except PasswordValidationError as exc:
            raise ValueError(
                str(exc),
            ) from exc

        return self


class PasswordResetResult(BaseModel):
    user_id: int
    revoked_session_count: int
    password_reset_at: datetime