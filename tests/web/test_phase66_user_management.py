from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.constants import (
    AuditAction,
    GlobalRole,
)
from app.core.security import verify_password
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


def test_phase66_user_list_exposes_complete_management_actions(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    active_user = create_user(
        db,
        username="phase66-active-user",
        display_name="Phase 66 Active User",
        is_active=True,
    )

    inactive_user = create_user(
        db,
        username="phase66-inactive-user",
        display_name="Phase 66 Inactive User",
        is_active=False,
    )

    anonymised_user = create_user(
        db,
        username="phase66-anonymised-user",
        display_name="Phase 66 Anonymised User",
        is_active=False,
        is_anonymised=True,
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
        'href="http://testserver/admin/users/create"'
        in response.text
    )

    assert (
        f"/admin/users/{active_user.id}/edit"
        in response.text
    )

    assert (
        f"/admin/users/{active_user.id}/reset-password"
        in response.text
    )

    assert (
        f"/admin/users/{active_user.id}/deactivate"
        in response.text
    )

    assert (
        f"/admin/users/{inactive_user.id}/edit"
        in response.text
    )

    assert (
        f"/admin/users/{inactive_user.id}/activate"
        in response.text
    )

    assert (
        f"/admin/users/{inactive_user.id}/anonymise"
        in response.text
    )

    anonymised_marker = (
        f"Phase 66 Anonymised User"
    )

    anonymised_start = response.text.index(
        anonymised_marker,
    )

    anonymised_end = response.text.index(
        "</tr>",
        anonymised_start,
    )

    anonymised_row = response.text[
        anonymised_start:
        anonymised_end
    ]

    assert "No account actions available" in (
        anonymised_row
    )

    assert (
        f"/admin/users/{anonymised_user.id}/edit"
        not in anonymised_row
    )


def test_phase66_create_and_edit_pages_render_expected_controls(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target_user = create_user(
        db,
        username="phase66-edit-controls",
        display_name="Phase 66 Edit Controls",
    )

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    create_response = client.get(
        "/admin/users/create",
    )

    assert create_response.status_code == 200

    for field_name in (
        "username",
        "display_name",
        "password",
        "confirm_password",
        "global_role",
        "is_active",
    ):
        assert (
            f'name="{field_name}"'
            in create_response.text
        )

    assert csrf_token in create_response.text

    edit_response = client.get(
        f"/admin/users/{target_user.id}/edit",
    )

    assert edit_response.status_code == 200

    for field_name in (
        "username",
        "display_name",
        "global_role",
    ):
        assert (
            f'name="{field_name}"'
            in edit_response.text
        )

    assert 'name="password"' not in edit_response.text
    assert csrf_token in edit_response.text


def test_phase66_administrator_creates_and_edits_user(
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

    password = "Phase66-Management-Password-123!"

    create_response = client.post(
        "/admin/users/create",
        data={
            "csrf_token": csrf_token,
            "username": "PHASE66-MANAGED-USER",
            "display_name": "Phase 66 Managed User",
            "password": password,
            "confirm_password": password,
            "global_role": GlobalRole.USER.value,
            "is_active": "1",
        },
        follow_redirects=False,
    )

    assert create_response.status_code == 303

    user = db.scalar(
        select(User).where(
            User.username
            == "phase66-managed-user",
        )
    )

    assert user is not None
    assert verify_password(
        password,
        user.password_hash,
    )

    edit_response = client.post(
        f"/admin/users/{user.id}/edit",
        data={
            "csrf_token": csrf_token,
            "username": "phase66-updated-user",
            "display_name": "Phase 66 Updated User",
            "global_role": (
                GlobalRole.ADMINISTRATOR.value
            ),
        },
        follow_redirects=False,
    )

    assert edit_response.status_code == 303

    db.refresh(
        user,
    )

    assert user.username == "phase66-updated-user"
    assert user.display_name == "Phase 66 Updated User"
    assert user.global_role == (
        GlobalRole.ADMINISTRATOR.value
    )


def test_phase66_creation_and_editing_are_audited(
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

    password = "Phase66-Audit-Password-123!"

    create_response = client.post(
        "/admin/users/create",
        data={
            "csrf_token": csrf_token,
            "username": "phase66-audit-user",
            "display_name": "Phase 66 Audit User",
            "password": password,
            "confirm_password": password,
            "global_role": GlobalRole.USER.value,
            "is_active": "1",
        },
        follow_redirects=False,
    )

    assert create_response.status_code == 303

    user = db.scalar(
        select(User).where(
            User.username == "phase66-audit-user",
        )
    )

    assert user is not None

    edit_response = client.post(
        f"/admin/users/{user.id}/edit",
        data={
            "csrf_token": csrf_token,
            "username": "phase66-audit-updated",
            "display_name": "Phase 66 Audit Updated",
            "global_role": GlobalRole.USER.value,
        },
        follow_redirects=False,
    )

    assert edit_response.status_code == 303

    audit_logs = list(
        db.scalars(
            select(AuditLog)
            .where(
                AuditLog.entity_type == "user",
                AuditLog.entity_id == user.id,
                AuditLog.action.in_(
                    [
                        AuditAction.USER_CREATED.value,
                        AuditAction.USER_UPDATED.value,
                    ],
                ),
            )
            .order_by(
                AuditLog.id.asc(),
            )
        ).all()
    )

    assert [
        audit_log.action
        for audit_log in audit_logs
    ] == [
        AuditAction.USER_CREATED.value,
        AuditAction.USER_UPDATED.value,
    ]

    serialised_audit = " ".join(
        (
            f"{audit_log.summary} "
            f"{audit_log.metadata_json}"
        )
        for audit_log in audit_logs
    )

    assert password not in serialised_audit
    assert "password_hash" not in serialised_audit
    assert "confirm_password" not in serialised_audit


def test_phase66_duplicate_username_is_rejected_without_mutation(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    existing_user = create_user(
        db,
        username="phase66-existing-username",
    )

    editable_user = create_user(
        db,
        username="phase66-editable-username",
        display_name="Phase 66 Editable User",
    )

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        f"/admin/users/{editable_user.id}/edit",
        data={
            "csrf_token": csrf_token,
            "username": "PHASE66-EXISTING-USERNAME",
            "display_name": "Changed Display Name",
            "global_role": GlobalRole.USER.value,
        },
    )

    assert response.status_code == 422
    assert "username already exists" in response.text

    db.refresh(
        existing_user,
    )

    db.refresh(
        editable_user,
    )

    assert (
        existing_user.username
        == "phase66-existing-username"
    )

    assert (
        editable_user.username
        == "phase66-editable-username"
    )

    assert (
        editable_user.display_name
        == "Phase 66 Editable User"
    )


def test_phase66_password_is_not_repopulated_after_invalid_creation(
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

    password = "Phase66-Sensitive-Password-123!"

    response = client.post(
        "/admin/users/create",
        data={
            "csrf_token": csrf_token,
            "username": "phase66-invalid-password-form",
            "display_name": "Phase 66 Invalid Form",
            "password": password,
            "confirm_password": (
                "Different-Phase66-Password-123!"
            ),
            "global_role": GlobalRole.USER.value,
            "is_active": "1",
        },
    )

    assert response.status_code == 422
    assert password not in response.text

    assert (
        'name="password"'
        in response.text
    )

    assert (
        'name="confirm_password"'
        in response.text
    )