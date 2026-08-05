from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import CompanyRole
from tests.factories import (
    create_auth_session,
    create_company,
    create_company_membership,
    create_section,
    create_section_list,
    create_task,
    create_user,
)


def _authenticate(
    client: TestClient,
    db: Session,
    *,
    user,
) -> str:
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

    return csrf_token


def _create_board_context(
    db: Session,
):
    creator = create_user(
        db,
    )

    company = create_company(
        db,
        name="Board Layout Company",
    )

    create_company_membership(
        db,
        company=company,
        user=creator,
        role=CompanyRole.MANAGER,
    )

    section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Board Layout Section",
    )

    first_list = create_section_list(
        db,
        section=section,
        name="First Equal List",
        sort_position=1000,
    )

    second_list = create_section_list(
        db,
        section=section,
        name="Second Equal List",
        sort_position=2000,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        title=(
            "A deliberately long task title that must wrap "
            "inside its list rather than widening the board"
        ),
        description=(
            "A deliberately long description that must remain "
            "contained within the task card."
        ),
        due_at=datetime(
            2026,
            8,
            7,
            11,
            0,
            tzinfo=UTC,
        ),
        sort_position=1000,
    )

    db.commit()

    return (
        creator,
        section,
        first_list,
        second_list,
        task,
    )


def test_section_board_renders_expected_layout_hooks(
    client: TestClient,
    db: Session,
) -> None:
    (
        creator,
        section,
        first_list,
        second_list,
        task,
    ) = _create_board_context(
        db,
    )

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.get(
        f"/sections/{section.id}",
    )

    assert response.status_code == 200

    html = response.text

    assert 'class="task-board"' in html
    assert "data-task-board" in html
    assert 'data-drag-enabled="true"' in html
    assert 'data-list-drag-enabled="true"' in html

    assert (
        f'data-list-id="{first_list.id}"'
        in html
    )

    assert (
        f'data-list-id="{second_list.id}"'
        in html
    )

    assert (
        f'data-task-id="{task.id}"'
        in html
    )

    assert "task-list-column" in html
    assert "task-card" in html


def test_sortable_board_uses_handles_without_native_draggable_attributes(
    client: TestClient,
    db: Session,
) -> None:
    (
        creator,
        section,
        _,
        _,
        _,
    ) = _create_board_context(
        db,
    )

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.get(
        f"/sections/{section.id}",
    )

    assert response.status_code == 200

    assert response.text.count(
        "data-list-drag-handle",
    ) == 2

    assert response.text.count(
        "data-task-drag-handle",
    ) == 1

    assert (
        "data-task-list-container"
        in response.text
    )

    assert 'draggable="true"' not in response.text


def test_section_page_loads_sortable_before_task_board_script(
    client: TestClient,
    db: Session,
) -> None:
    (
        creator,
        section,
        _,
        _,
        _,
    ) = _create_board_context(
        db,
    )

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.get(
        f"/sections/{section.id}",
    )

    assert response.status_code == 200

    sortable_position = response.text.index(
        "vendor/sortablejs/Sortable.min.js",
    )

    task_board_position = response.text.index(
        "js/task-board.js",
    )

    assert sortable_position < task_board_position


def test_task_card_renders_compact_local_due_datetime(
    client: TestClient,
    db: Session,
) -> None:
    (
        creator,
        section,
        _,
        _,
        task,
    ) = _create_board_context(
        db,
    )

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.get(
        f"/sections/{section.id}",
    )

    assert response.status_code == 200
    assert task.title in response.text
    assert "Due 12:00 07/08/26" in response.text

    assert (
        'datetime="2026-08-07T11:00:00+00:00"'
        in response.text
    )


def test_task_content_remains_inside_task_card_markup(
    client: TestClient,
    db: Session,
) -> None:
    (
        creator,
        section,
        _,
        _,
        task,
    ) = _create_board_context(
        db,
    )

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.get(
        f"/sections/{section.id}",
    )

    assert response.status_code == 200

    card_marker = (
        f'data-task-id="{task.id}"'
    )

    card_start = response.text.index(
        card_marker,
    )

    card_end = response.text.index(
        "</article>",
        card_start,
    )

    card_html = response.text[
        card_start:card_end
    ]

    assert task.title in card_html
    assert task.description in card_html
    assert "task-card-title" in card_html
    assert "task-card-description" in card_html


def test_section_summary_is_full_width_and_below_board(
    client: TestClient,
    db: Session,
) -> None:
    (
        creator,
        section,
        _,
        _,
        _,
    ) = _create_board_context(
        db,
    )

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.get(
        f"/sections/{section.id}",
    )

    assert response.status_code == 200

    board_position = response.text.index(
        "data-task-board",
    )

    summary_position = response.text.index(
        'class="content-card section-summary-card"',
    )

    assert board_position < summary_position

    assert (
        'id="section-members-heading"'
        not in response.text
    )


def test_active_filter_disables_sortable_handles(
    client: TestClient,
    db: Session,
) -> None:
    (
        creator,
        section,
        _,
        _,
        _,
    ) = _create_board_context(
        db,
    )

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.get(
        f"/sections/{section.id}",
        params={
            "search": "deliberately",
        },
    )

    assert response.status_code == 200
    assert 'class="task-filter-panel"' in response.text
    assert 'data-drag-enabled="false"' in response.text
    assert 'data-list-drag-enabled="false"' in response.text
    assert "Filters are currently applied." in response.text
    assert "data-list-drag-handle" not in response.text
    assert "data-task-drag-handle" not in response.text