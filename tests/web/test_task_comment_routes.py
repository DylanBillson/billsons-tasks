from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import CompanyRole
from app.models.task_comment import TaskComment
from tests.factories import (
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
        title="Commented Task",
    )

    member = create_user(
        db,
        display_name="Comment Author",
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

    return creator, member, task


def test_section_member_adds_comment(
    client: TestClient,
    db: Session,
) -> None:
    _, member, task = _create_context(db)

    csrf_token = _authenticate(
        client,
        db,
        user=member,
    )

    response = client.post(
        f"/tasks/{task.id}/comments",
        data={
            "csrf_token": csrf_token,
            "body": "The task is nearly complete.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    comment = db.scalar(
        select(TaskComment).where(
            TaskComment.task_id == task.id,
            TaskComment.user_id == member.id,
        )
    )

    assert comment is not None
    assert comment.body == (
        "The task is nearly complete."
    )


def test_comment_route_rejects_blank_comment(
    client: TestClient,
    db: Session,
) -> None:
    _, member, task = _create_context(db)

    csrf_token = _authenticate(
        client,
        db,
        user=member,
    )

    response = client.post(
        f"/tasks/{task.id}/comments",
        data={
            "csrf_token": csrf_token,
            "body": "   ",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    comments = list(
        db.scalars(
            select(TaskComment).where(
                TaskComment.task_id == task.id,
            )
        ).all()
    )

    assert comments == []


def test_comment_author_deletes_own_comment(
    client: TestClient,
    db: Session,
) -> None:
    _, member, task = _create_context(db)

    comment = create_task_comment(
        db,
        task=task,
        user=member,
        body="Delete this comment.",
    )
    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=member,
    )

    response = client.post(
        (
            f"/tasks/{task.id}/comments/"
            f"{comment.id}/delete"
        ),
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    db.refresh(comment)

    assert comment.is_deleted is True
    assert comment.deleted_by_user_id == member.id


def test_member_cannot_delete_another_users_comment(
    client: TestClient,
    db: Session,
) -> None:
    creator, member, task = _create_context(db)

    comment = create_task_comment(
        db,
        task=task,
        user=creator,
    )
    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=member,
    )

    response = client.post(
        (
            f"/tasks/{task.id}/comments/"
            f"{comment.id}/delete"
        ),
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    db.refresh(comment)
    assert comment.is_deleted is False


def test_comment_id_must_belong_to_task_url(
    client: TestClient,
    db: Session,
) -> None:
    creator, member, task = _create_context(db)

    other_task = create_task(
        db,
        section_list=task.section_list,
        created_by=creator,
        title="Other Task",
    )

    comment = create_task_comment(
        db,
        task=other_task,
        user=creator,
    )
    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=member,
    )

    response = client.post(
        (
            f"/tasks/{task.id}/comments/"
            f"{comment.id}/delete"
        ),
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    db.refresh(comment)
    assert comment.is_deleted is False


def test_comment_mutation_requires_csrf(
    client: TestClient,
    db: Session,
) -> None:
    _, member, task = _create_context(db)

    _authenticate(
        client,
        db,
        user=member,
    )

    response = client.post(
        f"/tasks/{task.id}/comments",
        data={
            "body": "Missing CSRF token.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 403


def test_task_detail_renders_comment_as_compact_bubble(
    client: TestClient,
    db: Session,
) -> None:
    from datetime import UTC, datetime
    _, member, task = _create_context(db)
    comment = create_task_comment(
        db,
        task=task,
        user=member,
        body="Rendered inside a compact comment bubble.",
    )
    comment.created_at = datetime(2026, 8, 3, 18, 55, tzinfo=UTC)
    db.add(comment)
    db.commit()
    _authenticate(client, db, user=member)
    response = client.get(f"/tasks/{task.id}")
    assert response.status_code == 200
    assert "task-comment-content" in response.text
    assert "task-comment-message" in response.text
    assert "task-comment-meta" in response.text
    assert f"{member.display_name}:" in response.text
    assert "Rendered inside a compact comment bubble." in response.text
    assert "19:55 03/08/26" in response.text
    assert "task-comment-delete" in response.text
