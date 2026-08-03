from urllib.parse import (
    parse_qs,
    urlparse,
)

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import AuditAction
from app.main import app
from app.models.audit_log import AuditLog
from app.web.routes.admin_archived_sections import (
    router as archived_sections_router,
)
from tests.factories import (
    create_administrator,
    create_auth_session,
    create_company,
    create_section,
    create_user,
)


def _route_is_registered(
    *,
    path: str,
    name: str,
) -> bool:
    return any(
        route.path == path
        and route.name == name
        for route in app.routes
    )


if not _route_is_registered(
    path="/admin/archived-sections",
    name="admin_archived_sections",
):
    app.include_router(
        archived_sections_router,
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


def test_archived_sections_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        "/admin/archived-sections",
        headers={
            "accept": "text/html",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303


def test_archived_sections_requires_administrator(
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
        "/admin/archived-sections",
        follow_redirects=False,
    )

    assert response.status_code == 403


def test_archived_sections_lists_only_archived_records(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    company = create_company(
        db,
    )

    archived = create_section(
        db,
        company=company,
        created_by=creator,
        name="Visible Archived Section",
        is_archived=True,
    )

    active = create_section(
        db,
        company=company,
        created_by=creator,
        name="Hidden Active Section",
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/admin/archived-sections",
    )

    assert response.status_code == 200
    assert archived.name in response.text
    assert active.name not in response.text


def test_archived_sections_filters_by_company(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    first_company = create_company(
        db,
        name="First Filter Company",
    )

    second_company = create_company(
        db,
        name="Second Filter Company",
    )

    visible = create_section(
        db,
        company=first_company,
        created_by=creator,
        name="Visible Filter Section",
        is_archived=True,
    )

    hidden = create_section(
        db,
        company=second_company,
        created_by=creator,
        name="Hidden Filter Section",
        is_archived=True,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        (
            "/admin/archived-sections"
            f"?company_id={first_company.id}"
        ),
    )

    assert response.status_code == 200
    assert visible.name in response.text
    assert hidden.name not in response.text


def test_archived_sections_searches_section_and_company(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    matching_company = create_company(
        db,
        name="Lighthouse Company",
    )

    other_company = create_company(
        db,
        name="Other Company",
    )

    company_match = create_section(
        db,
        company=matching_company,
        created_by=creator,
        name="Operations",
        is_archived=True,
    )

    section_match = create_section(
        db,
        company=other_company,
        created_by=creator,
        name="Lighthouse Maintenance",
        is_archived=True,
    )

    hidden = create_section(
        db,
        company=other_company,
        created_by=creator,
        name="Kitchen",
        is_archived=True,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        (
            "/admin/archived-sections"
            "?search=lighthouse"
        ),
    )

    assert response.status_code == 200
    assert company_match.name in response.text
    assert section_match.name in response.text
    assert hidden.name not in response.text


def test_archived_sections_paginates_results(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    company = create_company(
        db,
    )

    first = create_section(
        db,
        company=company,
        created_by=creator,
        name="A Archived Section",
        is_archived=True,
    )

    second = create_section(
        db,
        company=company,
        created_by=creator,
        name="B Archived Section",
        is_archived=True,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    first_page = client.get(
        (
            "/admin/archived-sections"
            "?page_size=1&page=1"
        ),
    )

    second_page = client.get(
        (
            "/admin/archived-sections"
            "?page_size=1&page=2"
        ),
    )

    assert first.name in first_page.text
    assert second.name not in first_page.text

    assert second.name in second_page.text
    assert first.name not in second_page.text


def test_administrator_restores_archived_section(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    company = create_company(
        db,
    )

    section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Route Restored Section",
        is_archived=True,
    )

    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        (
            "/admin/archived-sections/"
            f"{section.id}/restore"
        ),
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    db.refresh(
        section,
    )

    assert response.status_code == 303
    assert section.is_archived is False

    parsed = urlparse(
        response.headers[
            "location"
        ],
    )

    query = parse_qs(
        parsed.query,
    )

    assert query[
        "success"
    ] == [
        "Route Restored Section was restored.",
    ]


def test_restore_records_audit_event(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    company = create_company(
        db,
    )

    section = create_section(
        db,
        company=company,
        created_by=creator,
        is_archived=True,
    )

    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        (
            "/admin/archived-sections/"
            f"{section.id}/restore"
        ),
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    audit_log = db.scalar(
        select(
            AuditLog,
        ).where(
            AuditLog.action
            == AuditAction.SECTION_RESTORED.value,
            AuditLog.entity_type
            == "section",
            AuditLog.entity_id
            == section.id,
        ),
    )

    assert response.status_code == 303
    assert audit_log is not None
    assert audit_log.user_id == administrator.id


def test_restore_requires_csrf(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    company = create_company(
        db,
    )

    section = create_section(
        db,
        company=company,
        created_by=creator,
        is_archived=True,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        (
            "/admin/archived-sections/"
            f"{section.id}/restore"
        ),
        data={},
        follow_redirects=False,
    )

    db.refresh(
        section,
    )

    assert response.status_code == 403
    assert section.is_archived is True


def test_cannot_restore_section_inside_archived_company(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    company = create_company(
        db,
        is_archived=True,
    )

    section = create_section(
        db,
        company=company,
        created_by=creator,
        is_archived=True,
    )

    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        (
            "/admin/archived-sections/"
            f"{section.id}/restore"
        ),
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    db.refresh(
        section,
    )

    parsed = urlparse(
        response.headers[
            "location"
        ],
    )

    query = parse_qs(
        parsed.query,
    )

    assert response.status_code == 303
    assert section.is_archived is True

    assert (
        "company is archived"
        in query["error"][0]
    )


def test_archived_sections_empty_state(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/admin/archived-sections",
    )

    assert response.status_code == 200

    assert (
        "There are currently no archived sections."
        in response.text
    )