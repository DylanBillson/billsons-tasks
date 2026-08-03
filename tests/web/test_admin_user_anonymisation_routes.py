from urllib.parse import (
    parse_qs,
    urlparse,
)

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import AuditAction
from app.models.audit_log import AuditLog
from tests.factories import (
    create_administrator,
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


def _create_inactive_target(
    db: Session,
):
    user = create_user(
        db,
        username="anonymisation-target",
        display_name="Anonymisation Target",
        is_active=False,
    )

    creator = create_user(
        db,
    )

    company = create_company(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=user,
    )

    section = create_section(
        db,
        company=company,
        created_by=creator,
    )

    create_section_membership(
        db,
        section=section,
        user=user,
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

    create_task_assignee(
        db,
        task=task,
        user=user,
    )

    return user


def test_anonymisation_page_requires_authentication(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
        is_active=False,
    )

    db.commit()

    response = client.get(
        f"/admin/users/{user.id}/anonymise",
        headers={
            "accept": "text/html",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303


def test_anonymisation_page_requires_administrator(
    client: TestClient,
    db: Session,
) -> None:
    actor = create_user(
        db,
    )

    target = create_user(
        db,
        is_active=False,
    )

    _authenticate(
        client,
        db,
        user=actor,
    )

    response = client.get(
        f"/admin/users/{target.id}/anonymise",
        follow_redirects=False,
    )

    assert response.status_code == 403


def test_administrator_views_anonymisation_page(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target = _create_inactive_target(
        db,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        f"/admin/users/{target.id}/anonymise",
    )

    assert response.status_code == 200
    assert "Anonymise User" in response.text
    assert target.display_name in response.text
    assert target.username in response.text
    assert "ANONYMISE USER" in response.text
    assert csrf_token in response.text


def test_active_user_cannot_open_anonymisation_page(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target = create_user(
        db,
        is_active=True,
    )

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        f"/admin/users/{target.id}/anonymise",
        follow_redirects=False,
    )

    assert response.status_code == 303

    parsed = urlparse(
        response.headers["location"],
    )

    query = parse_qs(
        parsed.query,
    )

    assert "deactivated" in query["error"][0]


def test_submit_requires_exact_confirmation(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target = _create_inactive_target(
        db,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        f"/admin/users/{target.id}/anonymise",
        data={
            "csrf_token": csrf_token,
            "confirmation_phrase": "anonymise user",
            "confirm_irreversible": "1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert "Check the confirmation" in response.text

    db.refresh(
        target,
    )

    assert target.is_anonymised is False


def test_submit_requires_irreversible_confirmation(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target = _create_inactive_target(
        db,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        f"/admin/users/{target.id}/anonymise",
        data={
            "csrf_token": csrf_token,
            "confirmation_phrase": "ANONYMISE USER",
        },
        follow_redirects=False,
    )

    assert response.status_code == 422

    db.refresh(
        target,
    )

    assert target.is_anonymised is False


def test_administrator_anonymises_user(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target = _create_inactive_target(
        db,
    )

    target_id = target.id
    original_username = target.username
    original_display_name = target.display_name

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        f"/admin/users/{target.id}/anonymise",
        data={
            "csrf_token": csrf_token,
            "confirmation_phrase": "ANONYMISE USER",
            "confirm_irreversible": "1",
        },
        follow_redirects=False,
    )

    db.refresh(
        target,
    )

    assert response.status_code == 303
    assert target.is_anonymised is True
    assert target.is_active is False

    assert target.username == (
        f"anonymised-user-{target_id:04d}"
    )

    assert target.display_name == (
        f"Anonymised User {target_id:04d}"
    )

    assert original_username != target.username
    assert original_display_name != target.display_name


def test_anonymisation_records_audit_event(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target = _create_inactive_target(
        db,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        f"/admin/users/{target.id}/anonymise",
        data={
            "csrf_token": csrf_token,
            "confirmation_phrase": "ANONYMISE USER",
            "confirm_irreversible": "1",
        },
        follow_redirects=False,
    )

    audit_log = db.scalar(
        select(
            AuditLog,
        ).where(
            AuditLog.action
            == AuditAction.USER_ANONYMISED.value,
            AuditLog.entity_type
            == "user",
            AuditLog.entity_id
            == target.id,
        ),
    )

    assert response.status_code == 303
    assert audit_log is not None
    assert audit_log.user_id == administrator.id


def test_anonymisation_requires_csrf(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target = _create_inactive_target(
        db,
    )

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.post(
        f"/admin/users/{target.id}/anonymise",
        data={
            "confirmation_phrase": "ANONYMISE USER",
            "confirm_irreversible": "1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 403

    db.refresh(
        target,
    )

    assert target.is_anonymised is False


def test_user_list_links_inactive_user_to_anonymisation(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    target = create_user(
        db,
        is_active=False,
    )

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/admin/users",
    )

    assert response.status_code == 200

    assert (
        f"/admin/users/{target.id}/anonymise"
        in response.text
    )