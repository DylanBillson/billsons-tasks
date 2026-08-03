from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import CompanyRole
from app.models.task_assignee import TaskAssignee
from tests.factories import (
    create_auth_session,
    create_company,
    create_company_membership,
    create_section,
    create_section_list,
    create_section_membership,
    create_task,
    create_task_assignee,
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

    section_list = create_section_list(
        db,
        section=section,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
    )

    assignee = create_user(
        db,
        display_name="Available Assignee",
    )

    create_company_membership(
        db,
        company=company,
        user=assignee,
    )
    create_section_membership(
        db,
        section=section,
        user=assignee,
    )

    db.commit()

    return company, creator, section, task, assignee


def test_section_creator_adds_task_assignee(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, _, task, assignee = (
        _create_context(db)
    )

    csrf_token = _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.post(
        f"/tasks/{task.id}/assignees",
        data={
            "csrf_token": csrf_token,
            "user_id": str(assignee.id),
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        f"/tasks/{task.id}?"
    )

    assignment = db.scalar(
        select(TaskAssignee).where(
            TaskAssignee.task_id == task.id,
            TaskAssignee.user_id == assignee.id,
        )
    )

    assert assignment is not None


def test_assigned_member_cannot_manage_task_assignees(
    client: TestClient,
    db: Session,
) -> None:
    company, _, section, task, assignee = (
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

    response = client.post(
        f"/tasks/{task.id}/assignees",
        data={
            "csrf_token": csrf_token,
            "user_id": str(assignee.id),
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    assignment = db.scalar(
        select(TaskAssignee).where(
            TaskAssignee.task_id == task.id,
            TaskAssignee.user_id == assignee.id,
        )
    )

    assert assignment is None


def test_cannot_assign_user_without_section_access(
    client: TestClient,
    db: Session,
) -> None:
    company, creator, _, task, _ = (
        _create_context(db)
    )

    company_only_user = create_user(db)

    create_company_membership(
        db,
        company=company,
        user=company_only_user,
    )
    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.post(
        f"/tasks/{task.id}/assignees",
        data={
            "csrf_token": csrf_token,
            "user_id": str(company_only_user.id),
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    assignment = db.scalar(
        select(TaskAssignee).where(
            TaskAssignee.task_id == task.id,
            TaskAssignee.user_id
            == company_only_user.id,
        )
    )

    assert assignment is None


def test_section_creator_removes_task_assignee(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, _, task, assignee = (
        _create_context(db)
    )

    assignment = create_task_assignee(
        db,
        task=task,
        user=assignee,
    )
    assignment_id = assignment.id
    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.post(
        (
            f"/tasks/{task.id}/assignees/"
            f"{assignee.id}/remove"
        ),
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert db.get(
        TaskAssignee,
        assignment_id,
    ) is None


def test_replace_task_assignees(
    client: TestClient,
    db: Session,
) -> None:
    company, creator, section, task, first_user = (
        _create_context(db)
    )

    second_user = create_user(
        db,
        display_name="Second Assignee",
    )

    create_company_membership(
        db,
        company=company,
        user=second_user,
    )
    create_section_membership(
        db,
        section=section,
        user=second_user,
    )

    create_task_assignee(
        db,
        task=task,
        user=first_user,
    )
    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.post(
        f"/tasks/{task.id}/assignees/replace",
        data={
            "csrf_token": csrf_token,
            "user_ids": [
                str(second_user.id),
            ],
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    assignments = list(
        db.scalars(
            select(TaskAssignee).where(
                TaskAssignee.task_id == task.id,
            )
        ).all()
    )

    assert {
        assignment.user_id
        for assignment in assignments
    } == {
        second_user.id,
    }


def test_task_assignee_mutation_requires_csrf(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, _, task, assignee = (
        _create_context(db)
    )

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.post(
        f"/tasks/{task.id}/assignees",
        data={
            "user_id": str(assignee.id),
        },
        follow_redirects=False,
    )

    assert response.status_code == 403