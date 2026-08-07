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


def _create_company_context(
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


def test_phase7_live_update_endpoints_require_authentication(
    client: TestClient,
    db: Session,
) -> None:
    _, _, section, task = (
        _create_company_context(
            db,
            company_name="Authentication Company",
        )
    )

    db.commit()

    section_response = client.get(
        (
            "/api/live-updates/sections/"
            f"{section.id}/revision"
        ),
        headers={
            "accept": "application/json",
        },
        follow_redirects=False,
    )

    task_response = client.get(
        (
            "/api/live-updates/tasks/"
            f"{task.id}/revision"
        ),
        headers={
            "accept": "application/json",
        },
        follow_redirects=False,
    )

    assert section_response.status_code == 401
    assert task_response.status_code == 401


def test_phase7_cross_company_polling_is_hidden(
    client: TestClient,
    db: Session,
) -> None:
    first_creator, _, _, _ = (
        _create_company_context(
            db,
            company_name="First Isolation Company",
        )
    )

    _, _, second_section, second_task = (
        _create_company_context(
            db,
            company_name="Second Isolation Company",
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

    assert section_response.status_code != 403
    assert task_response.status_code != 403


def test_phase7_company_membership_alone_does_not_grant_polling(
    client: TestClient,
    db: Session,
) -> None:
    _, company, section, task = (
        _create_company_context(
            db,
            company_name="Section Isolation Company",
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


def test_phase7_explicit_section_member_can_poll(
    client: TestClient,
    db: Session,
) -> None:
    _, company, section, task = (
        _create_company_context(
            db,
            company_name="Shared Isolation Company",
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


def test_phase7_revoked_section_access_stops_polling(
    client: TestClient,
    db: Session,
) -> None:
    _, company, section, task = (
        _create_company_context(
            db,
            company_name="Revoked Access Company",
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

    membership = create_section_membership(
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

    before = client.get(
        (
            "/api/live-updates/tasks/"
            f"{task.id}/revision"
        ),
    )

    assert before.status_code == 200

    db.delete(
        membership,
    )

    db.commit()

    after_task = client.get(
        (
            "/api/live-updates/tasks/"
            f"{task.id}/revision"
        ),
    )

    after_section = client.get(
        (
            "/api/live-updates/sections/"
            f"{section.id}/revision"
        ),
    )

    assert after_task.status_code == 404
    assert after_section.status_code == 404


def test_phase7_unknown_and_inaccessible_resources_are_indistinguishable(
    client: TestClient,
    db: Session,
) -> None:
    first_creator, _, _, _ = (
        _create_company_context(
            db,
            company_name="Visible Company",
        )
    )

    _, _, hidden_section, hidden_task = (
        _create_company_context(
            db,
            company_name="Hidden Company",
        )
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=first_creator,
    )

    hidden_section_response = client.get(
        (
            "/api/live-updates/sections/"
            f"{hidden_section.id}/revision"
        ),
    )

    missing_section_response = client.get(
        "/api/live-updates/sections/999999999/revision",
    )

    hidden_task_response = client.get(
        (
            "/api/live-updates/tasks/"
            f"{hidden_task.id}/revision"
        ),
    )

    missing_task_response = client.get(
        "/api/live-updates/tasks/999999999/revision",
    )

    assert hidden_section_response.status_code == 404
    assert missing_section_response.status_code == 404

    assert hidden_task_response.status_code == 404
    assert missing_task_response.status_code == 404

    assert (
        hidden_section_response.json()
        == missing_section_response.json()
    )

    assert (
        hidden_task_response.json()
        == missing_task_response.json()
    )