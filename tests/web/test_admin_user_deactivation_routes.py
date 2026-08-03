from urllib.parse import (
    parse_qs,
    urlparse,
)

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import AuditAction
from app.models.audit_log import AuditLog
from app.models.session import AuthSession
from tests.factories import (
    create_administrator,
    create_auth_session,
    create_user,
)


def _authenticate(
    client: TestClient,
    db: Session,
    *,
    user,
) -> tuple[
    AuthSession,
    str,
]:
    auth_session, session_token, csrf_token = (
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

    return (
        auth_session,
        csrf_token,
    )


def test_deactivation_page_requires_authentication(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    db.commit()

    response = client.get(
        f"/admin/users/{user.id}/deactivate",
        headers={
            "accept": "text/html",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303


def test_deactivation_page_requires_administrator(
    client: TestClient,
    db: Session,
) -> None:
    acting_user = create_user(
        db,
    )

    target_user = create_user(
        db,
    )

    _authenticate(
        client,
        db,
        user=acting_user,
    )

    response = client.get(
        (
            f"/admin/users/{target_user.id}"
            "/deactivate"
        ),
        follow_redirects=False,
    )

    assert response.status_code == 403


def test_administrator_views_deactivation_confirmation(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target_user = create_user(
        db,
        username="deactivation-target",
        display_name="Deactivation Target",
    )

    _, csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        (
            f"/admin/users/{target_user.id}"
            "/deactivate"
        ),
    )

    assert response.status_code == 200
    assert "Deactivate User" in response.text
    assert target_user.display_name in response.text
    assert target_user.username in response.text
    assert csrf_token in response.text

    assert (
        'name="confirm_deactivation"'
        in response.text
    )


def test_deactivation_confirmation_rejects_current_user(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        (
            f"/admin/users/{administrator.id}"
            "/deactivate"
        ),
        follow_redirects=False,
    )

    assert response.status_code == 303

    parsed = urlparse(
        response.headers[
            "location"
        ],
    )

    query = parse_qs(
        parsed.query,
    )

    assert "own account" in query[
        "error"
    ][0]


def test_deactivation_submit_requires_confirmation(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target_user = create_user(
        db,
    )

    _, csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        (
            f"/admin/users/{target_user.id}"
            "/deactivate"
        ),
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert "Confirm the deactivation" in response.text

    db.refresh(
        target_user,
    )

    assert target_user.is_active is True


def test_administrator_deactivates_user(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target_user = create_user(
        db,
        username="route-deactivation-user",
    )

    target_session, _, _ = create_auth_session(
        db,
        user=target_user,
    )

    _, csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        (
            f"/admin/users/{target_user.id}"
            "/deactivate"
        ),
        data={
            "csrf_token": csrf_token,
            "confirm_deactivation": "1",
        },
        follow_redirects=False,
    )

    db.refresh(
        target_user,
    )

    db.refresh(
        target_session,
    )

    assert response.status_code == 303
    assert target_user.is_active is False
    assert target_session.is_revoked is True

    parsed = urlparse(
        response.headers[
            "location"
        ],
    )

    query = parse_qs(
        parsed.query,
    )

    assert parsed.path == "/admin/users"

    assert (
        "route-deactivation-user was deactivated"
        in query["success"][0]
    )


def test_deactivation_records_audit_log(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target_user = create_user(
        db,
        username="route-audit-user",
    )

    _, csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        (
            f"/admin/users/{target_user.id}"
            "/deactivate"
        ),
        data={
            "csrf_token": csrf_token,
            "confirm_deactivation": "1",
        },
        follow_redirects=False,
    )

    audit_log = db.scalar(
        select(
            AuditLog,
        ).where(
            AuditLog.action
            == AuditAction.USER_DEACTIVATED.value,
            AuditLog.entity_type
            == "user",
            AuditLog.entity_id
            == target_user.id,
        ),
    )

    assert response.status_code == 303
    assert audit_log is not None
    assert audit_log.user_id == administrator.id


def test_deactivation_requires_csrf(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target_user = create_user(
        db,
    )

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        (
            f"/admin/users/{target_user.id}"
            "/deactivate"
        ),
        data={
            "confirm_deactivation": "1",
        },
        follow_redirects=False,
    )

    db.refresh(
        target_user,
    )

    assert response.status_code == 403
    assert target_user.is_active is True


def test_inactive_user_can_be_reactivated(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target_user = create_user(
        db,
        username="reactivation-user",
        is_active=False,
    )

    _, csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        (
            f"/admin/users/{target_user.id}"
            "/activate"
        ),
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    db.refresh(
        target_user,
    )

    assert response.status_code == 303
    assert target_user.is_active is True


def test_deactivated_user_cannot_authenticate(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target_user = create_user(
        db,
        username="cannot-authenticate-user",
    )

    _, target_session_token, _ = (
        create_auth_session(
            db,
            user=target_user,
        )
    )

    _, csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    client.post(
        (
            f"/admin/users/{target_user.id}"
            "/deactivate"
        ),
        data={
            "csrf_token": csrf_token,
            "confirm_deactivation": "1",
        },
        follow_redirects=False,
    )

    client.cookies.set(
        settings.session_cookie_name,
        target_session_token,
    )

    response = client.get(
        "/companies",
        headers={
            "accept": "application/json",
        },
        follow_redirects=False,
    )

    assert response.status_code == 401


def test_user_list_links_to_deactivation_confirmation(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target_user = create_user(
        db,
    )

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/admin/users",
    )

    assert response.status_code == 200

    assert (
        f"/admin/users/{target_user.id}/deactivate"
        in response.text
    )