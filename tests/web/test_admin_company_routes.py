from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import AuditAction, CompanyRole
from app.models.audit_log import AuditLog
from app.models.company import Company
from app.models.company_membership import CompanyMembership
from tests.factories import (
    create_administrator,
    create_auth_session,
    create_company,
    create_company_membership,
    create_user,
)


def _authenticate(
    client: TestClient,
    db: Session,
    *,
    user,
) -> tuple[str, str]:
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

    return session_token, csrf_token


def test_admin_companies_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        "/admin/companies",
        headers={
            "accept": "text/html",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/login?next_url=%2Fadmin%2Fcompanies"
    )


def test_admin_companies_requires_administrator(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(db)
    _authenticate(client, db, user=user)

    response = client.get(
        "/admin/companies",
        follow_redirects=False,
    )

    assert response.status_code == 403


def test_admin_companies_lists_active_and_archived_companies(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(db)
    active = create_company(
        db,
        name="Active Company",
    )
    archived = create_company(
        db,
        name="Archived Company",
        is_archived=True,
    )
    db.commit()
    _authenticate(client, db, user=administrator)

    response = client.get("/admin/companies")

    assert response.status_code == 200
    assert active.name in response.text
    assert archived.name in response.text


def test_admin_company_create_page_renders(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(db)
    _, csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get("/admin/companies/create")

    assert response.status_code == 200
    assert 'name="name"' in response.text
    assert 'name="description"' in response.text
    assert csrf_token in response.text


def test_admin_company_create_submit_creates_company(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(db)
    _, csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        "/admin/companies/create",
        data={
            "csrf_token": csrf_token,
            "name": "New Company",
            "description": "Created through the web route.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    company = db.scalar(
        select(Company).where(
            Company.name == "New Company",
        )
    )
    assert company is not None
    assert company.description == "Created through the web route."
    assert response.headers["location"].startswith(
        f"/admin/companies/{company.id}"
    )


def test_admin_company_create_submit_rejects_duplicate_name(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(db)
    create_company(
        db,
        name="Duplicate Company",
    )
    db.commit()
    _, csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        "/admin/companies/create",
        data={
            "csrf_token": csrf_token,
            "name": "Duplicate Company",
            "description": "",
        },
    )

    assert response.status_code == 422
    assert "already exists" in response.text


def test_admin_company_detail_renders_company(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(db)
    company = create_company(
        db,
        name="Detail Company",
        description="Detail description.",
    )
    db.commit()
    _authenticate(client, db, user=administrator)

    response = client.get(
        f"/admin/companies/{company.id}",
    )

    assert response.status_code == 200
    assert "Detail Company" in response.text
    assert "Detail description." in response.text


def test_admin_company_edit_submit_updates_company(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(db)
    company = create_company(
        db,
        name="Before Edit",
    )
    db.commit()
    _, csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        f"/admin/companies/{company.id}/edit",
        data={
            "csrf_token": csrf_token,
            "name": "After Edit",
            "description": "Updated description.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    db.refresh(company)
    assert company.name == "After Edit"
    assert company.description == "Updated description."


def test_admin_company_archive_and_restore(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(db)
    company = create_company(db)
    db.commit()
    _, csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    archive_response = client.post(
        f"/admin/companies/{company.id}/archive",
        data={"csrf_token": csrf_token},
        follow_redirects=False,
    )

    assert archive_response.status_code == 303
    db.refresh(company)
    assert company.is_archived is True

    restore_response = client.post(
        f"/admin/companies/{company.id}/restore",
        data={"csrf_token": csrf_token},
        follow_redirects=False,
    )

    assert restore_response.status_code == 303
    db.refresh(company)
    assert company.is_archived is False


def test_admin_company_members_page_lists_members_and_available_users(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(db)
    company = create_company(db)
    member = create_user(
        db,
        display_name="Existing Member",
    )
    create_user(
        db,
        display_name="Available User",
    )
    create_company_membership(
        db,
        company=company,
        user=member,
    )
    db.commit()
    _authenticate(client, db, user=administrator)

    response = client.get(
        f"/admin/companies/{company.id}/members",
    )

    assert response.status_code == 200
    assert "Existing Member" in response.text
    assert "Available User" in response.text


def test_admin_company_member_add_update_and_remove(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(db)
    company = create_company(db)
    target = create_user(
        db,
        display_name="Membership Target",
    )
    db.commit()
    _, csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    add_response = client.post(
        f"/admin/companies/{company.id}/members",
        data={
            "csrf_token": csrf_token,
            "user_id": str(target.id),
            "role": CompanyRole.EMPLOYEE.value,
        },
        follow_redirects=False,
    )

    assert add_response.status_code == 303

    membership = db.scalar(
        select(CompanyMembership).where(
            CompanyMembership.company_id == company.id,
            CompanyMembership.user_id == target.id,
        )
    )
    assert membership is not None

    role_response = client.post(
        f"/admin/companies/{company.id}/members/{target.id}/role",
        data={
            "csrf_token": csrf_token,
            "role": CompanyRole.MANAGER.value,
        },
        follow_redirects=False,
    )

    assert role_response.status_code == 303
    db.refresh(membership)
    assert membership.role == CompanyRole.MANAGER.value

    membership_id = membership.id

    remove_response = client.post(
        f"/admin/companies/{company.id}/members/{target.id}/remove",
        data={"csrf_token": csrf_token},
        follow_redirects=False,
    )

    assert remove_response.status_code == 303
    assert db.scalar(
        select(CompanyMembership).where(
            CompanyMembership.id == membership_id,
        )
    ) is None


def test_admin_company_mutations_require_csrf(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(db)
    company = create_company(db)
    db.commit()
    _authenticate(client, db, user=administrator)

    response = client.post(
        f"/admin/companies/{company.id}/archive",
        data={},
        follow_redirects=False,
    )

    assert response.status_code == 403


def test_admin_company_create_records_audit_event(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(db)
    _, csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        "/admin/companies/create",
        data={
            "csrf_token": csrf_token,
            "name": "Audited Web Company",
            "description": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action == AuditAction.COMPANY_CREATED.value,
        )
    )
    assert audit_log is not None
    assert audit_log.user_id == administrator.id
