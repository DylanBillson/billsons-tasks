from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from tests.factories import (
    create_auth_session,
    create_user,
)


def _authenticate(
    client: TestClient,
    db: Session,
    *,
    user,
) -> None:
    _, session_token, csrf_token = create_auth_session(
        db,
        user=user,
    )

    db.commit()

    client.cookies.set(
        settings.session_cookie_name,
        session_token,
    )

    client.cookies.set(
        f"{settings.session_cookie_name}_csrf",
        csrf_token,
    )


def test_summary_and_filters_share_overview_container(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        "/my-tasks",
    )

    assert response.status_code == 200

    overview_start = response.text.index(
        'class="my-task-overview"',
    )
    results_start = response.text.index(
        'class="content-card my-task-results-card"',
    )
    overview_html = response.text[
        overview_start:results_start
    ]

    assert 'class="my-task-summary"' in overview_html
    assert "my-task-filter-card" in overview_html
    assert 'id="my-tasks-summary-heading"' in overview_html
    assert 'id="my-task-filters-heading"' in overview_html


def test_assigned_tasks_follow_summary_and_filters(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        "/my-tasks",
    )

    assert response.status_code == 200

    summary_position = response.text.index(
        'id="my-tasks-summary-heading"',
    )
    filters_position = response.text.index(
        'id="my-task-filters-heading"',
    )
    results_position = response.text.index(
        'id="my-task-results-heading"',
    )

    assert summary_position < results_position
    assert filters_position < results_position


def test_my_tasks_uses_compact_metric_grid(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        "/my-tasks",
    )

    assert response.status_code == 200
    assert "metric-grid my-task-metric-grid" in response.text

    for label in (
        "All",
        "Open",
        "Overdue",
        "Due Today",
        "Due Soon",
        "Completed",
    ):
        assert label in response.text


def test_filter_form_uses_my_task_layout_hooks(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        "/my-tasks",
    )

    assert response.status_code == 200
    assert "filter-panel my-task-filter-panel" in response.text
    assert "filter-grid my-task-filter-grid" in response.text
    assert "my-task-filter-search" in response.text
    assert "data-my-task-filters" in response.text
    assert "data-filter-form" in response.text


def test_old_standalone_filter_card_layout_is_not_rendered(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        "/my-tasks",
    )

    assert response.status_code == 200

    overview_position = response.text.index(
        'class="my-task-overview"',
    )
    results_position = response.text.index(
        'class="content-card my-task-results-card"',
    )

    assert overview_position < results_position
    assert response.text.count(
        'id="my-task-filters-heading"',
    ) == 1
