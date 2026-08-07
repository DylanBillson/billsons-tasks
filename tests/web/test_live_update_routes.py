from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timezone import utc_now
from app.services.live_update_service import (
    LiveUpdateService,
)
from tests.factories import (
    create_auth_session,
    create_company,
    create_company_membership,
    create_section,
    create_section_list,
    create_task,
    create_task_comment,
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


def test_section_revision_endpoint_requires_authentication(
    client: TestClient,
    db: Session,
) -> None:
    _, section, _ = _create_context(
        db,
    )

    response = client.get(
        (
            "/api/live-updates/sections/"
            f"{section.id}/revision"
        ),
        headers={
            "accept": "application/json",
        },
        follow_redirects=False,
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Authentication is required.",
    }


def test_task_revision_endpoint_requires_authentication(
    client: TestClient,
    db: Session,
) -> None:
    _, _, task = _create_context(
        db,
    )

    response = client.get(
        (
            "/api/live-updates/tasks/"
            f"{task.id}/revision"
        ),
        headers={
            "accept": "text/html",
        },
        follow_redirects=False,
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Authentication is required.",
    }


def test_section_revision_endpoint_returns_revision(
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

    payload = response.json()

    assert payload["enabled"] is True
    assert payload["scope"] == "section"
    assert payload["resource_id"] == section.id
    assert payload["revision"]
    assert payload["changed"] is False

    assert payload["poll_interval_seconds"] == (
        settings.live_updates_poll_interval_seconds
    )

    assert response.headers["cache-control"] == (
        "no-store, no-cache, must-revalidate"
    )


def test_task_revision_endpoint_returns_revision(
    client: TestClient,
    db: Session,
) -> None:
    creator, _, task = _create_context(
        db,
    )

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.get(
        (
            "/api/live-updates/tasks/"
            f"{task.id}/revision"
        ),
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["scope"] == "task"
    assert payload["resource_id"] == task.id
    assert payload["revision"]
    assert payload["changed"] is False


def test_section_revision_reports_unchanged_known_revision(
    client: TestClient,
    db: Session,
) -> None:
    creator, section, _ = _create_context(
        db,
    )

    revision = LiveUpdateService.get_section_revision(
        db,
        actor=creator,
        section_id=section.id,
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
        params={
            "known_revision": revision.revision,
        },
    )

    assert response.status_code == 200

    assert response.json()["revision"] == (
        revision.revision
    )

    assert response.json()["changed"] is False


def test_section_revision_reports_changed_board(
    client: TestClient,
    db: Session,
) -> None:
    creator, section, task = _create_context(
        db,
    )

    revision = LiveUpdateService.get_section_revision(
        db,
        actor=creator,
        section_id=section.id,
    )

    task.title = "Changed elsewhere"
    task.updated_at = (
        utc_now()
        + timedelta(
            seconds=1,
        )
    )

    db.commit()

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
        params={
            "known_revision": revision.revision,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["changed"] is True
    assert payload["revision"] != revision.revision


def test_task_revision_reports_changed_comment(
    client: TestClient,
    db: Session,
) -> None:
    creator, _, task = _create_context(
        db,
    )

    revision = LiveUpdateService.get_task_revision(
        db,
        actor=creator,
        task_id=task.id,
    )

    create_task_comment(
        db,
        task=task,
        user=creator,
        body="A new comment.",
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.get(
        (
            "/api/live-updates/tasks/"
            f"{task.id}/revision"
        ),
        params={
            "known_revision": revision.revision,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["changed"] is True
    assert payload["revision"] != revision.revision


def test_missing_live_update_resource_returns_404(
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

    section_response = client.get(
        "/api/live-updates/sections/999999/revision",
    )

    task_response = client.get(
        "/api/live-updates/tasks/999999/revision",
    )

    assert section_response.status_code == 404
    assert task_response.status_code == 404


def test_disabled_live_updates_return_service_unavailable(
    client: TestClient,
    db: Session,
    monkeypatch,
) -> None:
    creator, section, _ = _create_context(
        db,
    )

    _authenticate(
        client,
        db,
        user=creator,
    )

    monkeypatch.setattr(
        settings,
        "live_updates_enabled",
        False,
    )

    response = client.get(
        (
            "/api/live-updates/sections/"
            f"{section.id}/revision"
        ),
    )

    assert response.status_code == 503

    assert response.json() == {
        "detail": "Live updates are disabled.",
        "code": "live_updates_disabled",
    }