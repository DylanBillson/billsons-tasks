from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories.user_repository import (
    UserRepository,
)
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
):
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
        session_token,
        csrf_token,
    )


def test_complete_deactivate_reactivate_lifecycle(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target = create_user(
        db,
        username="phase-six-lifecycle-user",
    )

    target_session, _, _ = create_auth_session(
        db,
        user=target,
    )

    _, _, csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    deactivate_response = client.post(
        f"/admin/users/{target.id}/deactivate",
        data={
            "csrf_token": csrf_token,
            "confirm_deactivation": "1",
        },
        follow_redirects=False,
    )

    assert deactivate_response.status_code == 303

    db.refresh(
        target,
    )

    db.refresh(
        target_session,
    )

    assert target.is_active is False
    assert target_session.is_revoked is True

    activate_response = client.post(
        f"/admin/users/{target.id}/activate",
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert activate_response.status_code == 303

    db.refresh(
        target,
    )

    db.refresh(
        target_session,
    )

    assert target.is_active is True

    # Reactivation must not restore a previously revoked session.
    assert target_session.is_revoked is True


def test_deactivated_user_cannot_use_existing_session(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target = create_user(
        db,
    )

    _, target_token, _ = create_auth_session(
        db,
        user=target,
    )

    _, _, administrator_csrf = _authenticate(
        client,
        db,
        user=administrator,
    )

    client.post(
        f"/admin/users/{target.id}/deactivate",
        data={
            "csrf_token": administrator_csrf,
            "confirm_deactivation": "1",
        },
        follow_redirects=False,
    )

    client.cookies.set(
        settings.session_cookie_name,
        target_token,
    )

    response = client.get(
        "/",
        headers={
            "accept": "application/json",
        },
        follow_redirects=False,
    )

    assert response.status_code == 401


def test_anonymisation_requires_prior_deactivation(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target = create_user(
        db,
        is_active=True,
    )

    _, _, csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        f"/admin/users/{target.id}/anonymise",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "deactivated" in response.headers[
        "location"
    ].lower()


def test_complete_deactivate_then_anonymise_lifecycle(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target = create_user(
        db,
        username="phase-six-personal-name",
        display_name="Phase Six Personal Name",
    )

    target_id = target.id
    original_username = target.username
    original_display_name = target.display_name

    _, _, csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    deactivate_response = client.post(
        f"/admin/users/{target.id}/deactivate",
        data={
            "csrf_token": csrf_token,
            "confirm_deactivation": "1",
        },
        follow_redirects=False,
    )

    assert deactivate_response.status_code == 303

    anonymise_response = client.post(
        f"/admin/users/{target.id}/anonymise",
        data={
            "csrf_token": csrf_token,
            "confirmation_phrase": "ANONYMISE USER",
            "confirm_irreversible": "1",
        },
        follow_redirects=False,
    )

    assert anonymise_response.status_code == 303

    db.refresh(
        target,
    )

    assert target.is_active is False
    assert target.is_anonymised is True
    assert target.anonymised_at is not None

    assert target.username == (
        f"anonymised-user-{target_id:04d}"
    )

    assert target.display_name == (
        f"Anonymised User {target_id:04d}"
    )

    assert target.username != original_username
    assert target.display_name != original_display_name


def test_anonymised_user_cannot_be_reactivated(
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

    _, _, csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        f"/admin/users/{target.id}/activate",
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    db.refresh(
        target,
    )

    assert target.is_active is False
    assert target.is_anonymised is True


def test_anonymised_identity_cannot_authenticate(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="phase-six-anonymised-auth",
        is_active=False,
        is_anonymised=True,
    )

    result = (
        UserRepository.get_authenticatable_by_username(
            db,
            username=user.username,
        )
    )

    assert result is None


def test_administrator_cannot_deactivate_self(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    _, _, csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        (
            f"/admin/users/{administrator.id}"
            "/deactivate"
        ),
        data={
            "csrf_token": csrf_token,
            "confirm_deactivation": "1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    db.refresh(
        administrator,
    )

    assert administrator.is_active is True


def test_administrator_cannot_anonymise_self(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    _, _, csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        (
            f"/admin/users/{administrator.id}"
            "/anonymise"
        ),
        data={
            "csrf_token": csrf_token,
            "confirmation_phrase": "ANONYMISE USER",
            "confirm_irreversible": "1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    db.refresh(
        administrator,
    )

    assert administrator.is_anonymised is False