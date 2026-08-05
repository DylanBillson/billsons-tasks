from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.constants import (
    AuditAction,
    CompanyRole,
)
from app.models.audit_log import AuditLog
from app.models.company_membership import (
    CompanyMembership,
)
from tests.factories import (
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


def _create_manager_context(
    db: Session,
):
    company = create_company(
        db,
        name="Manager Membership Company",
    )

    manager = create_user(
        db,
        display_name="Company Manager",
    )

    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    return company, manager


def test_company_members_requires_authentication(
    client: TestClient,
    db: Session,
) -> None:
    company = create_company(
        db,
    )

    db.commit()

    response = client.get(
        f"/companies/{company.id}/members",
        headers={
            "accept": "text/html",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert response.headers["location"] == (
        "/login?next_url="
        f"%2Fcompanies%2F{company.id}%2Fmembers"
    )


def test_company_manager_can_render_members_page(
    client: TestClient,
    db: Session,
) -> None:
    company, manager = _create_manager_context(
        db,
    )

    member = create_user(
        db,
        display_name="Existing Company Member",
    )

    available = create_user(
        db,
        display_name="Available Company User",
    )

    create_company_membership(
        db,
        company=company,
        user=member,
        role=CompanyRole.EMPLOYEE,
    )

    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=manager,
    )

    response = client.get(
        f"/companies/{company.id}/members",
    )

    assert response.status_code == 200

    assert "Manage Company Members" in response.text
    assert "Existing Company Member" in response.text
    assert "Available Company User" in response.text
    assert csrf_token in response.text

    assert (
        f"/companies/{company.id}/members"
        in response.text
    )

    assert (
        f"/companies/{company.id}/members/"
        f"{member.id}/role"
        in response.text
    )

    assert (
        f"/companies/{company.id}/members/"
        f"{member.id}/remove"
        in response.text
    )

    assert str(available.id) in response.text


def test_company_employee_cannot_render_members_page(
    client: TestClient,
    db: Session,
) -> None:
    company = create_company(
        db,
    )

    employee = create_user(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=employee,
        role=CompanyRole.EMPLOYEE,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=employee,
    )

    response = client.get(
        f"/companies/{company.id}/members",
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert response.headers["location"].startswith(
        f"/companies/{company.id}?"
    )


def test_company_manager_adds_member(
    client: TestClient,
    db: Session,
) -> None:
    company, manager = _create_manager_context(
        db,
    )

    target = create_user(
        db,
        display_name="Manager Added User",
    )

    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=manager,
    )

    response = client.post(
        f"/companies/{company.id}/members",
        data={
            "csrf_token": csrf_token,
            "user_id": str(
                target.id,
            ),
            "role": CompanyRole.EMPLOYEE.value,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert response.headers["location"].startswith(
        f"/companies/{company.id}/members?"
    )

    membership = db.scalar(
        select(CompanyMembership).where(
            CompanyMembership.company_id
            == company.id,
            CompanyMembership.user_id
            == target.id,
        )
    )

    assert membership is not None
    assert membership.role == CompanyRole.EMPLOYEE.value


def test_company_manager_updates_member_role(
    client: TestClient,
    db: Session,
) -> None:
    company, manager = _create_manager_context(
        db,
    )

    target = create_user(
        db,
    )

    membership = create_company_membership(
        db,
        company=company,
        user=target,
        role=CompanyRole.EMPLOYEE,
    )

    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=manager,
    )

    response = client.post(
        (
            f"/companies/{company.id}/members/"
            f"{target.id}/role"
        ),
        data={
            "csrf_token": csrf_token,
            "role": CompanyRole.MANAGER.value,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    db.refresh(
        membership,
    )

    assert membership.role == CompanyRole.MANAGER.value


def test_company_manager_removes_member(
    client: TestClient,
    db: Session,
) -> None:
    company, manager = _create_manager_context(
        db,
    )

    target = create_user(
        db,
        display_name="Manager Removed User",
    )

    membership = create_company_membership(
        db,
        company=company,
        user=target,
    )

    membership_id = membership.id

    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=manager,
    )

    response = client.post(
        (
            f"/companies/{company.id}/members/"
            f"{target.id}/remove"
        ),
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert db.scalar(
        select(CompanyMembership).where(
            CompanyMembership.id
            == membership_id,
        )
    ) is None


def test_company_membership_mutations_are_audited(
    client: TestClient,
    db: Session,
) -> None:
    company, manager = _create_manager_context(
        db,
    )

    target = create_user(
        db,
        username="manager-audited-member",
        display_name="Manager Audited Member",
    )

    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=manager,
    )

    add_response = client.post(
        f"/companies/{company.id}/members",
        data={
            "csrf_token": csrf_token,
            "user_id": str(
                target.id,
            ),
            "role": CompanyRole.EMPLOYEE.value,
        },
        follow_redirects=False,
    )

    assert add_response.status_code == 303

    role_response = client.post(
        (
            f"/companies/{company.id}/members/"
            f"{target.id}/role"
        ),
        data={
            "csrf_token": csrf_token,
            "role": CompanyRole.MANAGER.value,
        },
        follow_redirects=False,
    )

    assert role_response.status_code == 303

    remove_response = client.post(
        (
            f"/companies/{company.id}/members/"
            f"{target.id}/remove"
        ),
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert remove_response.status_code == 303

    actions = list(
        db.scalars(
            select(AuditLog.action).where(
                AuditLog.user_id == manager.id,
                AuditLog.action.in_(
                    [
                        AuditAction.COMPANY_MEMBER_ADDED.value,
                        AuditAction.COMPANY_MEMBER_UPDATED.value,
                        AuditAction.COMPANY_MEMBER_REMOVED.value,
                    ],
                ),
            )
        ).all()
    )

    assert (
        AuditAction.COMPANY_MEMBER_ADDED.value
        in actions
    )

    assert (
        AuditAction.COMPANY_MEMBER_UPDATED.value
        in actions
    )

    assert (
        AuditAction.COMPANY_MEMBER_REMOVED.value
        in actions
    )


def test_company_member_add_rejects_invalid_form(
    client: TestClient,
    db: Session,
) -> None:
    company, manager = _create_manager_context(
        db,
    )

    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=manager,
    )

    response = client.post(
        f"/companies/{company.id}/members",
        data={
            "csrf_token": csrf_token,
            "user_id": "",
            "role": "not-a-role",
        },
    )

    assert response.status_code == 422
    assert "Please correct" in response.text


def test_company_membership_mutations_require_csrf(
    client: TestClient,
    db: Session,
) -> None:
    company, manager = _create_manager_context(
        db,
    )

    target = create_user(
        db,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=manager,
    )

    response = client.post(
        f"/companies/{company.id}/members",
        data={
            "user_id": str(
                target.id,
            ),
            "role": CompanyRole.EMPLOYEE.value,
        },
        follow_redirects=False,
    )

    assert response.status_code == 403

    membership = db.scalar(
        select(CompanyMembership).where(
            CompanyMembership.company_id
            == company.id,
            CompanyMembership.user_id
            == target.id,
        )
    )

    assert membership is None