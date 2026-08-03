from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import CompanyRole
from tests.factories import (
    create_auth_session,
    create_company,
    create_company_membership,
    create_section,
    create_section_list,
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

    creator = create_user(db)

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

    first_list = create_section_list(
        db,
        section=section,
        name="To Do",
        sort_position=1000,
    )

    second_list = create_section_list(
        db,
        section=section,
        name="In Progress",
        sort_position=2000,
    )

    first_task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        sort_position=1000,
    )

    second_task = create_task(
        db,
        section_list=second_list,
        created_by=creator,
        sort_position=1000,
    )

    db.commit()

    return (
        creator,
        section,
        first_list,
        second_list,
        first_task,
        second_task,
    )


def test_section_creator_reorders_lists(
    client: TestClient,
    db: Session,
) -> None:
    (
        creator,
        section,
        first_list,
        second_list,
        _,
        _,
    ) = _create_context(db)

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
                    "list_id": first_list.id,
                    "sort_position": 3000,
                },
                {
                    "list_id": second_list.id,
                    "sort_position": 1000,
                },
            ],
        },
        headers={
            "x-csrf-token": csrf_token,
        },
    )

    assert response.status_code == 200

    db.refresh(first_list)
    db.refresh(second_list)

    assert first_list.sort_position == 3000
    assert second_list.sort_position == 1000


def test_section_member_reorders_tasks(
    client: TestClient,
    db: Session,
) -> None:
    (
        creator,
        section,
        first_list,
        second_list,
        first_task,
        second_task,
    ) = _create_context(db)

    csrf_token = _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.post(
        f"/sections/{section.id}/tasks/reorder",
        json={
            "items": [
                {
                    "task_id": first_task.id,
                    "section_list_id": second_list.id,
                    "sort_position": 2000,
                },
                {
                    "task_id": second_task.id,
                    "section_list_id": first_list.id,
                    "sort_position": 500,
                },
            ],
        },
        headers={
            "x-csrf-token": csrf_token,
        },
    )

    assert response.status_code == 200

    db.refresh(first_task)
    db.refresh(second_task)

    assert first_task.section_list_id == second_list.id
    assert first_task.sort_position == 2000

    assert second_task.section_list_id == first_list.id
    assert second_task.sort_position == 500


def test_task_move_endpoint_moves_task(
    client: TestClient,
    db: Session,
) -> None:
    (
        creator,
        _,
        _,
        second_list,
        first_task,
        _,
    ) = _create_context(db)

    csrf_token = _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.post(
        f"/tasks/{first_task.id}/move",
        json={
            "destination_list_id": second_list.id,
            "sort_position": 2500,
        },
        headers={
            "x-csrf-token": csrf_token,
        },
    )

    assert response.status_code == 200

    db.refresh(first_task)

    assert first_task.section_list_id == second_list.id
    assert first_task.sort_position == 2500


def test_task_cannot_move_to_other_section(
    client: TestClient,
    db: Session,
) -> None:
    (
        creator,
        section,
        first_list,
        _,
        first_task,
        _,
    ) = _create_context(db)

    other_section = create_section(
        db,
        company=section.company,
        created_by=creator,
        name="Other Section",
    )

    foreign_list = create_section_list(
        db,
        section=other_section,
    )
    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=creator,
    )

    original_list_id = first_task.section_list_id

    response = client.post(
        f"/tasks/{first_task.id}/move",
        json={
            "destination_list_id": foreign_list.id,
            "sort_position": 1000,
        },
        headers={
            "x-csrf-token": csrf_token,
        },
    )

    assert response.status_code == 403

    db.refresh(first_task)

    assert first_task.section_list_id == original_list_id
    assert first_task.section_list_id == first_list.id


def test_reordering_requires_csrf(
    client: TestClient,
    db: Session,
) -> None:
    (
        creator,
        section,
        first_list,
        _,
        _,
        _,
    ) = _create_context(db)

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.post(
        f"/sections/{section.id}/lists/reorder",
        json={
            "items": [
                {
                    "list_id": first_list.id,
                    "sort_position": 2000,
                },
            ],
        },
    )

    assert response.status_code == 403