from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.constants import CompanyRole
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


def test_manager_cannot_view_other_company_members_page(
    client: TestClient,
    db: Session,
) -> None:
    own_company = create_company(
        db,
    )

    other_company = create_company(
        db,
    )

    manager = create_user(
        db,
    )

    create_company_membership(
        db,
        company=own_company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=manager,
    )

    response = client.get(
        f"/companies/{other_company.id}/members",
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert response.headers["location"].startswith(
        f"/companies/{other_company.id}?"
    )


def test_manager_cannot_add_member_to_other_company_by_posting_directly(
    client: TestClient,
    db: Session,
) -> None:
    own_company = create_company(
        db,
    )

    other_company = create_company(
        db,
    )

    manager = create_user(
        db,
    )

    target = create_user(
        db,
    )

    create_company_membership(
        db,
        company=own_company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=manager,
    )

    response = client.post(
        f"/companies/{other_company.id}/members",
        data={
            "csrf_token": csrf_token,
            "user_id": str(
                target.id,
            ),
            "role": CompanyRole.MANAGER.value,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    membership = db.scalar(
        select(CompanyMembership).where(
            CompanyMembership.company_id
            == other_company.id,
            CompanyMembership.user_id
            == target.id,
        )
    )

    assert membership is None


def test_manager_cannot_change_other_company_role_by_direct_post(
    client: TestClient,
    db: Session,
) -> None:
    own_company = create_company(
        db,
    )

    other_company = create_company(
        db,
    )

    manager = create_user(
        db,
    )

    target = create_user(
        db,
    )

    create_company_membership(
        db,
        company=own_company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    target_membership = create_company_membership(
        db,
        company=other_company,
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
            f"/companies/{other_company.id}/members/"
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
        target_membership,
    )

    assert (
        target_membership.role
        == CompanyRole.EMPLOYEE.value
    )


def test_manager_cannot_remove_other_company_member_by_direct_post(
    client: TestClient,
    db: Session,
) -> None:
    own_company = create_company(
        db,
    )

    other_company = create_company(
        db,
    )

    manager = create_user(
        db,
    )

    target = create_user(
        db,
    )

    create_company_membership(
        db,
        company=own_company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    target_membership = create_company_membership(
        db,
        company=other_company,
        user=target,
    )

    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=manager,
    )

    response = client.post(
        (
            f"/companies/{other_company.id}/members/"
            f"{target.id}/remove"
        ),
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert db.get(
        CompanyMembership,
        target_membership.id,
    ) is target_membership


def test_employee_cannot_mutate_company_membership_by_direct_post(
    client: TestClient,
    db: Session,
) -> None:
    company = create_company(
        db,
    )

    employee = create_user(
        db,
    )

    target = create_user(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=employee,
        role=CompanyRole.EMPLOYEE,
    )

    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=employee,
    )

    response = client.post(
        f"/companies/{company.id}/members",
        data={
            "csrf_token": csrf_token,
            "user_id": str(
                target.id,
            ),
            "role": CompanyRole.MANAGER.value,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    membership = db.scalar(
        select(CompanyMembership).where(
            CompanyMembership.company_id
            == company.id,
            CompanyMembership.user_id
            == target.id,
        )
    )

    assert membership is None


def test_missing_csrf_cannot_add_company_member(
    client: TestClient,
    db: Session,
) -> None:
    company = create_company(
        db,
    )

    manager = create_user(
        db,
    )

    target = create_user(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
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


def test_inactive_manager_session_cannot_manage_memberships(
    client: TestClient,
    db: Session,
) -> None:
    company = create_company(
        db,
    )

    manager = create_user(
        db,
        is_active=True,
    )

    target = create_user(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    _, session_token, csrf_token = create_auth_session(
        db,
        user=manager,
    )

    manager.is_active = False
    db.commit()

    client.cookies.set(
        settings.session_cookie_name,
        session_token,
    )

    client.cookies.set(
        f"{settings.session_cookie_name}_csrf",
        csrf_token,
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
        headers={
            "accept": "application/json",
        },
        follow_redirects=False,
    )

    assert response.status_code == 401

    membership = db.scalar(
        select(CompanyMembership).where(
            CompanyMembership.company_id
            == company.id,
            CompanyMembership.user_id
            == target.id,
        )
    )

    assert membership is None