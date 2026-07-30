from dataclasses import dataclass, field
from typing import Mapping

from pydantic import ValidationError

from app.schemas.auth import LoginRequest, PasswordResetRequest


@dataclass
class FormErrors:
    field_errors: dict[str, list[str]] = field(
        default_factory=dict,
    )
    form_errors: list[str] = field(
        default_factory=list,
    )

    @property
    def has_errors(self) -> bool:
        return bool(
            self.field_errors
            or self.form_errors
        )

    def add_field_error(
        self,
        field_name: str,
        message: str,
    ) -> None:
        self.field_errors.setdefault(
            field_name,
            [],
        ).append(
            message,
        )

    def add_form_error(
        self,
        message: str,
    ) -> None:
        self.form_errors.append(
            message,
        )

    def for_field(
        self,
        field_name: str,
    ) -> list[str]:
        return self.field_errors.get(
            field_name,
            [],
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
            username=_get_string(
                form_data,
                "username",
            ),
            password=_get_string(
                form_data,
                "password",
                strip=False,
            ),
            remember_me=_get_checkbox(
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
            _apply_validation_errors(
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
            new_password=_get_string(
                form_data,
                "new_password",
                strip=False,
            ),
            confirm_password=_get_string(
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
            _apply_validation_errors(
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


def _get_string(
    form_data: Mapping[str, object],
    field_name: str,
    *,
    strip: bool = True,
) -> str:
    raw_value = form_data.get(
        field_name,
        "",
    )

    if raw_value is None:
        return ""

    value = str(
        raw_value,
    )

    if strip:
        return value.strip()

    return value


def _get_checkbox(
    form_data: Mapping[str, object],
    field_name: str,
) -> bool:
    raw_value = form_data.get(
        field_name,
    )

    if raw_value is None:
        return False

    if isinstance(
        raw_value,
        bool,
    ):
        return raw_value

    normalised_value = str(
        raw_value,
    ).strip().lower()

    return normalised_value in {
        "1",
        "true",
        "yes",
        "on",
    }


def _apply_validation_errors(
    *,
    errors: FormErrors,
    exception: ValidationError,
) -> None:
    for error in exception.errors():
        location = error.get(
            "loc",
            (),
        )

        message = str(
            error.get(
                "msg",
                "Invalid value.",
            ),
        )

        if (
            location
            and location[0] != "__root__"
        ):
            field_name = str(
                location[0],
            )

            errors.add_field_error(
                field_name,
                message,
            )

            continue

        errors.add_form_error(
            message,
        )