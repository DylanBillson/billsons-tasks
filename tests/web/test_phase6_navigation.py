from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
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


def test_standard_user_sees_phase6_primary_navigation(
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
        "/",
    )

    assert response.status_code == 200

    assert (
        'href="http://testserver/"'
        in response.text
    )

    assert (
        'href="http://testserver/companies"'
        in response.text
    )

    assert (
        'href="http://testserver/my-tasks"'
        in response.text
    )


def test_standard_user_does_not_see_administration_navigation(
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
        "/",
    )

    assert response.status_code == 200

    for path in (
        "/admin",
        "/admin/users",
        "/admin/companies",
        "/admin/archived-companies",
        "/admin/archived-sections",
        "/admin/deleted-tasks",
        "/admin/audit",
    ):
        assert (
            f'href="http://testserver{path}"'
            not in response.text
        )


def test_administrator_sees_complete_phase6_navigation(
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
        "/",
    )

    assert response.status_code == 200

    for path in (
        "/",
        "/companies",
        "/my-tasks",
        "/admin",
        "/admin/users",
        "/admin/companies",
        "/admin/archived-companies",
        "/admin/archived-sections",
        "/admin/deleted-tasks",
        "/admin/audit",
    ):
        assert (
            f'href="http://testserver{path}"'
            in response.text
        )


def test_phase6_navigation_active_state_on_my_tasks(
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
        "/my-tasks",
    )

    assert response.status_code == 200

    assert (
        'class="app-navigation-link is-active"'
        in response.text
    )

    assert "My Tasks" in response.text


def test_phase6_navigation_active_state_on_administration(
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
        "/admin",
    )

    assert response.status_code == 200

    assert (
        'href="http://testserver/admin"'
        in response.text
    )

    assert "Overview" in response.text


def test_phase6_header_displays_current_user(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        display_name="Phase Six Administrator",
    )

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/admin",
    )

    assert response.status_code == 200
    assert "Phase Six Administrator" in response.text
    assert "Administrator" in response.text
    assert "Sign Out" in response.text


def test_unauthenticated_login_page_has_no_phase6_navigation(
    client: TestClient,
) -> None:
    response = client.get(
        "/login",
    )

    assert response.status_code == 200

    for label in (
        "My Tasks",
        "Archived Companies",
        "Archived Sections",
        "Deleted Tasks",
        "Audit Log",
    ):
        assert label not in response.text