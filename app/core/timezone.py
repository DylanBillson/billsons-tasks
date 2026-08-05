from datetime import UTC, date, datetime

from zoneinfo import ZoneInfo

from app.core.config import settings


DateLike = datetime | date


def utc_now() -> datetime:
    """
    Return the current timezone-aware UTC time.
    """

    return datetime.now(
        UTC,
    )


def get_timezone() -> ZoneInfo:
    """
    Return the application's configured timezone.
    """

    return ZoneInfo(
        settings.default_timezone,
    )


def local_now() -> datetime:
    """
    Return the current time in the application's configured timezone.
    """

    return utc_now().astimezone(
        get_timezone(),
    )


def to_local(
    value: datetime | None,
) -> datetime | None:
    """
    Convert a datetime to the application's configured timezone.

    Naive datetimes are treated as UTC because database timestamps are stored
    in UTC.
    """

    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(
            tzinfo=UTC,
        )

    return value.astimezone(
        get_timezone(),
    )


def to_utc(
    value: datetime | None,
) -> datetime | None:
    """
    Convert a datetime to UTC.

    Naive datetimes are interpreted in the application's configured timezone.
    """

    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(
            tzinfo=get_timezone(),
        )

    return value.astimezone(
        UTC,
    )


def format_datetime(
    value: datetime | None,
    *,
    include_seconds: bool = False,
) -> str:
    """
    Format a datetime in the application's configured timezone.

    Examples:

        07 August 2026 12:00
        07 August 2026 12:00:30
    """

    local_value = to_local(
        value,
    )

    if local_value is None:
        return ""

    if include_seconds:
        return local_value.strftime(
            "%d %B %Y %H:%M:%S",
        )

    return local_value.strftime(
        "%d %B %Y %H:%M",
    )


def format_compact_datetime(
    value: datetime | None,
    *,
    include_seconds: bool = False,
) -> str:
    """
    Format a datetime using the compact application display format.

    Examples:

        12:00 07/08/26
        12:00:30 07/08/26
    """

    local_value = to_local(
        value,
    )

    if local_value is None:
        return ""

    if include_seconds:
        return local_value.strftime(
            "%H:%M:%S %d/%m/%y",
        )

    return local_value.strftime(
        "%H:%M %d/%m/%y",
    )


def format_date(
    value: DateLike | None,
) -> str:
    """
    Format a date for long-form display.

    Datetime values are first converted into the configured timezone.
    Date-only values are rendered without timezone conversion.
    """

    resolved_value = _resolve_date_like(
        value,
    )

    if resolved_value is None:
        return ""

    return resolved_value.strftime(
        "%d %B %Y",
    )


def format_compact_date(
    value: DateLike | None,
) -> str:
    """
    Format a date using the compact application display format.

    Example:

        07/08/26
    """

    resolved_value = _resolve_date_like(
        value,
    )

    if resolved_value is None:
        return ""

    return resolved_value.strftime(
        "%d/%m/%y",
    )


def format_time(
    value: datetime | None,
    *,
    include_seconds: bool = False,
) -> str:
    """
    Format a time in the application's configured timezone.
    """

    local_value = to_local(
        value,
    )

    if local_value is None:
        return ""

    if include_seconds:
        return local_value.strftime(
            "%H:%M:%S",
        )

    return local_value.strftime(
        "%H:%M",
    )


def _resolve_date_like(
    value: DateLike | None,
) -> DateLike | None:
    """
    Resolve a date or datetime into a value suitable for date formatting.
    """

    if value is None:
        return None

    if isinstance(
        value,
        datetime,
    ):
        return to_local(
            value,
        )

    return value