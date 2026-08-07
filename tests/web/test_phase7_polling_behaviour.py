from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
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


def _create_context(
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
    )

    section = create_section(
        db,
        company=company,
        created_by=creator,
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
    )

    db.commit()

    return (
        creator,
        section,
        task,
    )


def test_phase7_authenticated_pages_load_live_update_script(
    client: TestClient,
    db: Session,
) -> None:
    creator, section, task = _create_context(
        db,
    )

    _authenticate(
        client,
        db,
        user=creator,
    )

    section_response = client.get(
        f"/sections/{section.id}",
    )

    task_response = client.get(
        f"/tasks/{task.id}",
    )

    assert section_response.status_code == 200
    assert task_response.status_code == 200

    assert (
        "js/live-updates.js"
        in section_response.text
    )

    assert (
        "js/live-updates.js"
        in task_response.text
    )

    assert (
        "window.billsonsLiveUpdates"
        in section_response.text
    )

    assert (
        "window.billsonsLiveUpdates"
        in task_response.text
    )


def test_phase7_page_exposes_configured_poll_interval(
    client: TestClient,
    db: Session,
) -> None:
    creator, section, _ = _create_context(
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

    assert (
        (
            "pollIntervalSeconds: "
            f"{settings.live_updates_poll_interval_seconds}"
        )
        in response.text
    )


def test_phase7_revision_endpoint_disables_caching(
    client: TestClient,
    db: Session,
) -> None:
    creator, section, _ = _create_context(
        db,
    )

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.get(
        (
            "/api/live-updates/sections/"
            f"{section.id}/revision"
        ),
    )

    assert response.status_code == 200

    assert response.headers["cache-control"] == (
        "no-store, no-cache, must-revalidate"
    )


def test_phase7_polling_pauses_for_hidden_tabs() -> None:
    script = Path(
        "app/web/static/js/live-updates.js",
    ).read_text(
        encoding="utf-8",
    )

    assert "document.hidden" in script


def test_phase7_polling_pauses_during_board_activity() -> None:
    script = Path(
        "app/web/static/js/live-updates.js",
    ).read_text(
        encoding="utf-8",
    )

    for state in (
        "is-dragging-task",
        "is-dragging-list",
        "is-preparing-task-drag",
        "is-preparing-list-drag",
        "is-saving-order",
    ):
        assert state in script

    assert "aria-busy" in script


def test_phase7_polling_defers_refresh_while_editing() -> None:
    script = Path(
        "app/web/static/js/live-updates.js",
    ).read_text(
        encoding="utf-8",
    )

    assert "shouldDeferRefresh" in script

    assert (
        "HTMLInputElement"
        in script
    )

    assert (
        "HTMLTextAreaElement"
        in script
    )

    assert (
        "HTMLSelectElement"
        in script
    )


def test_phase7_polling_uses_same_origin_and_no_store() -> None:
    script = Path(
        "app/web/static/js/live-updates.js",
    ).read_text(
        encoding="utf-8",
    )

    assert (
        'credentials: "same-origin"'
        in script
    )

    assert (
        'cache: "no-store"'
        in script
    )

    assert "known_revision" in script


def test_phase7_polling_exposes_conflict_coordination_api() -> None:
    script = Path(
        "app/web/static/js/live-updates.js",
    ).read_text(
        encoding="utf-8",
    )

    assert "window.BillsonsLiveUpdates" in script
    assert "refreshRevision" in script
    assert "markConflict" in script


def test_phase7_polling_has_offline_and_error_states() -> None:
    script = Path(
        "app/web/static/js/live-updates.js",
    ).read_text(
        encoding="utf-8",
    )

    assert "navigator.onLine" in script
    assert '"offline"' in script
    assert '"error"' in script
    assert '"conflict"' in script