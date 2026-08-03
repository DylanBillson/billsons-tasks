from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.main import app
from app.web.routes.admin_audit import (
    router as admin_audit_router,
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
    path="/admin/audit",
    name="admin_audit",
):
    app.include_router(
        admin_audit_router,
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


def test_standard_user_cannot_view_audit_index(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    create_audit_log(
        db,
        action="task_created",
        summary="Protected audit entry.",
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        "/admin/audit",
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert "Protected audit entry." not in response.text


def test_standard_user_cannot_view_audit_detail(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    audit_log = create_audit_log(
        db,
        action="task_updated",
        summary="Protected detail entry.",
        metadata_json={
            "sensitive_business_data": (
                "Protected value"
            ),
        },
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        f"/admin/audit/{audit_log.id}",
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert "Protected detail entry." not in response.text
    assert "Protected value" not in response.text


def test_standard_user_cannot_use_filters_to_expose_audit_data(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    audit_log = create_audit_log(
        db,
        action="company_created",
        summary="Hidden filtered audit event.",
        entity_type="company",
        entity_id=42,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        (
            "/admin/audit"
            "?action=company_created"
            "&entity_type=company"
            f"&entity_id={audit_log.entity_id}"
        ),
        follow_redirects=False,
    )

    assert response.status_code == 403

    assert (
        "Hidden filtered audit event."
        not in response.text
    )


def test_company_manager_cannot_view_company_audit_entries(
    client: TestClient,
    db: Session,
) -> None:
    manager = create_user(
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

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
    )

    audit_log = create_audit_log(
        db,
        action="task_updated",
        summary="Company task audit event.",
        entity_type="task",
        entity_id=task.id,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=manager,
    )

    response = client.get(
        f"/admin/audit/{audit_log.id}",
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert audit_log.summary not in response.text


def test_administrator_can_view_audit_entries_across_companies(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    first = create_audit_log(
        db,
        action="company_created",
        summary="First company audit event.",
        entity_type="company",
        entity_id=1,
    )

    second = create_audit_log(
        db,
        action="company_created",
        summary="Second company audit event.",
        entity_type="company",
        entity_id=2,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/admin/audit",
    )

    assert response.status_code == 200
    assert first.summary in response.text
    assert second.summary in response.text


def test_audit_detail_does_not_expose_redacted_secret(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    audit_log = create_audit_log(
        db,
        action="settings_updated",
        summary="Settings were updated.",
        metadata_json={
            "password": "[REDACTED]",
            "safe_setting": "visible",
        },
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        f"/admin/audit/{audit_log.id}",
    )

    assert response.status_code == 200
    assert "[REDACTED]" in response.text
    assert "visible" in response.text
    assert "actual-secret-value" not in response.text