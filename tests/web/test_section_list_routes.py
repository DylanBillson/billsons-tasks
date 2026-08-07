from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import timedelta

from app.core.timezone import utc_now
from app.services.live_update_service import (
    LiveUpdateService,
)
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

def test_section_creator_reorders_complete_active_list_snapshot(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    first = create_section_list(
        db,
        section=section,
        name="First",
        sort_position=1000,
    )

    second = create_section_list(
        db,
        section=section,
        name="Second",
        sort_position=2000,
    )

    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.post(
        f"/sections/{section.id}/lists/reorder",
        json={
            "items": [
                {
                    "list_id": second.id,
                    "sort_position": 1000,
                },
                {
                    "list_id": first.id,
                    "sort_position": 2000,
                },
            ],
        },
        headers={
            "x-csrf-token": csrf_token,
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "section_id": section.id,
        "items": [
            {
                "list_id": second.id,
                "sort_position": 1000,
            },
            {
                "list_id": first.id,
                "sort_position": 2000,
            },
        ],
    }


def test_list_reorder_rejects_partial_snapshot(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    first = create_section_list(
        db,
        section=section,
        sort_position=1000,
    )

    second = create_section_list(
        db,
        section=section,
        sort_position=2000,
    )

    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.post(
        f"/sections/{section.id}/lists/reorder",
        json={
            "items": [
                {
                    "list_id": first.id,
                    "sort_position": 2000,
                },
            ],
        },
        headers={
            "x-csrf-token": csrf_token,
        },
    )

    assert response.status_code == 422
    assert (
        "include every active list"
        in response.json()["detail"]
    )

    db.refresh(first)
    db.refresh(second)

    assert first.sort_position == 1000
    assert second.sort_position == 2000


def test_list_reorder_rejects_archived_list(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    active = create_section_list(
        db,
        section=section,
        sort_position=1000,
    )

    archived = create_section_list(
        db,
        section=section,
        sort_position=2000,
        is_archived=True,
    )

    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.post(
        f"/sections/{section.id}/lists/reorder",
        json={
            "items": [
                {
                    "list_id": active.id,
                    "sort_position": 2000,
                },
                {
                    "list_id": archived.id,
                    "sort_position": 1000,
                },
            ],
        },
        headers={
            "x-csrf-token": csrf_token,
        },
    )

    assert response.status_code == 422
    assert (
        "archived or does not belong"
        in response.json()["detail"]
    )


def test_list_reorder_rejects_malformed_json(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.post(
        f"/sections/{section.id}/lists/reorder",
        content="{invalid-json",
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "x-csrf-token": csrf_token,
        },
    )

    assert response.status_code == 422

    assert response.json() == {
        "detail": (
            "The list order request "
            "was not valid JSON."
        ),
    }

def test_list_reorder_returns_conflict_for_stale_revision(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    first = create_section_list(
        db,
        section=section,
        name="First",
        sort_position=1000,
    )

    second = create_section_list(
        db,
        section=section,
        name="Second",
        sort_position=2000,
    )

    db.commit()

    stale_revision = (
        LiveUpdateService.get_section_revision(
            db,
            actor=creator,
            section_id=section.id,
        )
    )

    first.name = "Changed elsewhere"
    first.updated_at = (
        utc_now()
        + timedelta(
            seconds=1,
        )
    )

    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.post(
        f"/sections/{section.id}/lists/reorder",
        json={
            "known_revision": (
                stale_revision.revision
            ),
            "items": [
                {
                    "list_id": second.id,
                    "sort_position": 1000,
                },
                {
                    "list_id": first.id,
                    "sort_position": 2000,
                },
            ],
        },
        headers={
            "x-csrf-token": csrf_token,
        },
    )

    assert response.status_code == 409

    payload = response.json()

    assert payload["code"] == "live_update_conflict"

    assert (
        payload["current_revision"]
        != stale_revision.revision
    )

    assert "board changed" in payload["detail"]

    db.refresh(
        first,
    )
    db.refresh(
        second,
    )

    assert first.sort_position == 1000
    assert second.sort_position == 2000