from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
    def has_errors(
        self,
    ) -> bool:
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

    def first_for_field(
        self,
        field_name: str,
    ) -> str | None:
        messages = self.for_field(
            field_name,
        )

        if not messages:
            return None

        return messages[0]


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
    *,
    strip: bool = True,
) -> str | None:
    value = get_string(
        form_data,
        field_name,
        strip=strip,
    )

    return value or None


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


def get_integer(
    form_data: Mapping[str, object],
    field_name: str,
) -> int | None:
    value = get_string(
        form_data,
        field_name,
    )

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


def get_integer_list(
    form_data: Mapping[str, object],
    field_name: str,
) -> list[int]:
    raw_values = _get_raw_list(
        form_data,
        field_name,
    )

    values: list[int] = []

    for raw_value in raw_values:
        value = str(
            raw_value,
        ).strip()

        if not value:
            continue

        try:
            parsed = int(
                value,
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        values.append(
            parsed,
        )

    return list(
        dict.fromkeys(
            values,
        ),
    )


def parse_datetime_local(
    value: str,
    *,
    timezone_name: str = "Europe/London",
) -> datetime:
    """
    Convert an HTML ``datetime-local`` value into an aware UTC datetime.

    Browser datetime-local controls do not include an offset, so the value is
    interpreted using the application's configured local timezone.
    """
    normalised_value = value.strip()

    if not normalised_value:
        raise ValueError(
            "Please enter a date and time.",
        )

    try:
        parsed = datetime.fromisoformat(
            normalised_value,
        )

    except ValueError as exc:
        raise ValueError(
            "Please enter a valid date and time.",
        ) from exc

    try:
        local_timezone = ZoneInfo(
            timezone_name,
        )

    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            "The configured application timezone is invalid.",
        ) from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=local_timezone,
        )
    else:
        parsed = parsed.astimezone(
            local_timezone,
        )

    return parsed.astimezone(
        timezone.utc,
    )


def format_datetime_local(
    value: datetime | None,
    *,
    timezone_name: str = "Europe/London",
) -> str:
    """
    Format an aware datetime for an HTML ``datetime-local`` input.
    """
    if value is None:
        return ""

    try:
        local_timezone = ZoneInfo(
            timezone_name,
        )

    except ZoneInfoNotFoundError:
        local_timezone = timezone.utc

    if value.tzinfo is None:
        value = value.replace(
            tzinfo=timezone.utc,
        )

    local_value = value.astimezone(
        local_timezone,
    )

    return local_value.strftime(
        "%Y-%m-%dT%H:%M",
    )


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
            error,
        )

        field_name = _get_error_field_name(
            location,
        )

        if field_name is None:
            errors.add_form_error(
                message,
            )

            continue

        errors.add_field_error(
            field_name,
            message,
        )


def _get_raw_list(
    form_data: Mapping[str, object],
    field_name: str,
) -> list[object]:
    getlist = getattr(
        form_data,
        "getlist",
        None,
    )

    if callable(
        getlist,
    ):
        return list(
            getlist(
                field_name,
            ),
        )

    raw_value = form_data.get(
        field_name,
    )

    if raw_value is None:
        return []

    if isinstance(
        raw_value,
        (
            list,
            tuple,
            set,
        ),
    ):
        return list(
            raw_value,
        )

    return [
        raw_value,
    ]


def _get_error_field_name(
    location: object,
) -> str | None:
    if not isinstance(
        location,
        (
            list,
            tuple,
        ),
    ):
        return None

    if not location:
        return None

    first_part = str(
        location[0],
    )

    if first_part in {
        "__root__",
        "root",
    }:
        return None

    return first_part


def _normalise_validation_message(
    error: Mapping[str, Any],
) -> str:
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

    return message