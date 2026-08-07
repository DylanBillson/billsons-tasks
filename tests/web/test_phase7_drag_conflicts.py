from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timezone import utc_now
from app.services.live_update_service import (
    LiveUpdateService,
)
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


def _create_board(
    db: Session,
):
    creator = create_user(
        db,
    )

    company = create_company(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=creator,
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
        title="First Task",
        sort_position=1000,
    )

    second_task = create_task(
        db,
        section_list=second_list,
        created_by=creator,
        title="Second Task",
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


def test_phase7_current_revision_allows_task_drag(
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
    ) = _create_board(
        db,
    )

    revision = (
        LiveUpdateService.get_section_revision(
            db,
            actor=creator,
            section_id=section.id,
        )
    )

    csrf_token = _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.post(
        f"/sections/{section.id}/tasks/reorder",
        json={
            "known_revision": revision.revision,
            "items": [
                {
                    "task_id": first_task.id,
                    "section_list_id": second_list.id,
                    "sort_position": 2000,
                },
                {
                    "task_id": second_task.id,
                    "section_list_id": first_list.id,
                    "sort_position": 1000,
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
    assert second_task.sort_position == 1000


def test_phase7_stale_task_drag_returns_conflict(
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
    ) = _create_board(
        db,
    )

    stale_revision = (
        LiveUpdateService.get_section_revision(
            db,
            actor=creator,
            section_id=section.id,
        )
    )

    first_task.title = "Changed by another user"

    first_task.updated_at = (
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
        f"/sections/{section.id}/tasks/reorder",
        json={
            "known_revision": stale_revision.revision,
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

    assert response.status_code == 409

    payload = response.json()

    assert payload["code"] == "live_update_conflict"

    assert (
        payload["current_revision"]
        != stale_revision.revision
    )

    assert "board changed" in payload["detail"]

    db.refresh(first_task)
    db.refresh(second_task)

    assert first_task.section_list_id == first_list.id
    assert first_task.sort_position == 1000

    assert second_task.section_list_id == second_list.id
    assert second_task.sort_position == 1000


def test_phase7_stale_list_drag_returns_conflict(
    client: TestClient,
    db: Session,
) -> None:
    (
        creator,
        section,
        first_list,
        second_list,
        first_task,
        _,
    ) = _create_board(
        db,
    )

    stale_revision = (
        LiveUpdateService.get_section_revision(
            db,
            actor=creator,
            section_id=section.id,
        )
    )

    first_task.title = "Concurrent board change"

    first_task.updated_at = (
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
            "known_revision": stale_revision.revision,
            "items": [
                {
                    "list_id": second_list.id,
                    "sort_position": 1000,
                },
                {
                    "list_id": first_list.id,
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

    db.refresh(first_list)
    db.refresh(second_list)

    assert first_list.sort_position == 1000
    assert second_list.sort_position == 2000


def test_phase7_drag_without_revision_remains_compatible(
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
    ) = _create_board(
        db,
    )

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
                    "list_id": second_list.id,
                    "sort_position": 1000,
                },
                {
                    "list_id": first_list.id,
                    "sort_position": 2000,
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

    assert first_list.sort_position == 2000
    assert second_list.sort_position == 1000