from dataclasses import dataclass, field
from typing import Mapping

from pydantic import ValidationError

from app.schemas.auth import (
    LoginRequest,
    PasswordResetRequest,
)
from app.web.forms.common import (
    FormErrors,
    apply_validation_errors,
    get_checkbox,
    get_string,
)


@dataclass
class LoginForm:
    username: str = ""
    password: str = ""
    remember_me: bool = False
    errors: FormErrors = field(
        default_factory=FormErrors,
    )

    @classmethod
    def from_form_data(
        cls,
        form_data: Mapping[str, object],
    ) -> "LoginForm":
        return cls(
            username=get_string(
                form_data,
                "username",
            ),
            password=get_string(
                form_data,
                "password",
                strip=False,
            ),
            remember_me=get_checkbox(
                form_data,
                "remember_me",
            ),
        )

    def validate(
        self,
    ) -> LoginRequest | None:
        self.errors = FormErrors()

        try:
            login_request = LoginRequest(
                username=self.username,
                password=self.password,
                remember_me=self.remember_me,
            )
        except ValidationError as exc:
            apply_validation_errors(
                errors=self.errors,
                exception=exc,
            )

            return None

        self.username = login_request.username
        self.remember_me = login_request.remember_me

        return login_request

    def clear_password(
        self,
    ) -> None:
        self.password = ""


@dataclass
class PasswordResetForm:
    new_password: str = ""
    confirm_password: str = ""
    errors: FormErrors = field(
        default_factory=FormErrors,
    )

    @classmethod
    def from_form_data(
        cls,
        form_data: Mapping[str, object],
    ) -> "PasswordResetForm":
        return cls(
            new_password=get_string(
                form_data,
                "new_password",
                strip=False,
            ),
            confirm_password=get_string(
                form_data,
                "confirm_password",
                strip=False,
            ),
        )

    def validate(
        self,
    ) -> PasswordResetRequest | None:
        self.errors = FormErrors()

        try:
            password_reset = PasswordResetRequest(
                new_password=self.new_password,
                confirm_password=self.confirm_password,
            )
        except ValidationError as exc:
            apply_validation_errors(
                errors=self.errors,
                exception=exc,
            )

            return None

        return password_reset

    def clear_passwords(
        self,
    ) -> None:
        self.new_password = ""
        self.confirm_password = ""