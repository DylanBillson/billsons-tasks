from datetime import UTC, datetime

from zoneinfo import ZoneInfo

from app.core.config import settings


def utc_now() -> datetime:
    """
    Returns the current UTC time.
    """

    return datetime.now(UTC)


def get_timezone() -> ZoneInfo:
    """
    Returns the application's configured timezone.
    """

    return ZoneInfo(settings.default_timezone)


def local_now() -> datetime:
    """
    Returns the current time in the application's timezone.
    """

    return utc_now().astimezone(get_timezone())


def to_local(dt: datetime | None) -> datetime | None:
    """
    Converts a UTC datetime to the application's timezone.
    """

    if dt is None:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)

    return dt.astimezone(get_timezone())


def to_utc(dt: datetime | None) -> datetime | None:
    """
    Converts a datetime to UTC.
    """

    if dt is None:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=get_timezone())

    return dt.astimezone(UTC)


def format_datetime(
    dt: datetime | None,
    *,
    include_seconds: bool = False,
) -> str:
    """
    Formats a datetime for display in the application's timezone.
    """

    if dt is None:
        return ""

    dt = to_local(dt)

    if include_seconds:
        return dt.strftime("%d %B %Y %H:%M:%S")

    return dt.strftime("%d %B %Y %H:%M")


def format_date(dt: datetime | None) -> str:
    """
    Formats a date for display.
    """

    if dt is None:
        return ""

    return to_local(dt).strftime("%d %B %Y")


def format_time(dt: datetime | None) -> str:
    """
    Formats a time for display.
    """

    if dt is None:
        return ""

    return to_local(dt).strftime("%H:%M")