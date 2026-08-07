from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
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
) -> None:
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


def _create_section_context(
    db: Session,
    *,
    company_name: str,
):
    creator = create_user(
        db,
    )

    company = create_company(
        db,
        name=company_name,
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

    section_list = create_section_list(
        db,
        section=section,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
    )

    return (
        creator,
        company,
        section,
        task,
    )


def test_unrelated_user_cannot_poll_section_revision(
    client: TestClient,
    db: Session,
) -> None:
    _, _, section, _ = _create_section_context(
        db,
        company_name="Private Company",
    )

    unrelated_user = create_user(
        db,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=unrelated_user,
    )

    response = client.get(
        (
            "/api/live-updates/sections/"
            f"{section.id}/revision"
        ),
    )

    assert response.status_code == 404


def test_unrelated_user_cannot_poll_task_revision(
    client: TestClient,
    db: Session,
) -> None:
    _, _, _, task = _create_section_context(
        db,
        company_name="Private Task Company",
    )

    unrelated_user = create_user(
        db,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=unrelated_user,
    )

    response = client.get(
        (
            "/api/live-updates/tasks/"
            f"{task.id}/revision"
        ),
    )

    assert response.status_code == 404


def test_company_member_without_section_access_cannot_poll(
    client: TestClient,
    db: Session,
) -> None:
    _, company, section, task = (
        _create_section_context(
            db,
            company_name="Restricted Company",
        )
    )

    company_member = create_user(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=company_member,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=company_member,
    )

    section_response = client.get(
        (
            "/api/live-updates/sections/"
            f"{section.id}/revision"
        ),
    )

    task_response = client.get(
        (
            "/api/live-updates/tasks/"
            f"{task.id}/revision"
        ),
    )

    assert section_response.status_code == 404
    assert task_response.status_code == 404


def test_assigned_section_member_can_poll_revisions(
    client: TestClient,
    db: Session,
) -> None:
    _, company, section, task = (
        _create_section_context(
            db,
            company_name="Shared Company",
        )
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

    _authenticate(
        client,
        db,
        user=member,
    )

    section_response = client.get(
        (
            "/api/live-updates/sections/"
            f"{section.id}/revision"
        ),
    )

    task_response = client.get(
        (
            "/api/live-updates/tasks/"
            f"{task.id}/revision"
        ),
    )

    assert section_response.status_code == 200
    assert task_response.status_code == 200


def test_access_revocation_stops_subsequent_polling(
    client: TestClient,
    db: Session,
) -> None:
    _, company, section, task = (
        _create_section_context(
            db,
            company_name="Revocation Company",
        )
    )

    member = create_user(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=member,
    )

    section_membership = create_section_membership(
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

    first_response = client.get(
        (
            "/api/live-updates/tasks/"
            f"{task.id}/revision"
        ),
    )

    assert first_response.status_code == 200

    db.delete(
        section_membership,
    )

    db.commit()

    second_response = client.get(
        (
            "/api/live-updates/tasks/"
            f"{task.id}/revision"
        ),
    )

    assert second_response.status_code == 404


def test_cross_company_ids_do_not_bypass_isolation(
    client: TestClient,
    db: Session,
) -> None:
    first_creator, _, _, _ = (
        _create_section_context(
            db,
            company_name="First Company",
        )
    )

    _, _, second_section, second_task = (
        _create_section_context(
            db,
            company_name="Second Company",
        )
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=first_creator,
    )

    section_response = client.get(
        (
            "/api/live-updates/sections/"
            f"{second_section.id}/revision"
        ),
    )

    task_response = client.get(
        (
            "/api/live-updates/tasks/"
            f"{second_task.id}/revision"
        ),
    )

    assert section_response.status_code == 404
    assert task_response.status_code == 404