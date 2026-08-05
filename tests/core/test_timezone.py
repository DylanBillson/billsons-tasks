from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.core.timezone import (
    format_compact_date,
    format_compact_datetime,
    format_date,
    format_datetime,
    format_time,
    get_timezone,
    local_now,
    to_local,
    to_utc,
    utc_now,
)


def test_utc_now_returns_timezone_aware_utc_datetime() -> None:
    result = utc_now()

    assert result.tzinfo is UTC
    assert result.utcoffset().total_seconds() == 0


def test_get_timezone_returns_configured_timezone(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "default_timezone",
        "Europe/London",
    )

    result = get_timezone()

    assert isinstance(
        result,
        ZoneInfo,
    )

    assert result.key == "Europe/London"


def test_local_now_uses_configured_timezone(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "default_timezone",
        "Europe/London",
    )

    result = local_now()

    assert result.tzinfo is not None
    assert getattr(
        result.tzinfo,
        "key",
        None,
    ) == "Europe/London"


def test_to_local_converts_utc_datetime_to_london_summer_time(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "default_timezone",
        "Europe/London",
    )

    value = datetime(
        2026,
        8,
        7,
        11,
        0,
        tzinfo=UTC,
    )

    result = to_local(
        value,
    )

    assert result is not None
    assert result.hour == 12
    assert result.minute == 0
    assert result.utcoffset().total_seconds() == 3_600


def test_to_local_treats_naive_datetime_as_utc(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "default_timezone",
        "Europe/London",
    )

    value = datetime(
        2026,
        8,
        7,
        11,
        0,
    )

    result = to_local(
        value,
    )

    assert result is not None
    assert result.hour == 12
    assert result.minute == 0


def test_to_local_returns_none_for_none() -> None:
    assert to_local(
        None,
    ) is None


def test_to_utc_converts_aware_local_datetime(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "default_timezone",
        "Europe/London",
    )

    london_timezone = ZoneInfo(
        "Europe/London",
    )

    value = datetime(
        2026,
        8,
        7,
        12,
        0,
        tzinfo=london_timezone,
    )

    result = to_utc(
        value,
    )

    assert result is not None
    assert result.tzinfo is UTC
    assert result.hour == 11
    assert result.minute == 0


def test_to_utc_treats_naive_datetime_as_local_time(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "default_timezone",
        "Europe/London",
    )

    value = datetime(
        2026,
        8,
        7,
        12,
        0,
    )

    result = to_utc(
        value,
    )

    assert result is not None
    assert result.tzinfo is UTC
    assert result.hour == 11
    assert result.minute == 0


def test_to_utc_returns_none_for_none() -> None:
    assert to_utc(
        None,
    ) is None


def test_format_datetime_uses_application_timezone(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "default_timezone",
        "Europe/London",
    )

    value = datetime(
        2026,
        8,
        7,
        11,
        0,
        tzinfo=UTC,
    )

    assert format_datetime(
        value,
    ) == "07 August 2026 12:00"


def test_format_datetime_can_include_seconds(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "default_timezone",
        "Europe/London",
    )

    value = datetime(
        2026,
        8,
        7,
        11,
        0,
        35,
        tzinfo=UTC,
    )

    assert format_datetime(
        value,
        include_seconds=True,
    ) == "07 August 2026 12:00:35"


def test_format_compact_datetime_uses_requested_format(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "default_timezone",
        "Europe/London",
    )

    value = datetime(
        2026,
        8,
        7,
        11,
        0,
        tzinfo=UTC,
    )

    assert format_compact_datetime(
        value,
    ) == "12:00 07/08/26"


def test_format_compact_datetime_can_include_seconds(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "default_timezone",
        "Europe/London",
    )

    value = datetime(
        2026,
        8,
        7,
        11,
        0,
        35,
        tzinfo=UTC,
    )

    assert format_compact_datetime(
        value,
        include_seconds=True,
    ) == "12:00:35 07/08/26"


def test_format_date_accepts_datetime(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "default_timezone",
        "Europe/London",
    )

    value = datetime(
        2026,
        8,
        7,
        23,
        30,
        tzinfo=UTC,
    )

    assert format_date(
        value,
    ) == "08 August 2026"


def test_format_date_accepts_date() -> None:
    value = date(
        2026,
        8,
        7,
    )

    assert format_date(
        value,
    ) == "07 August 2026"


def test_format_compact_date_accepts_datetime(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "default_timezone",
        "Europe/London",
    )

    value = datetime(
        2026,
        8,
        7,
        23,
        30,
        tzinfo=UTC,
    )

    assert format_compact_date(
        value,
    ) == "08/08/26"


def test_format_compact_date_accepts_date() -> None:
    value = date(
        2026,
        8,
        7,
    )

    assert format_compact_date(
        value,
    ) == "07/08/26"


def test_format_time_uses_application_timezone(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "default_timezone",
        "Europe/London",
    )

    value = datetime(
        2026,
        8,
        7,
        11,
        0,
        tzinfo=UTC,
    )

    assert format_time(
        value,
    ) == "12:00"


def test_format_time_can_include_seconds(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "default_timezone",
        "Europe/London",
    )

    value = datetime(
        2026,
        8,
        7,
        11,
        0,
        35,
        tzinfo=UTC,
    )

    assert format_time(
        value,
        include_seconds=True,
    ) == "12:00:35"


def test_formatters_return_empty_string_for_none() -> None:
    assert format_datetime(
        None,
    ) == ""

    assert format_compact_datetime(
        None,
    ) == ""

    assert format_date(
        None,
    ) == ""

    assert format_compact_date(
        None,
    ) == ""

    assert format_time(
        None,
    ) == ""