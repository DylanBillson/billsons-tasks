from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from html import unescape
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
) -> None:
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


def test_standard_user_navigation(
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

    html = response.text

    assert (
        'href="http://testserver/"'
        in html
    )

    assert (
        'href="http://testserver/companies"'
        in html
    )

    assert (
        'href="http://testserver/my-tasks"'
        in html
    )

    assert "Dashboard" in html
    assert "Companies" in html
    assert "My Tasks" in html

    assert "app-admin-menu" not in html
    assert "data-admin-menu" not in html

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
            not in html
        )


def test_administrator_navigation_uses_dropdown(
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

    html = response.text

    assert (
        'class="app-admin-menu"'
        in html
    )

    assert "data-admin-menu" in html
    assert "data-admin-menu-toggle" in html
    assert "data-admin-menu-panel" in html

    assert (
        'aria-haspopup="menu"'
        in html
    )

    assert (
        'aria-expanded="false"'
        in html
    )

    assert (
        'class="app-admin-menu-chevron"'
        in html
    )

    assert (
        'class="app-admin-menu-panel"'
        in html
    )

    assert "Administration" in html

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
            in html
        )

    for label in (
        "Overview",
        "Users",
        "Companies",
        "Archived Companies",
        "Archived Sections",
        "Deleted Tasks",
        "Audit Log",
    ):
        assert label in html


def test_administration_links_are_not_in_primary_navigation(
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

    primary_navigation_start = response.text.index(
        'class="app-navigation"',
    )

    primary_navigation_end = response.text.index(
        "</nav>",
        primary_navigation_start,
    )

    primary_navigation = response.text[
        primary_navigation_start:
        primary_navigation_end
    ]

    assert "Dashboard" in primary_navigation
    assert "Companies" in primary_navigation
    assert "My Tasks" in primary_navigation

    assert "Archived Companies" not in primary_navigation
    assert "Archived Sections" not in primary_navigation
    assert "Deleted Tasks" not in primary_navigation
    assert "Audit Log" not in primary_navigation


def test_brand_links_to_dashboard_when_authenticated(
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

    assert (
        'class="app-brand"'
        in response.text
    )

    assert (
        'href="http://testserver/"'
        in response.text
    )


def test_header_displays_single_visible_application_name(
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

    header_start = response.text.index(
        '<header class="app-header">',
    )

    header_end = response.text.index(
        "</header>",
        header_start,
    )

    header_html = response.text[
        header_start:
        header_end
    ]

    assert (
        'class="app-brand-mark"'
        in header_html
    )

    assert (
        'class="app-brand-text"'
        not in header_html
    )

    brand_start = header_html.index(
        'class="app-brand-mark"',
    )

    brand_end = header_html.index(
        "</span>",
        brand_start,
    )

    brand_html = header_html[
        brand_start:
        brand_end
    ]

    assert settings.app_name in unescape(
        brand_html,
    )


def test_header_displays_application_version(
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
        f"v{APP_VERSION}"
        in response.text
    )

    assert (
        f"Application version {APP_VERSION}"
        in response.text
    )


def test_header_displays_logged_in_user_and_actions(
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

    response = client.get(
        "/",
    )

    assert response.status_code == 200

    assert (
        "Navigation Administrator"
        in response.text
    )

    assert "Administrator" in response.text
    assert "Feedback" in response.text
    assert "Sign Out" in response.text


def test_standard_user_sees_feedback_but_not_admin_dropdown(
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
        "data-feedback-open"
        in response.text
    )

    assert (
        "data-admin-menu"
        not in response.text
    )

    assert (
        "app-admin-menu-chevron"
        not in response.text
    )


def test_login_page_has_no_authenticated_navigation_or_feedback(
    client: TestClient,
) -> None:
    response = client.get(
        "/login",
    )

    assert response.status_code == 200

    html = response.text

    assert "My Tasks" not in html
    assert "Audit Log" not in html
    assert "data-feedback-open" not in html
    assert "data-feedback-modal" not in html
    assert "data-admin-menu" not in html
    assert "app-admin-menu-chevron" not in html