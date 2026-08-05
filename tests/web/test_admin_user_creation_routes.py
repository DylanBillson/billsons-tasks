from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.constants import (
    AuditAction,
    GlobalRole,
)
from app.core.security import verify_password
from app.main import app
from app.models.audit_log import AuditLog
from app.models.user import User
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


def test_create_user_page_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        "/admin/users/create",
        headers={
            "accept": "text/html",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert response.headers["location"] == (
        "/login?next_url="
        "%2Fadmin%2Fusers%2Fcreate"
    )


def test_create_user_page_requires_administrator(
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
        "/admin/users/create",
        follow_redirects=False,
    )

    assert response.status_code == 403


def test_administrator_can_render_create_user_page(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/admin/users/create",
    )

    assert response.status_code == 200
    assert "Create User" in response.text
    assert 'class="checkbox-list-item"' in response.text
    assert 'name="username"' in response.text
    assert 'name="display_name"' in response.text
    assert 'name="password"' in response.text
    assert 'name="confirm_password"' in response.text
    assert 'name="global_role"' in response.text
    assert 'name="is_active"' in response.text
    assert csrf_token in response.text


def test_administrator_creates_active_standard_user(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    password = "Route-Created-Password-123!"

    response = client.post(
        "/admin/users/create",
        data={
            "csrf_token": csrf_token,
            "username": "  ROUTE-CREATED-USER  ",
            "display_name": "  Route Created User  ",
            "password": password,
            "confirm_password": password,
            "global_role": GlobalRole.USER.value,
            "is_active": "1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "/admin/users?"
    )

    user = db.scalar(
        select(User).where(
            User.username == "route-created-user",
        )
    )

    assert user is not None
    assert user.display_name == "Route Created User"
    assert user.global_role == GlobalRole.USER.value
    assert user.is_active is True
    assert user.is_anonymised is False

    assert verify_password(
        password,
        user.password_hash,
    )


def test_administrator_can_create_inactive_administrator(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    password = "Inactive-Route-Admin-123!"

    response = client.post(
        "/admin/users/create",
        data={
            "csrf_token": csrf_token,
            "username": "inactive-route-admin",
            "display_name": "Inactive Route Administrator",
            "password": password,
            "confirm_password": password,
            "global_role": (
                GlobalRole.ADMINISTRATOR.value
            ),
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    user = db.scalar(
        select(User).where(
            User.username == "inactive-route-admin",
        )
    )

    assert user is not None
    assert user.global_role == (
        GlobalRole.ADMINISTRATOR.value
    )
    assert user.is_active is False


def test_create_user_records_audit_log_without_password(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    password = "Never-Store-Route-Password-123!"

    response = client.post(
        "/admin/users/create",
        data={
            "csrf_token": csrf_token,
            "username": "route-audited-user",
            "display_name": "Route Audited User",
            "password": password,
            "confirm_password": password,
            "global_role": GlobalRole.USER.value,
            "is_active": "1",
        },
        headers={
            "user-agent": "User creation route test",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    user = db.scalar(
        select(User).where(
            User.username == "route-audited-user",
        )
    )

    assert user is not None

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action
            == AuditAction.USER_CREATED.value,
            AuditLog.entity_type == "user",
            AuditLog.entity_id == user.id,
        )
    )

    assert audit_log is not None
    assert audit_log.user_id == administrator.id
    assert audit_log.metadata_json == {
        "username": "route-audited-user",
        "display_name": "Route Audited User",
        "global_role": GlobalRole.USER.value,
        "is_active": True,
    }

    serialised_audit = (
        f"{audit_log.summary} "
        f"{audit_log.metadata_json}"
    )

    assert password not in serialised_audit
    assert "confirm_password" not in serialised_audit


def test_create_user_rejects_duplicate_username(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    existing_user = create_user(
        db,
        username="existing-route-user",
    )

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    password = "Duplicate-Route-Password-123!"

    response = client.post(
        "/admin/users/create",
        data={
            "csrf_token": csrf_token,
            "username": "EXISTING-ROUTE-USER",
            "display_name": "Duplicate Route User",
            "password": password,
            "confirm_password": password,
            "global_role": GlobalRole.USER.value,
            "is_active": "1",
        },
    )

    assert response.status_code == 422
    assert "username already exists" in response.text

    matching_users = list(
        db.scalars(
            select(User).where(
                User.username
                == "existing-route-user",
            )
        ).all()
    )

    assert matching_users == [
        existing_user,
    ]


def test_create_user_rejects_mismatched_passwords(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        "/admin/users/create",
        data={
            "csrf_token": csrf_token,
            "username": "mismatched-route-user",
            "display_name": "Mismatched Route User",
            "password": "First-Route-Password-123!",
            "confirm_password": (
                "Different-Route-Password-123!"
            ),
            "global_role": GlobalRole.USER.value,
            "is_active": "1",
        },
    )

    assert response.status_code == 422
    assert "passwords do not match" in response.text

    user = db.scalar(
        select(User).where(
            User.username
            == "mismatched-route-user",
        )
    )

    assert user is None


def test_create_user_rejects_invalid_role(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    password = "Invalid-Role-Password-123!"

    response = client.post(
        "/admin/users/create",
        data={
            "csrf_token": csrf_token,
            "username": "invalid-role-user",
            "display_name": "Invalid Role User",
            "password": password,
            "confirm_password": password,
            "global_role": "superuser",
            "is_active": "1",
        },
    )

    assert response.status_code == 422

    user = db.scalar(
        select(User).where(
            User.username == "invalid-role-user",
        )
    )

    assert user is None


def test_create_user_requires_csrf(
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

    password = "Missing-CSRF-Password-123!"

    response = client.post(
        "/admin/users/create",
        data={
            "username": "missing-csrf-user",
            "display_name": "Missing CSRF User",
            "password": password,
            "confirm_password": password,
            "global_role": GlobalRole.USER.value,
            "is_active": "1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 403

    user = db.scalar(
        select(User).where(
            User.username == "missing-csrf-user",
        )
    )

    assert user is None


def test_standard_user_cannot_submit_create_user_form(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=user,
    )

    password = "Unauthorised-Route-Password-123!"

    response = client.post(
        "/admin/users/create",
        data={
            "csrf_token": csrf_token,
            "username": "unauthorised-route-user",
            "display_name": "Unauthorised Route User",
            "password": password,
            "confirm_password": password,
            "global_role": GlobalRole.USER.value,
            "is_active": "1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 403

    created_user = db.scalar(
        select(User).where(
            User.username
            == "unauthorised-route-user",
        )
    )

    assert created_user is None