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


def test_standard_user_sees_primary_navigation(
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
        "/",
        "/companies",
        "/my-tasks",
    ):
        assert (
            f'href="http://testserver{path}"'
            in response.text
        )


def test_standard_user_does_not_see_administration_dropdown(
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
    assert "app-admin-menu" not in response.text

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


def test_administrator_sees_complete_administration_dropdown(
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
    assert "app-admin-menu" in response.text
    assert "Administration" in response.text

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
            in response.text
        )


def test_primary_navigation_active_state_on_my_tasks(
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
        'href="http://testserver/my-tasks"'
        in response.text
    )

    assert 'aria-current="page"' in response.text


def test_administration_dropdown_marks_active_page(
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
        "/admin/audit",
    )

    assert response.status_code == 200

    assert (
        'href="http://testserver/admin/audit"'
        in response.text
    )

    assert (
        "app-admin-menu-link is-active"
        in response.text
    )


def test_header_displays_current_user_and_controls(
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
    assert "Feedback" in response.text
    assert "Administration" in response.text
    assert "Sign Out" in response.text


def test_unauthenticated_login_page_has_no_protected_navigation(
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
        "Feedback",
        "Sign Out",
    ):
        assert label not in response.text