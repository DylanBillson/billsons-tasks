from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import CompanyRole
from tests.factories import (
    create_administrator,
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


def test_companies_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        "/companies",
        headers={
            "accept": "text/html",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/login?next_url=%2Fcompanies"
    )


def test_standard_user_sees_only_member_companies(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(db)
    visible = create_company(db, name="Visible Company")
    hidden = create_company(db, name="Hidden Company")
    create_company_membership(
        db,
        company=visible,
        user=user,
    )
    db.commit()
    _authenticate(client, db, user=user)

    response = client.get("/companies")

    assert response.status_code == 200
    assert visible.name in response.text
    assert hidden.name not in response.text


def test_administrator_sees_all_active_companies(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(db)
    first = create_company(db, name="First Active Company")
    second = create_company(db, name="Second Active Company")
    archived = create_company(
        db,
        name="Archived Hidden Company",
        is_archived=True,
    )
    db.commit()
    _authenticate(client, db, user=administrator)

    response = client.get("/companies")

    assert response.status_code == 200
    assert first.name in response.text
    assert second.name in response.text
    assert archived.name not in response.text


def test_company_detail_requires_membership(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(db)
    company = create_company(db)
    db.commit()
    _authenticate(client, db, user=user)

    response = client.get(
        f"/companies/{company.id}",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/companies?")


def test_company_detail_renders_member_company(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(db)
    company = create_company(
        db,
        name="Accessible Company",
        description="Accessible description.",
    )
    create_company_membership(db, company=company, user=user)
    db.commit()
    _authenticate(client, db, user=user)

    response = client.get(f"/companies/{company.id}")

    assert response.status_code == 200
    assert "Accessible Company" in response.text
    assert "Accessible description." in response.text


def test_company_detail_lists_only_accessible_sections(
    client: TestClient,
    db: Session,
) -> None:
    manager = create_user(db)
    other_manager = create_user(db)
    company = create_company(db)
    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )
    create_company_membership(
        db,
        company=company,
        user=other_manager,
        role=CompanyRole.MANAGER,
    )
    own_section = create_section(
        db,
        company=company,
        created_by=manager,
        name="Own Section",
    )
    hidden_section = create_section(
        db,
        company=company,
        created_by=other_manager,
        name="Hidden Section",
    )
    db.commit()
    _authenticate(client, db, user=manager)

    response = client.get(f"/companies/{company.id}")

    assert response.status_code == 200
    assert own_section.name in response.text
    assert hidden_section.name not in response.text


def test_company_detail_lists_explicitly_assigned_section(
    client: TestClient,
    db: Session,
) -> None:
    employee = create_user(db)
    creator = create_user(db)
    company = create_company(db)
    create_company_membership(db, company=company, user=employee)
    section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Assigned Section",
    )
    create_section_membership(
        db,
        section=section,
        user=employee,
    )
    db.commit()
    _authenticate(client, db, user=employee)

    response = client.get(f"/companies/{company.id}")

    assert response.status_code == 200
    assert "Assigned Section" in response.text


def test_manager_company_detail_shows_create_section_link(
    client: TestClient,
    db: Session,
) -> None:
    manager = create_user(db)
    company = create_company(db)
    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )
    db.commit()
    _authenticate(client, db, user=manager)

    response = client.get(f"/companies/{company.id}")

    assert response.status_code == 200
    assert f"/companies/{company.id}/sections/create" in response.text


def test_employee_company_detail_hides_create_section_link(
    client: TestClient,
    db: Session,
) -> None:
    employee = create_user(db)
    company = create_company(db)
    create_company_membership(
        db,
        company=company,
        user=employee,
        role=CompanyRole.EMPLOYEE,
    )
    db.commit()
    _authenticate(client, db, user=employee)

    response = client.get(f"/companies/{company.id}")

    assert response.status_code == 200
    assert f"/companies/{company.id}/sections/create" not in response.text


def test_company_members_route_denies_employee(
    client: TestClient,
    db: Session,
) -> None:
    employee = create_user(db)
    company = create_company(db)
    create_company_membership(db, company=company, user=employee)
    db.commit()
    _authenticate(client, db, user=employee)

    response = client.get(
        f"/companies/{company.id}/members",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        f"/companies/{company.id}?"
    )


def test_company_members_route_is_reserved_for_manager(
    client: TestClient,
    db: Session,
) -> None:
    manager = create_user(db)
    company = create_company(db)
    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )
    db.commit()
    _authenticate(client, db, user=manager)

    response = client.get(
        f"/companies/{company.id}/members",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        f"/companies/{company.id}?"
    )
    assert "not+been+created+yet" in response.headers["location"]
