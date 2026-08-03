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


def test_standard_user_navigation(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(db)

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get("/")

    assert response.status_code == 200

    html = response.text

    assert "Dashboard" in html
    assert "Companies" in html
    assert "My Tasks" in html

    assert 'href="/admin"' not in html
    assert 'href="/admin/audit"' not in html
    assert 'href="/admin/deleted-tasks"' not in html
    assert 'href="/admin/archived-companies"' not in html
    assert 'href="/admin/archived-sections"' not in html


def test_administrator_navigation(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(db)

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get("/")

    assert response.status_code == 200

    html = response.text

    for label in (
        "Dashboard",
        "Companies",
        "My Tasks",
        "Overview",
        "Users",
        "Archived Companies",
        "Archived Sections",
        "Deleted Tasks",
        "Audit Log",
    ):
        assert label in html


def test_brand_links_to_dashboard_when_authenticated(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(db)

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get("/")

    assert 'class="app-brand"' in response.text
    assert 'href="http://testserver/"' in response.text


def test_header_displays_logged_in_user(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        display_name="Navigation Administrator",
    )

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get("/")

    assert response.status_code == 200

    assert "Navigation Administrator" in response.text
    assert "Administrator" in response.text
    assert "Sign Out" in response.text


def test_login_page_has_no_navigation(
    client: TestClient,
) -> None:
    response = client.get("/login")

    html = response.text

    assert "Dashboard" not in html
    assert "Companies" not in html
    assert "Audit Log" not in html