from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import CompanyRole
from app.services.task_history_service import (
    TaskHistoryService,
)
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
        display_name="History Creator",
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

    section_list = create_section_list(
        db,
        section=section,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="History Task",
    )

    return company, creator, section, task


def test_task_detail_renders_history_events(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, _, task = _create_context(db)

    TaskHistoryService.record_updated(
        db,
        task=task,
        actor=creator,
        changes={
            "title": {
                "previous": "Old title",
                "current": "History Task",
            },
        },
        commit=False,
    )
    db.commit()

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.get(
        f"/tasks/{task.id}",
    )

    assert response.status_code == 200
    assert "Task History" in response.text
    assert "updated this task" in response.text


def test_task_detail_history_renders_actor(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, _, task = _create_context(db)

    TaskHistoryService.record_created(
        db,
        task=task,
        actor=creator,
        commit=False,
    )
    db.commit()

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.get(
        f"/tasks/{task.id}",
    )

    assert response.status_code == 200
    assert creator.display_name in response.text


def test_task_detail_history_renders_empty_state(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, _, task = _create_context(db)
    db.commit()

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.get(
        f"/tasks/{task.id}",
    )

    assert response.status_code == 200
    assert "No task history is available." in (
        response.text
    )


def test_outsider_cannot_view_task_history(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, _, task = _create_context(db)

    TaskHistoryService.record_created(
        db,
        task=task,
        actor=creator,
        commit=False,
    )

    outsider = create_user(db)
    db.commit()

    _authenticate(
        client,
        db,
        user=outsider,
    )

    response = client.get(
        f"/tasks/{task.id}",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "created this task" not in response.text


def test_assigned_member_can_view_task_history(
    client: TestClient,
    db: Session,
) -> None:
    company, creator, section, task = (
        _create_context(db)
    )

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

    TaskHistoryService.record_created(
        db,
        task=task,
        actor=creator,
        commit=False,
    )
    db.commit()

    _authenticate(
        client,
        db,
        user=member,
    )

    response = client.get(
        f"/tasks/{task.id}",
    )

    assert response.status_code == 200
    assert "created this task" in response.text