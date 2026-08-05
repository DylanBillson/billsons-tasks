from pathlib import Path

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


def _create_board(
    db: Session,
):
    creator = create_user(
        db,
    )

    company = create_company(
        db,
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
    )

    first_list = create_section_list(
        db,
        section=section,
        name="First",
        sort_position=1000,
    )

    second_list = create_section_list(
        db,
        section=section,
        name="Second",
        sort_position=2000,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    db.commit()

    return (
        creator,
        section,
        first_list,
        second_list,
        task,
    )


def test_phase66_board_exposes_sortable_configuration(
    client: TestClient,
    db: Session,
) -> None:
    (
        creator,
        section,
        _,
        _,
        _,
    ) = _create_board(
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

    for attribute in (
        "data-task-board",
        "data-section-id",
        "data-reorder-url",
        "data-list-reorder-url",
        "data-csrf-token",
        'data-drag-enabled="true"',
        'data-list-drag-enabled="true"',
    ):
        assert attribute in response.text


def test_phase66_dragging_is_handle_only(
    client: TestClient,
    db: Session,
) -> None:
    (
        creator,
        section,
        _,
        _,
        _,
    ) = _create_board(
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

    assert "data-list-drag-handle" in response.text
    assert "data-task-drag-handle" in response.text
    assert 'draggable="true"' not in response.text


def test_phase66_sortable_vendor_asset_is_served(
    client: TestClient,
) -> None:
    response = client.get(
        "/static/vendor/sortablejs/Sortable.min.js",
    )

    assert response.status_code == 200
    assert len(response.content) > 1000


def test_phase66_sortable_licence_is_present() -> None:
    licence_path = Path(
        "app/web/static/vendor/sortablejs/LICENSE",
    )

    assert licence_path.is_file()

    licence_text = licence_path.read_text(
        encoding="utf-8",
    )

    assert "MIT License" in licence_text


def test_phase66_task_board_script_uses_sortablejs() -> None:
    script_path = Path(
        "app/web/static/js/task-board.js",
    )

    script = script_path.read_text(
        encoding="utf-8",
    )

    assert "window.Sortable" in script
    assert "new window.Sortable" in script

    assert (
        'handle: (\n'
        '                        "[data-task-drag-handle]"'
        in script
        or "[data-task-drag-handle]" in script
    )

    assert "[data-list-drag-handle]" in script

    for setting in (
        "animation:",
        "scroll:",
        "scrollSensitivity:",
        "scrollSpeed:",
        "ghostClass:",
        "chosenClass:",
        "dragClass:",
    ):
        assert setting in script


def test_phase66_task_board_script_has_no_native_drag_listeners() -> None:
    script = Path(
        "app/web/static/js/task-board.js",
    ).read_text(
        encoding="utf-8",
    )

    assert '"dragstart"' not in script
    assert '"dragover"' not in script
    assert '"dragleave"' not in script
    assert '"drop"' not in script


def test_phase66_sortable_visual_classes_are_defined() -> None:
    board_css = Path(
        "app/web/static/css/components/task-board.css",
    ).read_text(
        encoding="utf-8",
    )

    card_css = Path(
        "app/web/static/css/components/task-cards.css",
    ).read_text(
        encoding="utf-8",
    )

    for class_name in (
        ".task-list-sortable-ghost",
        ".task-list-sortable-chosen",
        ".task-list-sortable-drag",
        ".task-card-sortable-ghost",
        ".task-card-sortable-chosen",
        ".task-card-sortable-drag",
        ".is-insertion-before",
        ".is-insertion-after",
        ".is-task-drop-target",
    ):
        assert (
            class_name in board_css
            or class_name in card_css
        )