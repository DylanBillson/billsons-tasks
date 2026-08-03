from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import AuditAction
from app.main import app
from app.web.routes.admin import (
    router as admin_router,
)
from tests.factories import (
    create_administrator,
    create_audit_log,
    create_auth_session,
    create_company,
    create_section,
    create_section_list,
    create_task,
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
    path="/admin",
    name="admin_dashboard",
):
    app.include_router(
        admin_router,
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


def test_admin_dashboard_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        "/admin",
        headers={
            "accept": "text/html",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert response.headers[
        "location"
    ] == "/login?next_url=%2Fadmin"


def test_admin_dashboard_requires_administrator(
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
        "/admin",
        follow_redirects=False,
    )

    assert response.status_code == 403


def test_administrator_views_admin_dashboard(
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
        "/admin",
    )

    assert response.status_code == 200
    assert "Administration" in response.text
    assert "Active Users" in response.text
    assert "Active Companies" in response.text
    assert "Deleted Tasks" in response.text
    assert "Archived Sections" in response.text
    assert "Archived Companies" in response.text
    assert "Notification Failures" in response.text


def test_admin_dashboard_displays_user_metrics(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    create_user(
        db,
        display_name="Active Dashboard User",
    )

    create_user(
        db,
        display_name="Inactive Dashboard User",
        is_active=False,
    )

    create_user(
        db,
        display_name="Anonymised Dashboard User",
        is_active=False,
        is_anonymised=True,
    )

    db.commit()

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
        "2 active,"
        in response.text
    )

    assert (
        "1 inactive,"
        in response.text
    )

    assert (
        "1 anonymised"
        in response.text
    )


def test_admin_dashboard_displays_company_metrics(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    create_company(
        db,
        name="Active Dashboard Company",
    )

    create_company(
        db,
        name="Archived Dashboard Company",
        is_archived=True,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/admin",
    )

    assert response.status_code == 200
    assert "1 active" in response.text
    assert "1 archived" in response.text


def test_admin_dashboard_counts_archived_sections(
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

    create_section(
        db,
        company=company,
        created_by=creator,
        name="Archived Dashboard Section",
        is_archived=True,
    )

    db.commit()

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
        "1 archived"
        in response.text
    )


def test_admin_dashboard_counts_deleted_tasks(
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
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Deleted Dashboard Task",
        deleted_by=creator,
    )

    db.commit()

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
        "1 deleted"
        in response.text
    )


def test_admin_dashboard_counts_notification_failures(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    create_audit_log(
        db,
        action=(
            AuditAction.NOTIFICATION_FAILED.value
        ),
        summary="Notification delivery failed.",
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/admin",
    )

    assert response.status_code == 200
    assert "Notification Failures" in response.text
    assert "1" in response.text


def test_admin_dashboard_lists_recent_audit_activity(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    audit_log = create_audit_log(
        db,
        action="company_created",
        summary="A recent dashboard company was created.",
        user=administrator,
        entity_type="company",
        entity_id=42,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/admin",
    )

    assert response.status_code == 200
    assert audit_log.summary in response.text
    assert audit_log.action in response.text

    assert (
        f"/admin/audit/{audit_log.id}"
        in response.text
    )


def test_admin_dashboard_contains_management_links(
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
        "/admin",
    )

    assert response.status_code == 200

    for path in (
        "/admin/users",
        "/admin/companies",
        "/admin/archived-companies",
        "/admin/archived-sections",
        "/admin/deleted-tasks",
        "/admin/audit",
    ):
        assert path in response.text


def test_admin_dashboard_renders_empty_activity_state(
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
        "/admin",
    )

    assert response.status_code == 200

    assert (
        "No audit activity has been recorded yet."
        in response.text
    )