from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.constants import GlobalRole
from app.models.audit_log import AuditLog
from app.models.user import User
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


def test_standard_user_cannot_access_user_management_pages(
    client: TestClient,
    db: Session,
) -> None:
    actor = create_user(
        db,
    )

    target = create_user(
        db,
    )

    _authenticate(
        client,
        db,
        user=actor,
    )

    for path in (
        "/admin/users",
        "/admin/users/create",
        f"/admin/users/{target.id}/edit",
        f"/admin/users/{target.id}/reset-password",
        f"/admin/users/{target.id}/deactivate",
        f"/admin/users/{target.id}/anonymise",
    ):
        response = client.get(
            path,
            follow_redirects=False,
        )

        assert response.status_code == 403


def test_standard_user_cannot_create_account_with_crafted_request(
    client: TestClient,
    db: Session,
) -> None:
    actor = create_user(
        db,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=actor,
    )

    password = "Crafted-Create-Password-123!"

    response = client.post(
        "/admin/users/create",
        data={
            "csrf_token": csrf_token,
            "username": "crafted-created-user",
            "display_name": "Crafted Created User",
            "password": password,
            "confirm_password": password,
            "global_role": (
                GlobalRole.ADMINISTRATOR.value
            ),
            "is_active": "1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 403

    created_user = db.scalar(
        select(User).where(
            User.username
            == "crafted-created-user",
        )
    )

    assert created_user is None


def test_standard_user_cannot_edit_account_with_crafted_request(
    client: TestClient,
    db: Session,
) -> None:
    actor = create_user(
        db,
    )

    target = create_user(
        db,
        username="isolated-edit-target",
        display_name="Isolated Edit Target",
        global_role=GlobalRole.USER.value,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=actor,
    )

    response = client.post(
        f"/admin/users/{target.id}/edit",
        data={
            "csrf_token": csrf_token,
            "username": "isolated-hijacked-target",
            "display_name": "Isolated Hijacked Target",
            "global_role": (
                GlobalRole.ADMINISTRATOR.value
            ),
        },
        follow_redirects=False,
    )

    assert response.status_code == 403

    db.refresh(
        target,
    )

    assert target.username == "isolated-edit-target"
    assert target.display_name == "Isolated Edit Target"
    assert target.global_role == GlobalRole.USER.value


def test_standard_user_cannot_activate_account_with_crafted_request(
    client: TestClient,
    db: Session,
) -> None:
    actor = create_user(
        db,
    )

    target = create_user(
        db,
        is_active=False,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=actor,
    )

    response = client.post(
        f"/admin/users/{target.id}/activate",
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 403

    db.refresh(
        target,
    )

    assert target.is_active is False


def test_standard_user_cannot_deactivate_account_with_crafted_request(
    client: TestClient,
    db: Session,
) -> None:
    actor = create_user(
        db,
    )

    target = create_user(
        db,
        is_active=True,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=actor,
    )

    response = client.post(
        f"/admin/users/{target.id}/deactivate",
        data={
            "csrf_token": csrf_token,
            "confirm_deactivation": "1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 403

    db.refresh(
        target,
    )

    assert target.is_active is True


def test_standard_user_cannot_anonymise_account_with_crafted_request(
    client: TestClient,
    db: Session,
) -> None:
    actor = create_user(
        db,
    )

    target = create_user(
        db,
        is_active=False,
        is_anonymised=False,
    )

    original_username = target.username
    original_display_name = target.display_name

    csrf_token = _authenticate(
        client,
        db,
        user=actor,
    )

    response = client.post(
        f"/admin/users/{target.id}/anonymise",
        data={
            "csrf_token": csrf_token,
            "confirmation_phrase": "ANONYMISE USER",
            "confirm_irreversible": "1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 403

    db.refresh(
        target,
    )

    assert target.is_anonymised is False
    assert target.username == original_username
    assert target.display_name == original_display_name


def test_missing_csrf_cannot_mutate_user_management_state(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target = create_user(
        db,
        username="csrf-isolated-target",
        display_name="CSRF Isolated Target",
        is_active=True,
    )

    _authenticate(
        client,
        db,
        user=administrator,
    )

    edit_response = client.post(
        f"/admin/users/{target.id}/edit",
        data={
            "username": "csrf-mutated-target",
            "display_name": "CSRF Mutated Target",
            "global_role": (
                GlobalRole.ADMINISTRATOR.value
            ),
        },
        follow_redirects=False,
    )

    deactivate_response = client.post(
        f"/admin/users/{target.id}/deactivate",
        data={
            "confirm_deactivation": "1",
        },
        follow_redirects=False,
    )

    assert edit_response.status_code == 403
    assert deactivate_response.status_code == 403

    db.refresh(
        target,
    )

    assert target.username == "csrf-isolated-target"
    assert target.display_name == "CSRF Isolated Target"
    assert target.global_role == GlobalRole.USER.value
    assert target.is_active is True


def test_failed_unauthorised_requests_create_no_user_audit_entries(
    client: TestClient,
    db: Session,
) -> None:
    actor = create_user(
        db,
    )

    target = create_user(
        db,
        username="audit-isolation-target",
    )

    csrf_token = _authenticate(
        client,
        db,
        user=actor,
    )

    audit_count_before = len(
        db.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "user",
                AuditLog.entity_id == target.id,
            )
        ).all()
    )

    response = client.post(
        f"/admin/users/{target.id}/edit",
        data={
            "csrf_token": csrf_token,
            "username": "audit-isolation-mutated",
            "display_name": "Audit Isolation Mutated",
            "global_role": (
                GlobalRole.ADMINISTRATOR.value
            ),
        },
        follow_redirects=False,
    )

    assert response.status_code == 403

    audit_count_after = len(
        db.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "user",
                AuditLog.entity_id == target.id,
            )
        ).all()
    )

    assert audit_count_after == audit_count_before


def test_administrator_cannot_edit_anonymised_user_by_posting_directly(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target = create_user(
        db,
        is_active=False,
        is_anonymised=True,
    )

    original_username = target.username
    original_display_name = target.display_name

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        f"/admin/users/{target.id}/edit",
        data={
            "csrf_token": csrf_token,
            "username": "restored-personal-username",
            "display_name": "Restored Personal Name",
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
        target,
    )

    assert target.username == original_username
    assert target.display_name == original_display_name
    assert target.is_anonymised is True


def test_administrator_cannot_remove_own_role_by_direct_post(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        username="isolation-self-admin",
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
        follow_redirects=False,
    )

    assert response.status_code == 422

    db.refresh(
        administrator,
    )

    assert administrator.global_role == (
        GlobalRole.ADMINISTRATOR.value
    )