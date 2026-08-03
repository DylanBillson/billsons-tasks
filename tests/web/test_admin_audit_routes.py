from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.main import app
from app.web.routes.admin_audit import (
    router as admin_audit_router,
)
from tests.factories import (
    create_administrator,
    create_audit_log,
    create_auth_session,
    create_user,
)


def _route_is_registered(
    *,
    path: str,
    name: str,
) -> bool:
    return any(
        route.path == path
        and route.name == name
        for route in app.routes
    )


if not _route_is_registered(
    path="/admin/audit",
    name="admin_audit",
):
    app.include_router(
        admin_audit_router,
    )


def _authenticate(
    client: TestClient,
    db: Session,
    *,
    user,
) -> None:
    _, session_token, csrf_token = (
        create_auth_session(
            db,
            user=user,
        )
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


def test_audit_index_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        "/admin/audit",
        headers={
            "accept": "text/html",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert response.headers[
        "location"
    ] == (
        "/login?next_url=%2Fadmin%2Faudit"
    )


def test_audit_index_requires_administrator(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        "/admin/audit",
        follow_redirects=False,
    )

    assert response.status_code == 403


def test_administrator_views_audit_index(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    audit_log = create_audit_log(
        db,
        action="task_created",
        summary="A route task was created.",
        user=administrator,
        entity_type="task",
        entity_id=42,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/admin/audit",
    )

    assert response.status_code == 200
    assert "Audit Log" in response.text
    assert audit_log.summary in response.text
    assert audit_log.action in response.text
    assert administrator.display_name in response.text


def test_audit_index_renders_system_event(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    create_audit_log(
        db,
        action="notification_failed",
        summary="A notification failed.",
        user=None,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/admin/audit",
    )

    assert response.status_code == 200
    assert "A notification failed." in response.text
    assert "System" in response.text


def test_administrator_views_audit_detail(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    audit_log = create_audit_log(
        db,
        action="task_updated",
        summary="A task was updated.",
        user=administrator,
        entity_type="task",
        entity_id=84,
        metadata_json={
            "field": "title",
            "previous_value": "Old title",
            "value": "New title",
        },
        ip_address="192.0.2.140",
        user_agent="pytest audit routes",
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        f"/admin/audit/{audit_log.id}",
    )

    assert response.status_code == 200
    assert f"Audit Entry {audit_log.id}" in response.text
    assert audit_log.summary in response.text
    assert "task_updated" in response.text
    assert "192.0.2.140" in response.text
    assert "pytest audit routes" in response.text
    assert "previous_value" in response.text
    assert "Old title" in response.text


def test_unknown_audit_detail_redirects(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/admin/audit/999999",
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert response.headers[
        "location"
    ].startswith(
        "/admin/audit?"
    )


def test_audit_index_renders_empty_state(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/admin/audit",
    )

    assert response.status_code == 200

    assert (
        "Audit activity will appear here"
        in response.text
    )