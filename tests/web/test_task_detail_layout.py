from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import CompanyRole
from app.services.task_history_service import TaskHistoryService
from tests.factories import (
    create_auth_session,
    create_company,
    create_company_membership,
    create_section,
    create_section_list,
    create_task,
    create_task_comment,
    create_user,
)


def _authenticate(client: TestClient, db: Session, *, user) -> str:
    _, session_token, csrf_token = create_auth_session(db, user=user)
    db.commit()
    client.cookies.set(settings.session_cookie_name, session_token)
    client.cookies.set(
        f"{settings.session_cookie_name}_csrf",
        csrf_token,
    )
    return csrf_token


def _create_context(db: Session):
    creator = create_user(db, display_name="Task Layout Creator")
    company = create_company(db, name="Task Layout Company")
    create_company_membership(
        db, company=company, user=creator, role=CompanyRole.MANAGER
    )
    section = create_section(
        db, company=company, created_by=creator, name="Task Layout Section"
    )
    section_list = create_section_list(
        db, section=section, name="Task Layout List"
    )
    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Task Detail Layout",
        description="Prominent task description.",
    )
    return creator, task


def test_comments_appear_before_detail_history_columns(
    client: TestClient, db: Session
) -> None:
    creator, task = _create_context(db)
    create_task_comment(db, task=task, user=creator, body="Layout comment")
    TaskHistoryService.record_created(
        db, task=task, actor=creator, commit=False
    )
    db.commit()
    _authenticate(client, db, user=creator)
    response = client.get(f"/tasks/{task.id}")
    assert response.status_code == 200
    comments = response.text.index('id="task-comments-heading"')
    columns = response.text.index('class="task-detail-columns"')
    details = response.text.index('id="task-details-heading"')
    history = response.text.index('id="task-history-heading"')
    assert comments < columns < details
    assert columns < history


def test_task_details_and_history_share_column_container(
    client: TestClient, db: Session
) -> None:
    creator, task = _create_context(db)
    TaskHistoryService.record_created(
        db, task=task, actor=creator, commit=False
    )
    db.commit()
    _authenticate(client, db, user=creator)
    response = client.get(f"/tasks/{task.id}")
    assert response.status_code == 200
    start = response.text.index('class="task-detail-columns"')
    end = response.text.index('class="task-detail-secondary-grid"', start)
    html = response.text[start:end]
    assert 'id="task-details-heading"' in html
    assert 'id="task-history-heading"' in html
    assert "task-information-card" in html
    assert "task-history-card" in html


def test_description_is_rendered_before_comments(
    client: TestClient, db: Session
) -> None:
    creator, task = _create_context(db)
    db.commit()
    _authenticate(client, db, user=creator)
    response = client.get(f"/tasks/{task.id}")
    assert response.status_code == 200
    description = response.text.index('id="task-description-heading"')
    comments = response.text.index('id="task-comments-heading"')
    assert description < comments
    assert "task-description-card" in response.text
    assert "task-description-content" in response.text


def test_legacy_sidebar_layout_is_not_rendered(
    client: TestClient, db: Session
) -> None:
    creator, task = _create_context(db)
    db.commit()
    _authenticate(client, db, user=creator)
    response = client.get(f"/tasks/{task.id}")
    assert response.status_code == 200
    assert "task-detail-layout" not in response.text
    assert "task-detail-sidebar" not in response.text
    assert "task-detail-main" not in response.text
