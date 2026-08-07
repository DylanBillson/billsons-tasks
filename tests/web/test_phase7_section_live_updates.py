from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.live_update_service import (
    LiveUpdateService,
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


def _create_context(
    db: Session,
):
    creator = create_user(db)

    company = create_company(db)

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

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
    )

    db.commit()

    return (
        creator,
        section,
    )


def test_phase7_section_revision_endpoint_matches_service(
    client: TestClient,
    db: Session,
) -> None:
    creator, section = _create_context(db)

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.get(
        f"/api/live-updates/sections/{section.id}/revision",
    )

    assert response.status_code == 200

    payload = response.json()

    service_revision = (
        LiveUpdateService.get_section_revision(
            db,
            actor=creator,
            section_id=section.id,
        )
    )

    assert payload["revision"] == service_revision.revision
    assert payload["scope"] == "section"
    assert payload["changed"] is False

def test_phase7_section_reports_changed_revision(
    client: TestClient,
    db: Session,
) -> None:
    from datetime import timedelta

    from app.core.timezone import utc_now

    creator, section = _create_context(db)

    revision = (
        LiveUpdateService.get_section_revision(
            db,
            actor=creator,
            section_id=section.id,
        )
    )

    section.name = "Updated section"

    section.updated_at = (
        utc_now()
        + timedelta(
            seconds=1,
        )
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=creator,
    )

    response = client.get(
        f"/api/live-updates/sections/{section.id}/revision",
        params={
            "known_revision": revision.revision,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["changed"] is True
    assert payload["revision"] != revision.revision


def test_phase7_section_revision_is_stable_when_unchanged(
    client: TestClient,
    db: Session,
) -> None:
    creator, section = _create_context(db)

    first = LiveUpdateService.get_section_revision(
        db,
        actor=creator,
        section_id=section.id,
    )

    second = LiveUpdateService.get_section_revision(
        db,
        actor=creator,
        section_id=section.id,
    )

    assert first.revision == second.revision