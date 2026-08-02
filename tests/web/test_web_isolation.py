from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import CompanyRole
from tests.factories import (
    create_auth_session,
    create_company,
    create_company_membership,
    create_section,
    create_section_membership,
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


def test_manager_cannot_discover_unassigned_section_on_company_page(
    client: TestClient,
    db: Session,
) -> None:
    company = create_company(db)
    manager_a = create_user(db)
    manager_b = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=manager_a,
        role=CompanyRole.MANAGER,
    )
    create_company_membership(
        db,
        company=company,
        user=manager_b,
        role=CompanyRole.MANAGER,
    )
    visible = create_section(
        db,
        company=company,
        created_by=manager_a,
        name="Manager A Section",
    )
    hidden = create_section(
        db,
        company=company,
        created_by=manager_b,
        name="Manager B Private Section",
    )
    db.commit()
    _authenticate(client, db, user=manager_a)

    response = client.get(f"/companies/{company.id}")

    assert response.status_code == 200
    assert visible.name in response.text
    assert hidden.name not in response.text
    assert f"/sections/{hidden.id}" not in response.text


def test_manager_cannot_open_unassigned_section_by_changing_url(
    client: TestClient,
    db: Session,
) -> None:
    company = create_company(db)
    manager_a = create_user(db)
    manager_b = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=manager_a,
        role=CompanyRole.MANAGER,
    )
    create_company_membership(
        db,
        company=company,
        user=manager_b,
        role=CompanyRole.MANAGER,
    )
    hidden = create_section(
        db,
        company=company,
        created_by=manager_b,
    )
    db.commit()
    _authenticate(client, db, user=manager_a)

    response = client.get(
        f"/sections/{hidden.id}",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/companies?")


def test_manager_cannot_edit_unassigned_section_by_changing_url(
    client: TestClient,
    db: Session,
) -> None:
    company = create_company(db)
    manager_a = create_user(db)
    manager_b = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=manager_a,
        role=CompanyRole.MANAGER,
    )
    create_company_membership(
        db,
        company=company,
        user=manager_b,
        role=CompanyRole.MANAGER,
    )
    hidden = create_section(
        db,
        company=company,
        created_by=manager_b,
    )
    db.commit()
    _authenticate(client, db, user=manager_a)

    response = client.get(
        f"/sections/{hidden.id}/edit",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        f"/sections/{hidden.id}?"
    )


def test_assigned_manager_can_view_but_cannot_edit_section(
    client: TestClient,
    db: Session,
) -> None:
    company = create_company(db)
    creator = create_user(db)
    assigned_manager = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=assigned_manager,
        role=CompanyRole.MANAGER,
    )
    section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Assigned Read Only Section",
    )
    create_section_membership(
        db,
        section=section,
        user=assigned_manager,
    )
    db.commit()
    _authenticate(client, db, user=assigned_manager)

    detail_response = client.get(f"/sections/{section.id}")
    edit_response = client.get(
        f"/sections/{section.id}/edit",
        follow_redirects=False,
    )

    assert detail_response.status_code == 200
    assert "Assigned Read Only Section" in detail_response.text
    assert edit_response.status_code == 303


def test_employee_cannot_open_unassigned_section_in_own_company(
    client: TestClient,
    db: Session,
) -> None:
    company = create_company(db)
    manager = create_user(db)
    employee = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )
    create_company_membership(
        db,
        company=company,
        user=employee,
        role=CompanyRole.EMPLOYEE,
    )
    section = create_section(
        db,
        company=company,
        created_by=manager,
    )
    db.commit()
    _authenticate(client, db, user=employee)

    response = client.get(
        f"/sections/{section.id}",
        follow_redirects=False,
    )

    assert response.status_code == 303


def test_user_cannot_open_company_by_changing_company_id(
    client: TestClient,
    db: Session,
) -> None:
    own_company = create_company(db)
    other_company = create_company(db)
    user = create_user(db)
    create_company_membership(
        db,
        company=own_company,
        user=user,
    )
    db.commit()
    _authenticate(client, db, user=user)

    response = client.get(
        f"/companies/{other_company.id}",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/companies?")


def test_manager_cannot_create_section_in_other_company_by_url(
    client: TestClient,
    db: Session,
) -> None:
    own_company = create_company(db)
    other_company = create_company(db)
    manager = create_user(db)
    create_company_membership(
        db,
        company=own_company,
        user=manager,
        role=CompanyRole.MANAGER,
    )
    db.commit()
    csrf_token = _authenticate(client, db, user=manager)

    response = client.post(
        f"/companies/{other_company.id}/sections/create",
        data={
            "csrf_token": csrf_token,
            "name": "Forbidden Cross Company Section",
            "description": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        f"/companies/{other_company.id}?"
    )


def test_assigned_member_cannot_manage_section_memberships_by_url(
    client: TestClient,
    db: Session,
) -> None:
    company = create_company(db)
    creator = create_user(db)
    assigned = create_user(db)
    target = create_user(db)
    create_company_membership(db, company=company, user=assigned)
    create_company_membership(db, company=company, user=target)
    section = create_section(
        db,
        company=company,
        created_by=creator,
    )
    create_section_membership(
        db,
        section=section,
        user=assigned,
    )
    db.commit()
    _authenticate(client, db, user=assigned)

    response = client.get(
        f"/sections/{section.id}/members",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        f"/sections/{section.id}?"
    )
