from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.constants import (
    AuditAction,
    GlobalRole,
)
from app.main import app
from app.models.audit_log import AuditLog
from app.web.routes.admin_users import (
    router as admin_users_router,
)
from tests.factories import (
    create_administrator,
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
    path="/admin/users",
    name="admin_users",
):
    app.include_router(
        admin_users_router,
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


def test_edit_user_page_requires_authentication(
    client: TestClient,
    db: Session,
) -> None:
    target_user = create_user(
        db,
    )

    db.commit()

    response = client.get(
        f"/admin/users/{target_user.id}/edit",
        headers={
            "accept": "text/html",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert response.headers["location"] == (
        "/login?next_url="
        f"%2Fadmin%2Fusers%2F{target_user.id}%2Fedit"
    )


def test_edit_user_page_requires_administrator(
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
        f"/admin/users/{target_user.id}/edit",
        follow_redirects=False,
    )

    assert response.status_code == 403


def test_administrator_can_render_edit_user_page(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target_user = create_user(
        db,
        username="render-edit-user",
        display_name="Render Edit User",
    )

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        f"/admin/users/{target_user.id}/edit",
    )

    assert response.status_code == 200
    assert "Edit User" in response.text
    assert "render-edit-user" in response.text
    assert "Render Edit User" in response.text
    assert 'name="username"' in response.text
    assert 'name="display_name"' in response.text
    assert 'name="global_role"' in response.text
    assert csrf_token in response.text


def test_administrator_updates_user_identity_and_role(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target_user = create_user(
        db,
        username="before-route-edit",
        display_name="Before Route Edit",
        global_role=GlobalRole.USER.value,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        f"/admin/users/{target_user.id}/edit",
        data={
            "csrf_token": csrf_token,
            "username": "AFTER-ROUTE-EDIT",
            "display_name": "After Route Edit",
            "global_role": (
                GlobalRole.ADMINISTRATOR.value
            ),
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "/admin/users?"
    )

    db.refresh(
        target_user,
    )

    assert target_user.username == "after-route-edit"
    assert target_user.display_name == "After Route Edit"
    assert target_user.global_role == (
        GlobalRole.ADMINISTRATOR.value
    )


def test_edit_user_records_audit_log(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target_user = create_user(
        db,
        username="audit-before-edit",
        display_name="Audit Before Edit",
        global_role=GlobalRole.USER.value,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        f"/admin/users/{target_user.id}/edit",
        data={
            "csrf_token": csrf_token,
            "username": "audit-after-edit",
            "display_name": "Audit After Edit",
            "global_role": (
                GlobalRole.ADMINISTRATOR.value
            ),
        },
        headers={
            "user-agent": "User editing route test",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action
            == AuditAction.USER_UPDATED.value,
            AuditLog.entity_type == "user",
            AuditLog.entity_id == target_user.id,
        )
    )

    assert audit_log is not None
    assert audit_log.user_id == administrator.id

    assert audit_log.metadata_json["changes"] == {
        "username": {
            "previous": "audit-before-edit",
            "current": "audit-after-edit",
        },
        "display_name": {
            "previous": "Audit Before Edit",
            "current": "Audit After Edit",
        },
        "global_role": {
            "previous": GlobalRole.USER.value,
            "current": (
                GlobalRole.ADMINISTRATOR.value
            ),
        },
    }


def test_edit_user_rejects_duplicate_username(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target_user = create_user(
        db,
        username="route-edit-target",
        display_name="Route Edit Target",
    )

    create_user(
        db,
        username="route-existing-user",
    )

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        f"/admin/users/{target_user.id}/edit",
        data={
            "csrf_token": csrf_token,
            "username": "ROUTE-EXISTING-USER",
            "display_name": "Route Edit Target",
            "global_role": GlobalRole.USER.value,
        },
    )

    assert response.status_code == 422
    assert "username already exists" in response.text

    db.refresh(
        target_user,
    )

    assert target_user.username == "route-edit-target"


def test_edit_user_allows_unchanged_username(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target_user = create_user(
        db,
        username="unchanged-route-username",
        display_name="Old Route Display Name",
    )

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        f"/admin/users/{target_user.id}/edit",
        data={
            "csrf_token": csrf_token,
            "username": "UNCHANGED-ROUTE-USERNAME",
            "display_name": "New Route Display Name",
            "global_role": GlobalRole.USER.value,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    db.refresh(
        target_user,
    )

    assert (
        target_user.username
        == "unchanged-route-username"
    )

    assert (
        target_user.display_name
        == "New Route Display Name"
    )


def test_administrator_cannot_remove_own_role(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        username="self-route-admin",
        display_name="Self Route Administrator",
    )

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        f"/admin/users/{administrator.id}/edit",
        data={
            "csrf_token": csrf_token,
            "username": administrator.username,
            "display_name": administrator.display_name,
            "global_role": GlobalRole.USER.value,
        },
    )

    assert response.status_code == 422

    assert (
        "cannot remove your own administrator role"
        in response.text
    )

    db.refresh(
        administrator,
    )

    assert administrator.global_role == (
        GlobalRole.ADMINISTRATOR.value
    )


def test_administrator_can_edit_own_display_name(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        username="self-display-admin",
        display_name="Old Self Display Name",
    )

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        f"/admin/users/{administrator.id}/edit",
        data={
            "csrf_token": csrf_token,
            "username": administrator.username,
            "display_name": "New Self Display Name",
            "global_role": (
                GlobalRole.ADMINISTRATOR.value
            ),
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    db.refresh(
        administrator,
    )

    assert (
        administrator.display_name
        == "New Self Display Name"
    )


def test_anonymised_user_cannot_be_edited(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target_user = create_user(
        db,
        is_anonymised=True,
        is_active=False,
    )

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        f"/admin/users/{target_user.id}/edit",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "/admin/users?"
    )


def test_edit_missing_user_redirects_to_user_list(
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
        "/admin/users/999999/edit",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "/admin/users?"
    )


def test_edit_user_requires_csrf(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target_user = create_user(
        db,
        username="csrf-edit-target",
        display_name="CSRF Edit Target",
    )

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        f"/admin/users/{target_user.id}/edit",
        data={
            "username": "csrf-edit-changed",
            "display_name": "CSRF Edit Changed",
            "global_role": GlobalRole.USER.value,
        },
        follow_redirects=False,
    )

    assert response.status_code == 403

    db.refresh(
        target_user,
    )

    assert target_user.username == "csrf-edit-target"
    assert target_user.display_name == "CSRF Edit Target"


def test_standard_user_cannot_submit_edit_user_form(
    client: TestClient,
    db: Session,
) -> None:
    acting_user = create_user(
        db,
    )

    target_user = create_user(
        db,
        username="protected-route-user",
        display_name="Protected Route User",
    )

    csrf_token = _authenticate(
        client,
        db,
        user=acting_user,
    )

    response = client.post(
        f"/admin/users/{target_user.id}/edit",
        data={
            "csrf_token": csrf_token,
            "username": "hijacked-route-user",
            "display_name": "Hijacked Route User",
            "global_role": (
                GlobalRole.ADMINISTRATOR.value
            ),
        },
        follow_redirects=False,
    )

    assert response.status_code == 403

    db.refresh(
        target_user,
    )

    assert target_user.username == "protected-route-user"
    assert target_user.display_name == "Protected Route User"
    assert target_user.global_role == GlobalRole.USER.value