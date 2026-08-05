from dataclasses import (
    dataclass,
    field,
)
from typing import Mapping

from pydantic import ValidationError

from app.core.constants import (
    ANONYMISATION_CONFIRMATION_PHRASE,
    GlobalRole,
)
from app.models.user import User
from app.schemas.user import (
    UserCreateRequest,
    UserUpdateRequest,
)
from app.web.forms.common import FormErrors


def _form_value(
    form_data: Mapping[str, object],
    field_name: str,
) -> str:
    value = form_data.get(
        field_name,
        "",
    )

    return str(
        value
        or "",
    ).strip()


def _form_checkbox(
    form_data: Mapping[str, object],
    field_name: str,
) -> bool:
    value = form_data.get(
        field_name,
    )

    return (
        str(
            value,
        ).strip().lower()
        in {
            "1",
            "true",
            "yes",
            "on",
        }
    )


def _apply_validation_errors(
    errors: FormErrors,
    validation_error: ValidationError,
) -> None:
    for error in validation_error.errors(
        include_url=False,
    ):
        location = error.get(
            "loc",
            (),
        )

        field_name = (
            str(
                location[0],
            )
            if location
            else ""
        )

        message = str(
            error.get(
                "msg",
                "Invalid value.",
            ),
        )

        if message.startswith(
            "Value error, ",
        ):
            message = message.removeprefix(
                "Value error, ",
            )

        if field_name in {
            "username",
            "display_name",
            "password",
            "confirm_password",
            "global_role",
            "is_active",
        }:
            errors.add_field_error(
                field_name,
                message,
            )

        else:
            errors.add_form_error(
                message,
            )


@dataclass
class UserCreateForm:
    username: str = ""
    display_name: str = ""
    password: str = ""
    confirm_password: str = ""
    global_role: str = (
        GlobalRole.USER.value
    )
    is_active: bool = True

    errors: FormErrors = field(
        default_factory=FormErrors,
    )

    @classmethod
    def from_form_data(
        cls,
        form_data: Mapping[str, object],
    ) -> "UserCreateForm":
        return cls(
            username=_form_value(
                form_data,
                "username",
            ),
            display_name=_form_value(
                form_data,
                "display_name",
            ),
            password=_form_value(
                form_data,
                "password",
            ),
            confirm_password=_form_value(
                form_data,
                "confirm_password",
            ),
            global_role=(
                _form_value(
                    form_data,
                    "global_role",
                )
                or GlobalRole.USER.value
            ),
            is_active=_form_checkbox(
                form_data,
                "is_active",
            ),
        )

    def validate(
        self,
    ) -> UserCreateRequest | None:
        self.errors = FormErrors()

        try:
            return UserCreateRequest(
                username=self.username,
                display_name=self.display_name,
                password=self.password,
                confirm_password=(
                    self.confirm_password
                ),
                global_role=self.global_role,
                is_active=self.is_active,
            )

        except ValidationError as exc:
            _apply_validation_errors(
                self.errors,
                exc,
            )

            return None

    def clear_passwords(
        self,
    ) -> None:
        self.password = ""
        self.confirm_password = ""


@dataclass
class UserUpdateForm:
    username: str = ""
    display_name: str = ""
    global_role: str = (
        GlobalRole.USER.value
    )

    errors: FormErrors = field(
        default_factory=FormErrors,
    )

    @classmethod
    def from_user(
        cls,
        user: User,
    ) -> "UserUpdateForm":
        return cls(
            username=user.username,
            display_name=user.display_name,
            global_role=user.global_role,
        )

    @classmethod
    def from_form_data(
        cls,
        form_data: Mapping[str, object],
    ) -> "UserUpdateForm":
        return cls(
            username=_form_value(
                form_data,
                "username",
            ),
            display_name=_form_value(
                form_data,
                "display_name",
            ),
            global_role=(
                _form_value(
                    form_data,
                    "global_role",
                )
                or GlobalRole.USER.value
            ),
        )

    def validate(
        self,
    ) -> UserUpdateRequest | None:
        self.errors = FormErrors()

        try:
            return UserUpdateRequest(
                username=self.username,
                display_name=self.display_name,
                global_role=self.global_role,
            )

        except ValidationError as exc:
            _apply_validation_errors(
                self.errors,
                exc,
            )

            return None


@dataclass
class UserDeactivationForm:
    confirm_deactivation: bool = False

    errors: FormErrors = field(
        default_factory=FormErrors,
    )

    @classmethod
    def from_form_data(
        cls,
        form_data: Mapping[str, object],
    ) -> "UserDeactivationForm":
        return cls(
            confirm_deactivation=(
                _form_checkbox(
                    form_data,
                    "confirm_deactivation",
                )
            ),
        )

    def validate(
        self,
    ) -> bool:
        self.errors = FormErrors()

        if not self.confirm_deactivation:
            self.errors.add_field_error(
                "confirm_deactivation",
                (
                    "Confirm that you want to deactivate "
                    "this user."
                ),
            )

        return not self.errors.has_errors


@dataclass
class UserAnonymisationForm:
    confirmation_phrase: str = ""
    confirm_irreversible: bool = False

    errors: FormErrors = field(
        default_factory=FormErrors,
    )

    @classmethod
    def from_form_data(
        cls,
        form_data: Mapping[str, object],
    ) -> "UserAnonymisationForm":
        return cls(
            confirmation_phrase=_form_value(
                form_data,
                "confirmation_phrase",
            ),
            confirm_irreversible=(
                _form_checkbox(
                    form_data,
                    "confirm_irreversible",
                )
            ),
        )

    def validate(
        self,
    ) -> bool:
        self.errors = FormErrors()

        if (
            self.confirmation_phrase
            != ANONYMISATION_CONFIRMATION_PHRASE
        ):
            self.errors.add_field_error(
                "confirmation_phrase",
                (
                    "Enter ANONYMISE USER exactly "
                    "to continue."
                ),
            )

        if not self.confirm_irreversible:
            self.errors.add_field_error(
                "confirm_irreversible",
                (
                    "Confirm that you understand "
                    "anonymisation is irreversible."
                ),
            )

        return not self.errors.has_errors