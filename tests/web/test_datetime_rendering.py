from datetime import UTC, date, datetime

from app.core.config import settings
from app.web.templating import templates


def test_compact_datetime_filter_is_registered() -> None:
    assert (
        templates.env.filters[
            "format_compact_datetime"
        ]
        is not None
    )


def test_long_datetime_filter_is_registered() -> None:
    assert (
        templates.env.filters[
            "format_datetime"
        ]
        is not None
    )


def test_date_filters_are_registered() -> None:
    assert (
        templates.env.filters[
            "format_date"
        ]
        is not None
    )

    assert (
        templates.env.filters[
            "format_compact_date"
        ]
        is not None
    )


def test_time_filter_is_registered() -> None:
    assert (
        templates.env.filters[
            "format_time"
        ]
        is not None
    )


def test_template_renders_compact_datetime_in_local_timezone(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "default_timezone",
        "Europe/London",
    )

    template = templates.env.from_string(
        "{{ value | format_compact_datetime }}"
    )

    rendered = template.render(
        value=datetime(
            2026,
            8,
            7,
            11,
            0,
            tzinfo=UTC,
        ),
    )

    assert rendered == "12:00 07/08/26"


def test_template_renders_long_datetime_in_local_timezone(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "default_timezone",
        "Europe/London",
    )

    template = templates.env.from_string(
        "{{ value | format_datetime }}"
    )

    rendered = template.render(
        value=datetime(
            2026,
            8,
            7,
            11,
            0,
            tzinfo=UTC,
        ),
    )

    assert rendered == "07 August 2026 12:00"


def test_template_renders_compact_date_from_date_value() -> None:
    template = templates.env.from_string(
        "{{ value | format_compact_date }}"
    )

    rendered = template.render(
        value=date(
            2026,
            8,
            7,
        ),
    )

    assert rendered == "07/08/26"


def test_template_renders_time_in_local_timezone(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "default_timezone",
        "Europe/London",
    )

    template = templates.env.from_string(
        "{{ value | format_time }}"
    )

    rendered = template.render(
        value=datetime(
            2026,
            8,
            7,
            11,
            0,
            tzinfo=UTC,
        ),
    )

    assert rendered == "12:00"


def test_datetime_filters_render_empty_string_for_none() -> None:
    template = templates.env.from_string(
        (
            "{{ value | format_datetime }}|"
            "{{ value | format_compact_datetime }}|"
            "{{ value | format_date }}|"
            "{{ value | format_compact_date }}|"
            "{{ value | format_time }}"
        ),
    )

    rendered = template.render(
        value=None,
    )

    assert rendered == "||||"