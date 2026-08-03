from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import CompanyRole
from app.models.task import Task
from tests.factories import (
    create_administrator,
    create_auth_session,
    create_company,
    create_company_membership,
    create_section,
    create_section_list,
    create_section_membership,
    create_task,
    create_task_comment,
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

    section_list = create_section_list(
        db,
        section=section,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Deletion Task",
    )

    db.commit()

    return company, creator, section, task


def test_section_creator_soft_deletes_task(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, section, task = _create_context(db)

    csrf_token = _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.post(
        f"/tasks/{task.id}/delete",
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        f"/sections/{section.id}?"
    )

    db.refresh(task)

    assert task.deleted_at is not None
    assert task.deleted_by_user_id == creator.id


def test_assigned_member_cannot_delete_task(
    client: TestClient,
    db: Session,
) -> None:
    company, _, section, task = _create_context(db)

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
        f"/tasks/{task.id}/delete",
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    db.refresh(task)
    assert task.deleted_at is None


def test_section_creator_restores_deleted_task(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, _, task = _create_context(db)

    task.deleted_by = creator

    from app.core.timezone import utc_now

    task.deleted_at = utc_now()
    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.post(
        f"/tasks/{task.id}/restore",
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    db.refresh(task)

    assert task.deleted_at is None
    assert task.deleted_by_user_id is None


def test_deleted_tasks_page_requires_administrator(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, _, _ = _create_context(db)

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.get(
        "/admin/deleted-tasks",
        follow_redirects=False,
    )

    assert response.status_code == 403


def test_administrator_views_deleted_tasks(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, _, task = _create_context(db)

    task.deleted_by = creator

    from app.core.timezone import utc_now

    task.deleted_at = utc_now()

    administrator = create_administrator(db)
    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/admin/deleted-tasks",
    )

    assert response.status_code == 200
    assert "Deletion Task" in response.text


def test_administrator_restores_deleted_task(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, _, task = _create_context(db)

    task.deleted_by = creator

    from app.core.timezone import utc_now

    task.deleted_at = utc_now()

    administrator = create_administrator(db)
    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        f"/admin/deleted-tasks/{task.id}/restore",
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    db.refresh(task)
    assert task.deleted_at is None


def test_administrator_permanently_deletes_task(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, _, task = _create_context(db)

    create_task_comment(
        db,
        task=task,
        user=creator,
    )

    task.deleted_by = creator

    from app.core.timezone import utc_now

    task.deleted_at = utc_now()

    task_id = task.id

    administrator = create_administrator(db)
    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        (
            f"/admin/deleted-tasks/{task_id}"
            "/delete-permanently"
        ),
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert db.get(
        Task,
        task_id,
    ) is None


def test_task_deletion_requires_csrf(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, _, task = _create_context(db)

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.post(
        f"/tasks/{task.id}/delete",
        data={},
        follow_redirects=False,
    )

    assert response.status_code == 403