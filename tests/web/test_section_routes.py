from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import CompanyRole
from app.models.section import Section
from app.models.section_membership import SectionMembership
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

    client.cookies.set(settings.session_cookie_name, session_token)
    client.cookies.set(
        f"{settings.session_cookie_name}_csrf",
        csrf_token,
    )

    return csrf_token


def test_section_create_page_requires_authentication(
    client: TestClient,
    db: Session,
) -> None:
    company = create_company(db)
    db.commit()

    create_url = (
        f"/companies/{company.id}/sections/create"
    )

    response = client.get(
        create_url,
        headers={
            "accept": "text/html",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/login?next_url="
        f"%2Fcompanies%2F{company.id}"
        "%2Fsections%2Fcreate"
    )


def test_manager_can_render_section_create_page(
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
    csrf_token = _authenticate(client, db, user=manager)

    response = client.get(
        f"/companies/{company.id}/sections/create"
    )

    assert response.status_code == 200
    assert 'name="name"' in response.text
    assert csrf_token in response.text


def test_employee_cannot_render_section_create_page(
    client: TestClient,
    db: Session,
) -> None:
    employee = create_user(db)
    company = create_company(db)
    create_company_membership(db, company=company, user=employee)
    db.commit()
    _authenticate(client, db, user=employee)

    response = client.get(
        f"/companies/{company.id}/sections/create",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        f"/companies/{company.id}?"
    )


def test_manager_creates_section(
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
    csrf_token = _authenticate(client, db, user=manager)

    response = client.post(
        f"/companies/{company.id}/sections/create",
        data={
            "csrf_token": csrf_token,
            "name": "Created Section",
            "description": "Created through the route.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    section = db.scalar(
        select(Section).where(
            Section.company_id == company.id,
            Section.name == "Created Section",
        )
    )
    assert section is not None
    assert section.created_by_user_id == manager.id
    assert response.headers["location"].startswith(
        f"/sections/{section.id}"
    )


def test_section_create_rejects_duplicate_name(
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
    create_section(
        db,
        company=company,
        created_by=manager,
        name="Duplicate Section",
    )
    db.commit()
    csrf_token = _authenticate(client, db, user=manager)

    response = client.post(
        f"/companies/{company.id}/sections/create",
        data={
            "csrf_token": csrf_token,
            "name": "Duplicate Section",
            "description": "",
        },
    )

    assert response.status_code == 422
    assert "already exists" in response.text


def test_section_detail_renders_for_creator(
    client: TestClient,
    db: Session,
) -> None:
    creator = create_user(db)
    company = create_company(db)
    section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Creator Section",
    )
    db.commit()
    _authenticate(client, db, user=creator)

    response = client.get(f"/sections/{section.id}")

    assert response.status_code == 200
    assert "Creator Section" in response.text
    assert "Section Creator" in response.text


def test_section_detail_renders_for_assigned_member(
    client: TestClient,
    db: Session,
) -> None:
    creator = create_user(db)
    assigned = create_user(db)
    company = create_company(db)
    section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Assigned Detail Section",
    )
    create_section_membership(db, section=section, user=assigned)
    db.commit()
    _authenticate(client, db, user=assigned)

    response = client.get(f"/sections/{section.id}")

    assert response.status_code == 200
    assert "Assigned Detail Section" in response.text
    assert "Assigned Member" in response.text


def test_unassigned_user_cannot_view_section(
    client: TestClient,
    db: Session,
) -> None:
    creator = create_user(db)
    denied = create_user(db)
    company = create_company(db)
    section = create_section(
        db,
        company=company,
        created_by=creator,
    )
    db.commit()
    _authenticate(client, db, user=denied)

    response = client.get(
        f"/sections/{section.id}",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/companies?")


def test_creator_updates_section(
    client: TestClient,
    db: Session,
) -> None:
    creator = create_user(db)
    company = create_company(db)
    section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Before Section Edit",
    )
    db.commit()
    csrf_token = _authenticate(client, db, user=creator)

    response = client.post(
        f"/sections/{section.id}/edit",
        data={
            "csrf_token": csrf_token,
            "name": "After Section Edit",
            "description": "Updated.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    db.refresh(section)
    assert section.name == "After Section Edit"
    assert section.description == "Updated."


def test_assigned_member_cannot_edit_section(
    client: TestClient,
    db: Session,
) -> None:
    creator = create_user(db)
    assigned = create_user(db)
    company = create_company(db)
    section = create_section(
        db,
        company=company,
        created_by=creator,
    )
    create_section_membership(db, section=section, user=assigned)
    db.commit()
    _authenticate(client, db, user=assigned)

    response = client.get(
        f"/sections/{section.id}/edit",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        f"/sections/{section.id}?"
    )


def test_creator_archives_and_restores_section(
    client: TestClient,
    db: Session,
) -> None:
    creator = create_user(db)
    company = create_company(db)
    section = create_section(
        db,
        company=company,
        created_by=creator,
    )
    db.commit()
    csrf_token = _authenticate(client, db, user=creator)

    archive_response = client.post(
        f"/sections/{section.id}/archive",
        data={"csrf_token": csrf_token},
        follow_redirects=False,
    )

    assert archive_response.status_code == 303
    db.refresh(section)
    assert section.is_archived is True

    restore_response = client.post(
        f"/sections/{section.id}/restore",
        data={"csrf_token": csrf_token},
        follow_redirects=False,
    )

    assert restore_response.status_code == 303
    db.refresh(section)
    assert section.is_archived is False


def test_section_members_page_lists_available_company_members(
    client: TestClient,
    db: Session,
) -> None:
    creator = create_user(db)
    available = create_user(
        db,
        display_name="Available Section User",
    )
    company = create_company(db)
    create_company_membership(
        db,
        company=company,
        user=creator,
        role=CompanyRole.MANAGER,
    )
    create_company_membership(db, company=company, user=available)
    section = create_section(
        db,
        company=company,
        created_by=creator,
    )
    db.commit()
    _authenticate(client, db, user=creator)

    response = client.get(f"/sections/{section.id}/members")

    assert response.status_code == 200
    assert "Available Section User" in response.text


def test_creator_adds_and_removes_section_member(
    client: TestClient,
    db: Session,
) -> None:
    creator = create_user(db)
    target = create_user(db)
    company = create_company(db)
    create_company_membership(
        db,
        company=company,
        user=creator,
        role=CompanyRole.MANAGER,
    )
    create_company_membership(db, company=company, user=target)
    section = create_section(
        db,
        company=company,
        created_by=creator,
    )
    db.commit()
    csrf_token = _authenticate(client, db, user=creator)

    add_response = client.post(
        f"/sections/{section.id}/members",
        data={
            "csrf_token": csrf_token,
            "user_id": str(target.id),
        },
        follow_redirects=False,
    )

    assert add_response.status_code == 303

    membership = db.scalar(
        select(SectionMembership).where(
            SectionMembership.section_id == section.id,
            SectionMembership.user_id == target.id,
        )
    )
    assert membership is not None
    membership_id = membership.id

    remove_response = client.post(
        f"/sections/{section.id}/members/{target.id}/remove",
        data={"csrf_token": csrf_token},
        follow_redirects=False,
    )

    assert remove_response.status_code == 303
    assert db.scalar(
        select(SectionMembership).where(
            SectionMembership.id == membership_id,
        )
    ) is None


def test_section_mutations_require_csrf(
    client: TestClient,
    db: Session,
) -> None:
    creator = create_user(db)
    company = create_company(db)
    section = create_section(
        db,
        company=company,
        created_by=creator,
    )
    db.commit()
    _authenticate(client, db, user=creator)

    response = client.post(
        f"/sections/{section.id}/archive",
        data={},
        follow_redirects=False,
    )

    assert response.status_code == 403
