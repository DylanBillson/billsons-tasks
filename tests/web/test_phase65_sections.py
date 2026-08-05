from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import CompanyRole
from tests.factories import (
    create_auth_session,
    create_company,
    create_company_membership,
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



def _create_section_context(db: Session):
    user = create_user(db)
    company = create_company(db)
    create_company_membership(
        db,
        company=company,
        user=user,
        role=CompanyRole.MANAGER,
    )
    section = create_section(
        db,
        company=company,
        created_by=user,
    )
    section_list = create_section_list(
        db,
        section=section,
        name="Phase 6.5 List",
    )
    task = create_task(
        db,
        section_list=section_list,
        created_by=user,
        title="Phase 6.5 Section Task",
    )
    db.commit()
    return user, section, section_list, task


def test_phase65_section_board_layout(
    client: TestClient,
    db: Session,
) -> None:
    user, section, section_list, task = (
        _create_section_context(db)
    )
    _authenticate(client, db, user=user)

    response = client.get(
        f"/sections/{section.id}",
    )

    assert response.status_code == 200
    assert "task-filter-panel" in response.text
    assert "task-board" in response.text
    assert "task-list-column" in response.text
    assert "task-card" in response.text
    assert f'data-list-id="{section_list.id}"' in response.text
    assert f'data-task-id="{task.id}"' in response.text
    assert 'data-list-drag-enabled="true"' in response.text


def test_phase65_section_summary_follows_board(
    client: TestClient,
    db: Session,
) -> None:
    user, section, _, _ = _create_section_context(db)
    _authenticate(client, db, user=user)

    response = client.get(
        f"/sections/{section.id}",
    )

    board_position = response.text.index(
        "data-task-board",
    )
    summary_position = response.text.index(
        'id="section-summary-heading"',
    )

    assert board_position < summary_position
    assert 'id="section-members-heading"' not in response.text


def test_phase65_active_filters_disable_dragging(
    client: TestClient,
    db: Session,
) -> None:
    user, section, _, _ = _create_section_context(db)
    _authenticate(client, db, user=user)

    response = client.get(
        f"/sections/{section.id}?state=open",
    )

    assert response.status_code == 200
    assert 'data-drag-enabled="false"' in response.text
    assert 'data-list-drag-enabled="false"' in response.text
    assert "Filters are currently applied." in response.text
