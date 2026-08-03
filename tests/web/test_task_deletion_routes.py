from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import CompanyRole
from app.core.timezone import utc_now
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
    *,
    company_name: str | None = None,
    section_name: str | None = None,
    task_title: str = "Deletion Task",
):
    company = create_company(
        db,
        name=company_name,
    )

    creator = create_user(
        db,
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
        name=section_name,
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title=task_title,
    )

    db.commit()

    return (
        company,
        creator,
        section,
        task,
    )


def _mark_deleted(
    db: Session,
    *,
    task,
    deleted_by,
    deleted_at=None,
) -> None:
    task.deleted_by = deleted_by
    task.deleted_at = (
        deleted_at
        or utc_now()
    )

    db.commit()


def test_section_creator_soft_deletes_task(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, section, task = _create_context(
        db,
    )

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

    assert response.headers[
        "location"
    ].startswith(
        f"/sections/{section.id}?"
    )

    db.refresh(
        task,
    )

    assert task.deleted_at is not None
    assert task.deleted_by_user_id == creator.id


def test_assigned_member_cannot_delete_task(
    client: TestClient,
    db: Session,
) -> None:
    company, _, section, task = _create_context(
        db,
    )

    member = create_user(
        db,
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
        f"/tasks/{task.id}/delete",
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    db.refresh(
        task,
    )

    assert task.deleted_at is None


def test_section_creator_restores_deleted_task(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, _, task = _create_context(
        db,
    )

    _mark_deleted(
        db,
        task=task,
        deleted_by=creator,
    )

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

    db.refresh(
        task,
    )

    assert task.deleted_at is None
    assert task.deleted_by_user_id is None


def test_deleted_tasks_page_requires_administrator(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, _, _ = _create_context(
        db,
    )

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
    _, creator, _, task = _create_context(
        db,
    )

    _mark_deleted(
        db,
        task=task,
        deleted_by=creator,
    )

    administrator = create_administrator(
        db,
    )

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


def test_deleted_task_page_searches_tasks(
    client: TestClient,
    db: Session,
) -> None:
    _, first_creator, _, matching = _create_context(
        db,
        task_title="Order coffee",
    )

    _, second_creator, _, hidden = _create_context(
        db,
        task_title="Clean cellar",
    )

    _mark_deleted(
        db,
        task=matching,
        deleted_by=first_creator,
    )

    _mark_deleted(
        db,
        task=hidden,
        deleted_by=second_creator,
    )

    administrator = create_administrator(
        db,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/admin/deleted-tasks?search=coffee",
    )

    assert response.status_code == 200
    assert matching.title in response.text
    assert hidden.title not in response.text


def test_deleted_task_page_filters_by_company(
    client: TestClient,
    db: Session,
) -> None:
    (
        company,
        first_creator,
        _,
        matching,
    ) = _create_context(
        db,
        company_name="Matching Company",
        task_title="Matching Company Task",
    )

    _, second_creator, _, hidden = _create_context(
        db,
        company_name="Other Company",
        task_title="Other Company Task",
    )

    _mark_deleted(
        db,
        task=matching,
        deleted_by=first_creator,
    )

    _mark_deleted(
        db,
        task=hidden,
        deleted_by=second_creator,
    )

    administrator = create_administrator(
        db,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        (
            "/admin/deleted-tasks"
            f"?company_id={company.id}"
        ),
    )

    assert response.status_code == 200
    assert matching.title in response.text
    assert hidden.title not in response.text


def test_deleted_task_page_filters_by_section(
    client: TestClient,
    db: Session,
) -> None:
    (
        _,
        first_creator,
        section,
        matching,
    ) = _create_context(
        db,
        section_name="Matching Section",
        task_title="Matching Section Task",
    )

    _, second_creator, _, hidden = _create_context(
        db,
        section_name="Other Section",
        task_title="Other Section Task",
    )

    _mark_deleted(
        db,
        task=matching,
        deleted_by=first_creator,
    )

    _mark_deleted(
        db,
        task=hidden,
        deleted_by=second_creator,
    )

    administrator = create_administrator(
        db,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        (
            "/admin/deleted-tasks"
            f"?section_id={section.id}"
        ),
    )

    assert response.status_code == 200
    assert matching.title in response.text
    assert hidden.title not in response.text


def test_deleted_task_page_filters_by_deleting_user(
    client: TestClient,
    db: Session,
) -> None:
    deleting_user = create_user(
        db,
        display_name="Deleting User",
    )

    _, first_creator, _, matching = _create_context(
        db,
        task_title="Matching User Task",
    )

    _, second_creator, _, hidden = _create_context(
        db,
        task_title="Other User Task",
    )

    _mark_deleted(
        db,
        task=matching,
        deleted_by=deleting_user,
    )

    _mark_deleted(
        db,
        task=hidden,
        deleted_by=second_creator,
    )

    administrator = create_administrator(
        db,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        (
            "/admin/deleted-tasks"
            f"?deleted_by_user_id={deleting_user.id}"
        ),
    )

    assert response.status_code == 200
    assert matching.title in response.text
    assert hidden.title not in response.text
    assert first_creator.id != deleting_user.id


def test_deleted_task_page_filters_by_date(
    client: TestClient,
    db: Session,
) -> None:
    _, first_creator, _, matching = _create_context(
        db,
        task_title="Recent Deleted Task",
    )

    _, second_creator, _, hidden = _create_context(
        db,
        task_title="Old Deleted Task",
    )

    _mark_deleted(
        db,
        task=matching,
        deleted_by=first_creator,
        deleted_at=utc_now(),
    )

    _mark_deleted(
        db,
        task=hidden,
        deleted_by=second_creator,
        deleted_at=utc_now() - timedelta(
            days=30,
        ),
    )

    administrator = create_administrator(
        db,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    from_date = (
        utc_now().date()
        - timedelta(
            days=2,
        )
    ).isoformat()

    response = client.get(
        (
            "/admin/deleted-tasks"
            f"?deleted_from={from_date}"
        ),
    )

    assert response.status_code == 200
    assert matching.title in response.text
    assert hidden.title not in response.text


def test_deleted_task_page_paginates_results(
    client: TestClient,
    db: Session,
) -> None:
    _, first_creator, _, first = _create_context(
        db,
        task_title="Newest Deleted Task",
    )

    _, second_creator, _, second = _create_context(
        db,
        task_title="Older Deleted Task",
    )

    _mark_deleted(
        db,
        task=first,
        deleted_by=first_creator,
        deleted_at=utc_now(),
    )

    _mark_deleted(
        db,
        task=second,
        deleted_by=second_creator,
        deleted_at=utc_now() - timedelta(
            days=1,
        ),
    )

    administrator = create_administrator(
        db,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    first_page = client.get(
        (
            "/admin/deleted-tasks"
            "?page=1&page_size=1"
        ),
    )

    second_page = client.get(
        (
            "/admin/deleted-tasks"
            "?page=2&page_size=1"
        ),
    )

    assert first_page.status_code == 200
    assert second_page.status_code == 200

    assert first.title in first_page.text
    assert second.title not in first_page.text

    assert second.title in second_page.text
    assert first.title not in second_page.text


def test_invalid_deleted_task_filter_returns_422(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/admin/deleted-tasks?page_size=invalid",
    )

    assert response.status_code == 422

    assert (
        "Check the selected filters"
        in response.text
    )


def test_administrator_restores_deleted_task(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, _, task = _create_context(
        db,
    )

    _mark_deleted(
        db,
        task=task,
        deleted_by=creator,
    )

    administrator = create_administrator(
        db,
    )

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

    db.refresh(
        task,
    )

    assert task.deleted_at is None


def test_administrator_permanently_deletes_task(
    client: TestClient,
    db: Session,
) -> None:
    _, creator, _, task = _create_context(
        db,
    )

    create_task_comment(
        db,
        task=task,
        user=creator,
    )

    _mark_deleted(
        db,
        task=task,
        deleted_by=creator,
    )

    task_id = task.id

    administrator = create_administrator(
        db,
    )

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
    _, creator, _, task = _create_context(
        db,
    )

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