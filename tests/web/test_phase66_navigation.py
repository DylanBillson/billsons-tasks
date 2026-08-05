from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from html import unescape
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


def test_phase66_brand_is_not_duplicated(
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
        header_html.count(
            'class="app-brand-mark"',
        )
        == 1
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


def test_phase66_administration_menu_has_dropdown_hooks(
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
        "data-admin-menu"
        in response.text
    )

    assert (
        "data-admin-menu-toggle"
        in response.text
    )

    assert (
        "data-admin-menu-panel"
        in response.text
    )

    assert (
        "app-admin-menu-chevron"
        in response.text
    )


def test_phase66_administration_menu_contains_expected_links(
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

    expected_links = {
        "/admin": "Overview",
        "/admin/users": "Users",
        "/admin/companies": "Companies",
        "/admin/archived-companies": (
            "Archived Companies"
        ),
        "/admin/archived-sections": (
            "Archived Sections"
        ),
        "/admin/deleted-tasks": (
            "Deleted Tasks"
        ),
        "/admin/audit": "Audit Log",
    }

    for path, label in expected_links.items():
        assert (
            f'href="http://testserver{path}"'
            in response.text
        )

        assert label in response.text


def test_phase66_administration_menu_marks_active_page(
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

    audit_link_position = response.text.index(
        'href="http://testserver/admin/audit"',
    )

    audit_link_end = response.text.index(
        "</a>",
        audit_link_position,
    )

    audit_link_html = response.text[
        audit_link_position:
        audit_link_end
    ]

    assert (
        "app-admin-menu-link is-active"
        in audit_link_html
    )

    assert (
        'aria-current="page"'
        in audit_link_html
    )


def test_phase66_standard_user_cannot_see_admin_dropdown(
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
        "data-admin-menu"
        not in response.text
    )

    assert (
        "app-admin-menu-chevron"
        not in response.text
    )

    assert (
        "app-admin-menu-panel"
        not in response.text
    )


def test_phase66_login_page_keeps_single_brand(
    client: TestClient,
) -> None:
    response = client.get(
        "/login",
    )

    assert response.status_code == 200

    assert (
        response.text.count(
            'class="app-brand-mark"',
        )
        == 1
    )

    assert (
        'class="app-brand-text"'
        not in response.text
    )

    assert (
        "data-admin-menu"
        not in response.text
    )


def test_phase66_administration_toggle_starts_closed(
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

    menu_position = response.text.index(
        'class="app-admin-menu"',
    )

    menu_opening_tag_end = response.text.index(
        ">",
        menu_position,
    )

    menu_opening_tag = response.text[
        menu_position:
        menu_opening_tag_end
    ]

    assert " open" not in menu_opening_tag

    assert (
        'aria-expanded="false"'
        in response.text
    )