import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from tests.factories import (
    create_administrator,
    create_auth_session,
    create_user,
)


ADMINISTRATION_PATHS = (
    "/admin",
    "/admin/users",
    "/admin/companies",
    "/admin/archived-companies",
    "/admin/archived-sections",
    "/admin/deleted-tasks",
    "/admin/audit",
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


@pytest.mark.parametrize(
    "path",
    ADMINISTRATION_PATHS,
)
def test_unauthenticated_user_cannot_access_phase6_administration(
    client: TestClient,
    path: str,
) -> None:
    response = client.get(
        path,
        headers={
            "accept": "text/html",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert response.headers[
        "location"
    ].startswith(
        "/login?next_url=",
    )


@pytest.mark.parametrize(
    "path",
    ADMINISTRATION_PATHS,
)
def test_standard_user_cannot_access_phase6_administration(
    client: TestClient,
    db: Session,
    path: str,
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
        path,
        follow_redirects=False,
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    "path",
    ADMINISTRATION_PATHS,
)
def test_administrator_can_access_phase6_administration(
    client: TestClient,
    db: Session,
    path: str,
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
        path,
        follow_redirects=False,
    )

    assert response.status_code == 200


def test_inactive_administrator_session_cannot_access_administration(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        is_active=False,
    )

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/admin",
        headers={
            "accept": "application/json",
        },
        follow_redirects=False,
    )

    assert response.status_code == 401


def test_anonymised_administrator_session_cannot_access_administration(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        is_active=False,
        is_anonymised=True,
    )

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/admin/audit",
        headers={
            "accept": "application/json",
        },
        follow_redirects=False,
    )

    assert response.status_code == 401


def test_standard_user_cannot_post_user_activation(
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

    _, session_token, csrf_token = (
        create_auth_session(
            db,
            user=actor,
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