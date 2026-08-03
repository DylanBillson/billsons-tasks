from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import CompanyRole
from app.models.section_list import SectionList
from tests.factories import (
    create_auth_session,
    create_company,
    create_company_membership,
    create_section,
    create_section_list,
    create_section_membership,
    create_task,
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


def _create_context(
    db: Session,
):
    company = create_company(db)

    creator = create_user(
        db,
        display_name="Section Creator",
    )

    create_company_membership(
        db,
        company=company,
        user=creator,
        role=CompanyRole.MANAGER,
    )

    section = create_section(
        db,
        company=company,
        created_by=creator,
    )

    db.commit()

    return company, creator, section


def test_section_list_create_requires_authentication(
    client: TestClient,
    db: Session,
) -> None:
    _, _, section = _create_context(db)

    response = client.get(
        f"/sections/{section.id}/lists/create",
        headers={
            "accept": "text/html",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/login?next_url="
        f"%2Fsections%2F{section.id}%2Flists%2Fcreate"
    )


def test_section_creator_can_render_list_create_page(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, section = _create_context(db)
    csrf_token = _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.get(
        f"/sections/{section.id}/lists/create",
    )

    assert response.status_code == 200
    assert "Create List" in response.text
    assert 'name="name"' in response.text
    assert 'name="description"' in response.text
    assert csrf_token in response.text


def test_assigned_member_cannot_create_list(
    client: TestClient,
    db: Session,
) -> None:
    company, _, section = _create_context(db)

    member = create_user(db)

    create_company_membership(
        db,
        company=company,
        user=member,
    )
    create_section_membership(
        db,
        section=section,
        user=member,
    )
    db.commit()

    _authenticate(
        client,
        db,
        user=member,
    )

    response = client.get(
        f"/sections/{section.id}/lists/create",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        f"/sections/{section.id}?"
    )


def test_section_creator_creates_list(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, section = _create_context(db)
    csrf_token = _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.post(
        f"/sections/{section.id}/lists/create",
        data={
            "csrf_token": csrf_token,
            "name": "To Do",
            "description": "Tasks waiting to begin.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        f"/sections/{section.id}?"
    )

    section_list = db.scalar(
        select(SectionList).where(
            SectionList.section_id == section.id,
            SectionList.name == "To Do",
        )
    )

    assert section_list is not None
    assert section_list.description == (
        "Tasks waiting to begin."
    )


def test_section_list_create_rejects_duplicate_name(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, section = _create_context(db)

    create_section_list(
        db,
        section=section,
        name="To Do",
    )
    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.post(
        f"/sections/{section.id}/lists/create",
        data={
            "csrf_token": csrf_token,
            "name": "To Do",
            "description": "",
        },
    )

    assert response.status_code == 422
    assert "already exists" in response.text


def test_section_creator_edits_list(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, section = _create_context(db)

    section_list = create_section_list(
        db,
        section=section,
        name="Old Name",
    )
    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.post(
        f"/section-lists/{section_list.id}/edit",
        data={
            "csrf_token": csrf_token,
            "name": "New Name",
            "description": "Updated description.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    db.refresh(section_list)

    assert section_list.name == "New Name"
    assert section_list.description == (
        "Updated description."
    )


def test_section_creator_archives_and_restores_list(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, section = _create_context(db)

    section_list = create_section_list(
        db,
        section=section,
    )
    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=creator,
    )

    archive_response = client.post(
        f"/section-lists/{section_list.id}/archive",
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert archive_response.status_code == 303

    db.refresh(section_list)
    assert section_list.is_archived is True

    restore_response = client.post(
        f"/section-lists/{section_list.id}/restore",
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert restore_response.status_code == 303

    db.refresh(section_list)
    assert section_list.is_archived is False


def test_empty_list_can_be_deleted(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, section = _create_context(db)

    section_list = create_section_list(
        db,
        section=section,
    )
    section_list_id = section_list.id
    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.post(
        f"/section-lists/{section_list_id}/delete",
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert db.get(
        SectionList,
        section_list_id,
    ) is None


def test_non_empty_list_cannot_be_deleted(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, section = _create_context(db)

    section_list = create_section_list(
        db,
        section=section,
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
    )
    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.post(
        f"/section-lists/{section_list.id}/delete",
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert db.get(
        SectionList,
        section_list.id,
    ) is not None


def test_section_list_mutation_requires_csrf(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, section = _create_context(db)

    section_list = create_section_list(
        db,
        section=section,
    )
    db.commit()

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.post(
        f"/section-lists/{section_list.id}/archive",
        data={},
        follow_redirects=False,
    )

    assert response.status_code == 403