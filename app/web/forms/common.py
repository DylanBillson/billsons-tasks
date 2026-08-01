from dataclasses import dataclass, field
from typing import Mapping

from pydantic import ValidationError


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


def get_string(
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


def get_optional_string(
    form_data: Mapping[str, object],
    field_name: str,
) -> str | None:
    value = get_string(
        form_data,
        field_name,
    )

    return value or None


def get_integer(
    form_data: Mapping[str, object],
    field_name: str,
) -> int | None:
    raw_value = form_data.get(
        field_name,
    )

    if raw_value is None:
        return None

    value = str(
        raw_value,
    ).strip()

    if not value:
        return None

    try:
        return int(
            value,
        )
    except (
        TypeError,
        ValueError,
    ):
        return None


def get_checkbox(
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


def apply_validation_errors(
    *,
    errors: FormErrors,
    exception: ValidationError,
) -> None:
    for error in exception.errors():
        location = error.get(
            "loc",
            (),
        )

        message = _normalise_validation_message(
            str(
                error.get(
                    "msg",
                    "Invalid value.",
                ),
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


def _normalise_validation_message(
    message: str,
) -> str:
    prefix = "Value error, "

    if message.startswith(
        prefix,
    ):
        return message[
            len(prefix):
        ]

    return message