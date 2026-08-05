from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import APP_VERSION, settings
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



def test_phase65_standard_user_header(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
        display_name="Phase 6.5 User",
    )
    _authenticate(client, db, user=user)

    response = client.get("/")

    assert response.status_code == 200
    assert f"v{APP_VERSION}" in response.text
    assert "Phase 6.5 User" in response.text
    assert "data-feedback-open" in response.text
    assert "app-admin-menu" not in response.text
    assert "Sign Out" in response.text


def test_phase65_administrator_controls_are_dropdown(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(db)
    _authenticate(client, db, user=administrator)

    response = client.get("/")

    assert response.status_code == 200
    assert '<details class="app-admin-menu">' in response.text
    assert "Administration" in response.text
    assert 'class="app-admin-menu-panel"' in response.text

    for path in (
        "/admin",
        "/admin/users",
        "/admin/companies",
        "/admin/archived-companies",
        "/admin/archived-sections",
        "/admin/deleted-tasks",
        "/admin/audit",
    ):
        assert f'href="http://testserver{path}"' in response.text


def test_phase65_primary_navigation_excludes_admin_links(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(db)
    _authenticate(client, db, user=administrator)

    response = client.get("/")

    navigation_start = response.text.index(
        'class="app-navigation"',
    )
    navigation_end = response.text.index(
        "</nav>",
        navigation_start,
    )
    navigation_html = response.text[
        navigation_start:navigation_end
    ]

    assert "Dashboard" in navigation_html
    assert "Companies" in navigation_html
    assert "My Tasks" in navigation_html
    assert "Audit Log" not in navigation_html
    assert "Archived Companies" not in navigation_html
