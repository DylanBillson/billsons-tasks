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
from app.web.routes.admin_archived_companies import (
    router as archived_companies_router,
)
from tests.factories import (
    create_administrator,
    create_auth_session,
    create_company,
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
    path="/admin/archived-companies",
    name="admin_archived_companies",
):
    app.include_router(
        archived_companies_router,
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


def test_archived_companies_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        "/admin/archived-companies",
        headers={
            "accept": "text/html",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert response.headers[
        "location"
    ] == (
        "/login?next_url="
        "%2Fadmin%2Farchived-companies"
    )


def test_archived_companies_requires_administrator(
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
        "/admin/archived-companies",
        follow_redirects=False,
    )

    assert response.status_code == 403


def test_archived_companies_lists_only_archived_records(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    archived = create_company(
        db,
        name="Visible Archived Company",
        is_archived=True,
    )

    active = create_company(
        db,
        name="Hidden Active Company",
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/admin/archived-companies",
    )

    assert response.status_code == 200
    assert archived.name in response.text
    assert active.name not in response.text


def test_archived_companies_searches_name(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    matching = create_company(
        db,
        name="Matching Archive",
        is_archived=True,
    )

    create_company(
        db,
        name="Different Archive",
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
            "/admin/archived-companies"
            "?search=matching"
        ),
    )

    assert response.status_code == 200
    assert matching.name in response.text
    assert "Different Archive" not in response.text


def test_archived_companies_searches_description(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    matching = create_company(
        db,
        name="Description Match",
        description="Contains a lighthouse.",
        is_archived=True,
    )

    create_company(
        db,
        name="Other Description",
        description="Contains a harbour.",
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
            "/admin/archived-companies"
            "?search=lighthouse"
        ),
    )

    assert response.status_code == 200
    assert matching.name in response.text
    assert "Other Description" not in response.text


def test_archived_companies_paginates_results(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    first = create_company(
        db,
        name="A Archived Company",
        is_archived=True,
    )

    second = create_company(
        db,
        name="B Archived Company",
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
            "/admin/archived-companies"
            "?page_size=1&page=1"
        ),
    )

    second_page = client.get(
        (
            "/admin/archived-companies"
            "?page_size=1&page=2"
        ),
    )

    assert first_page.status_code == 200
    assert second_page.status_code == 200

    assert first.name in first_page.text
    assert second.name not in first_page.text

    assert second.name in second_page.text
    assert first.name not in second_page.text


def test_administrator_restores_archived_company(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    company = create_company(
        db,
        name="Route Restored Company",
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
            "/admin/archived-companies/"
            f"{company.id}/restore"
        ),
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    db.refresh(
        company,
    )

    assert response.status_code == 303
    assert company.is_archived is False

    parsed = urlparse(
        response.headers[
            "location"
        ],
    )

    query = parse_qs(
        parsed.query,
    )

    assert parsed.path == (
        "/admin/archived-companies"
    )

    assert query[
        "success"
    ] == [
        "Route Restored Company was restored.",
    ]


def test_restore_records_audit_event(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    company = create_company(
        db,
        name="Audited Route Restore",
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
            "/admin/archived-companies/"
            f"{company.id}/restore"
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
            == AuditAction.COMPANY_RESTORED.value,
            AuditLog.entity_type
            == "company",
            AuditLog.entity_id
            == company.id,
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

    company = create_company(
        db,
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
            "/admin/archived-companies/"
            f"{company.id}/restore"
        ),
        data={},
        follow_redirects=False,
    )

    db.refresh(
        company,
    )

    assert response.status_code == 403
    assert company.is_archived is True


def test_restore_rejects_active_company(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    company = create_company(
        db,
        name="Already Active Company",
    )

    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        (
            "/admin/archived-companies/"
            f"{company.id}/restore"
        ),
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
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
    assert query[
        "error"
    ] == [
        "Already Active Company is not archived.",
    ]


def test_archived_company_page_renders_empty_state(
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
        "/admin/archived-companies",
    )

    assert response.status_code == 200

    assert (
        "There are currently no archived companies."
        in response.text
    )