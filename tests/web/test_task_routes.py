from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import CompanyRole
from app.models.task import Task
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

    first_list = create_section_list(
        db,
        section=section,
        name="To Do",
    )

    second_list = create_section_list(
        db,
        section=section,
        name="In Progress",
    )

    db.commit()

    return (
        company,
        creator,
        section,
        first_list,
        second_list,
    )


def test_task_create_page_requires_authentication(
    client: TestClient,
    db: Session,
) -> None:
    _, _, _, section_list, _ = _create_context(db)

    response = client.get(
        f"/section-lists/{section_list.id}/tasks/create",
        headers={
            "accept": "text/html",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303


def test_section_member_can_render_task_create_page(
    client: TestClient,
    db: Session,
) -> None:
    company, _, section, section_list, _ = (
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
    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=member,
    )

    response = client.get(
        f"/section-lists/{section_list.id}/tasks/create",
    )

    assert response.status_code == 200
    assert "Create Task" in response.text
    assert 'name="title"' in response.text
    assert 'name="description"' in response.text
    assert 'name="due_at"' in response.text
    assert csrf_token in response.text


def test_section_member_creates_task(
    client: TestClient,
    db: Session,
) -> None:
    company, _, section, section_list, _ = (
        _create_context(db)
    )

    member = create_user(
        db,
        display_name="Task Creator",
    )

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

    csrf_token = _authenticate(
        client,
        db,
        user=member,
    )

    response = client.post(
        f"/section-lists/{section_list.id}/tasks/create",
        data={
            "csrf_token": csrf_token,
            "section_list_id": str(section_list.id),
            "title": "Complete stock count",
            "description": "Count all remaining stock.",
            "due_at": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    task = db.scalar(
        select(Task).where(
            Task.section_list_id == section_list.id,
            Task.title == "Complete stock count",
        )
    )

    assert task is not None
    assert task.created_by_user_id == member.id
    assert response.headers["location"].startswith(
        f"/tasks/{task.id}"
    )


def test_task_create_rejects_blank_title(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, _, section_list, _ = (
        _create_context(db)
    )

    csrf_token = _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.post(
        f"/section-lists/{section_list.id}/tasks/create",
        data={
            "csrf_token": csrf_token,
            "section_list_id": str(section_list.id),
            "title": "",
            "description": "",
            "due_at": "",
        },
    )

    assert response.status_code == 422


def test_task_detail_renders_for_section_member(
    client: TestClient,
    db: Session,
) -> None:
    company, creator, section, section_list, _ = (
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

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Visible Task",
        description="Visible task description.",
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
    assert "Visible Task" in response.text
    assert "Visible task description." in response.text
    assert section_list.name in response.text


def test_section_member_updates_task(
    client: TestClient,
    db: Session,
) -> None:
    company, creator, section, section_list, _ = (
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

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Old Task",
    )
    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=member,
    )

    response = client.post(
        f"/tasks/{task.id}/edit",
        data={
            "csrf_token": csrf_token,
            "title": "Updated Task",
            "description": "Updated description.",
            "due_at": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    db.refresh(task)

    assert task.title == "Updated Task"
    assert task.description == "Updated description."


def test_section_member_completes_and_reopens_task(
    client: TestClient,
    db: Session,
) -> None:
    company, creator, section, section_list, _ = (
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

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
    )
    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=member,
    )

    complete_response = client.post(
        f"/tasks/{task.id}/complete",
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert complete_response.status_code == 303

    db.refresh(task)
    assert task.completed_at is not None
    assert task.completed_by_user_id == member.id

    reopen_response = client.post(
        f"/tasks/{task.id}/reopen",
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert reopen_response.status_code == 303

    db.refresh(task)
    assert task.completed_at is None
    assert task.completed_by_user_id is None


def test_task_mutation_requires_csrf(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, _, section_list, _ = (
        _create_context(db)
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
    )
    db.commit()

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.post(
        f"/tasks/{task.id}/complete",
        data={},
        follow_redirects=False,
    )

    assert response.status_code == 403


def test_task_create_page_renders_structured_assignee_choices(
    client: TestClient,
    db: Session,
) -> None:
    company, creator, section, section_list, _ = _create_context(db)
    assignee = create_user(
        db,
        display_name="Structured Assignee",
        username="structured.assignee",
    )
    create_company_membership(db, company=company, user=assignee)
    create_section_membership(db, section=section, user=assignee)
    db.commit()
    _authenticate(client, db, user=creator)
    response = client.get(
        f"/section-lists/{section_list.id}/tasks/create",
    )
    assert response.status_code == 200
    assert "task-assignee-choice-list" in response.text
    assert "task-assignee-choice-control" in response.text
    assert "task-assignee-choice-user" in response.text
    assert "Structured Assignee" in response.text
    assert "structured.assignee" in response.text
    assert 'name="assignee_user_ids"' in response.text


def test_task_detail_renders_description_as_prominent_section(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, _, section_list, _ = _create_context(db)
    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Prominent Description Task",
        description="Prominent description content.",
    )
    db.commit()
    _authenticate(client, db, user=creator)
    response = client.get(f"/tasks/{task.id}")
    assert response.status_code == 200
    assert 'id="task-description-heading"' in response.text
    assert "task-description-card" in response.text
    assert "task-description-content" in response.text
    assert "Prominent description content." in response.text


def test_task_detail_renders_compact_due_datetime(
    client: TestClient,
    db: Session,
) -> None:
    from datetime import UTC, datetime
    _, creator, _, section_list, _ = _create_context(db)
    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        due_at=datetime(2026, 8, 7, 11, 0, tzinfo=UTC),
    )
    db.commit()
    _authenticate(client, db, user=creator)
    response = client.get(f"/tasks/{task.id}")
    assert response.status_code == 200
    assert "12:00 07/08/26" in response.text
    assert 'datetime="2026-08-07T11:00:00+00:00"' in response.text
