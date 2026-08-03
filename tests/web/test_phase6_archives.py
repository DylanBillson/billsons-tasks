from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from tests.factories import (
    create_administrator,
    create_auth_session,
    create_company,
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
):
    _, session_token, csrf_token = (
        create_auth_session(
            db,
            user=user,
        )
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


def test_archived_company_appears_in_administration_archive(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    archived_company = create_company(
        db,
        name="Phase Six Archived Company",
        is_archived=True,
    )

    active_company = create_company(
        db,
        name="Phase Six Active Company",
        is_archived=False,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/admin/archived-companies",
    )

    assert response.status_code == 200
    assert archived_company.name in response.text
    assert active_company.name not in response.text


def test_archived_section_appears_in_administration_archive(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    company = create_company(
        db,
    )

    archived_section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Phase Six Archived Section",
        is_archived=True,
    )

    active_section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Phase Six Active Section",
        is_archived=False,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/admin/archived-sections",
    )

    assert response.status_code == 200
    assert archived_section.name in response.text
    assert active_section.name not in response.text


def test_deleted_task_appears_in_deleted_task_administration(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    company = create_company(
        db,
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

    deleted_task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Phase Six Deleted Task",
        deleted_by=creator,
    )

    active_task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Phase Six Active Task",
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
    assert deleted_task.title in response.text
    assert active_task.title not in response.text


def test_administrator_restores_archived_company(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    company = create_company(
        db,
        name="Company To Restore",
        is_archived=True,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        (
            f"/admin/archived-companies/"
            f"{company.id}/restore"
        ),
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    db.refresh(
        company,
    )

    assert company.is_archived is False


def test_administrator_restores_archived_section(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    company = create_company(
        db,
    )

    section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Section To Restore",
        is_archived=True,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        (
            f"/admin/archived-sections/"
            f"{section.id}/restore"
        ),
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    db.refresh(
        section,
    )

    assert section.is_archived is False


def test_administrator_restores_deleted_task(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    company = create_company(
        db,
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
        title="Deleted Task To Restore",
        deleted_by=creator,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        (
            f"/admin/deleted-tasks/"
            f"{task.id}/restore"
        ),
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


def test_archive_restore_actions_require_csrf(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    company = create_company(
        db,
        is_archived=True,
    )

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        (
            f"/admin/archived-companies/"
            f"{company.id}/restore"
        ),
        data={},
        follow_redirects=False,
    )

    assert response.status_code == 403

    db.refresh(
        company,
    )

    assert company.is_archived is True


def test_standard_user_cannot_view_archive_administration(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    _authenticate(
        client,
        db,
        user=user,
    )

    for path in (
        "/admin/archived-companies",
        "/admin/archived-sections",
        "/admin/deleted-tasks",
    ):
        response = client.get(
            path,
            follow_redirects=False,
        )

        assert response.status_code == 403