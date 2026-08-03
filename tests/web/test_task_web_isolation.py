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


def _create_isolated_context(
    db: Session,
):
    first_company = create_company(
        db,
        name="First Company",
    )

    second_company = create_company(
        db,
        name="Second Company",
    )

    first_creator = create_user(db)
    second_creator = create_user(db)

    create_company_membership(
        db,
        company=first_company,
        user=first_creator,
        role=CompanyRole.MANAGER,
    )

    create_company_membership(
        db,
        company=second_company,
        user=second_creator,
        role=CompanyRole.MANAGER,
    )

    first_section = create_section(
        db,
        company=first_company,
        created_by=first_creator,
        name="First Section",
    )

    second_section = create_section(
        db,
        company=second_company,
        created_by=second_creator,
        name="Second Section",
    )

    first_list = create_section_list(
        db,
        section=first_section,
    )

    second_list = create_section_list(
        db,
        section=second_section,
    )

    first_task = create_task(
        db,
        section_list=first_list,
        created_by=first_creator,
        title="First Task",
    )

    second_task = create_task(
        db,
        section_list=second_list,
        created_by=second_creator,
        title="Second Task",
    )

    db.commit()

    return {
        "first_creator": first_creator,
        "second_creator": second_creator,
        "first_section": first_section,
        "second_section": second_section,
        "first_list": first_list,
        "second_list": second_list,
        "first_task": first_task,
        "second_task": second_task,
    }


def test_user_cannot_open_task_from_other_company(
    client: TestClient,
    db: Session,
) -> None:
    context = _create_isolated_context(db)

    _authenticate(
        client,
        db,
        user=context["first_creator"],
    )

    response = client.get(
        f"/tasks/{context['second_task'].id}",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "Second Task" not in response.text


def test_user_cannot_edit_task_from_other_company(
    client: TestClient,
    db: Session,
) -> None:
    context = _create_isolated_context(db)

    _authenticate(
        client,
        db,
        user=context["first_creator"],
    )

    response = client.get(
        f"/tasks/{context['second_task'].id}/edit",
        follow_redirects=False,
    )

    assert response.status_code == 303


def test_user_cannot_update_task_from_other_company(
    client: TestClient,
    db: Session,
) -> None:
    context = _create_isolated_context(db)

    csrf_token = _authenticate(
        client,
        db,
        user=context["first_creator"],
    )

    original_title = context["second_task"].title

    response = client.post(
        f"/tasks/{context['second_task'].id}/edit",
        data={
            "csrf_token": csrf_token,
            "title": "Hijacked Task",
            "description": "",
            "due_at": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    db.refresh(context["second_task"])
    assert context["second_task"].title == original_title


def test_user_cannot_complete_task_from_other_company(
    client: TestClient,
    db: Session,
) -> None:
    context = _create_isolated_context(db)

    csrf_token = _authenticate(
        client,
        db,
        user=context["first_creator"],
    )

    response = client.post(
        f"/tasks/{context['second_task'].id}/complete",
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    db.refresh(context["second_task"])
    assert context["second_task"].completed_at is None


def test_user_cannot_delete_task_from_other_company(
    client: TestClient,
    db: Session,
) -> None:
    context = _create_isolated_context(db)

    csrf_token = _authenticate(
        client,
        db,
        user=context["first_creator"],
    )

    response = client.post(
        f"/tasks/{context['second_task'].id}/delete",
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    db.refresh(context["second_task"])
    assert context["second_task"].deleted_at is None


def test_user_cannot_comment_on_task_from_other_company(
    client: TestClient,
    db: Session,
) -> None:
    context = _create_isolated_context(db)

    csrf_token = _authenticate(
        client,
        db,
        user=context["first_creator"],
    )

    response = client.post(
        f"/tasks/{context['second_task'].id}/comments",
        data={
            "csrf_token": csrf_token,
            "body": "Cross-company comment.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert context["second_task"].comments == []


def test_user_cannot_delete_comment_from_other_company(
    client: TestClient,
    db: Session,
) -> None:
    context = _create_isolated_context(db)

    comment = create_task_comment(
        db,
        task=context["second_task"],
        user=context["second_creator"],
    )
    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=context["first_creator"],
    )

    response = client.post(
        (
            f"/tasks/{context['second_task'].id}"
            f"/comments/{comment.id}/delete"
        ),
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    db.refresh(comment)
    assert comment.is_deleted is False


def test_user_cannot_move_task_into_other_company(
    client: TestClient,
    db: Session,
) -> None:
    context = _create_isolated_context(db)

    csrf_token = _authenticate(
        client,
        db,
        user=context["first_creator"],
    )

    original_list_id = (
        context["first_task"].section_list_id
    )

    response = client.post(
        f"/tasks/{context['first_task'].id}/move",
        json={
            "destination_list_id": context["second_list"].id,
            "sort_position": 1000,
        },
        headers={
            "x-csrf-token": csrf_token,
        },
    )

    assert response.status_code == 403

    db.refresh(context["first_task"])

    assert (
        context["first_task"].section_list_id
        == original_list_id
    )


def test_user_cannot_reorder_foreign_task_into_local_section(
    client: TestClient,
    db: Session,
) -> None:
    context = _create_isolated_context(db)

    csrf_token = _authenticate(
        client,
        db,
        user=context["first_creator"],
    )

    response = client.post(
        (
            f"/sections/{context['first_section'].id}"
            "/tasks/reorder"
        ),
        json={
            "items": [
                {
                    "task_id": context["second_task"].id,
                    "section_list_id": context["first_list"].id,
                    "sort_position": 1000,
                },
            ],
        },
        headers={
            "x-csrf-token": csrf_token,
        },
    )

    assert response.status_code == 422

    db.refresh(context["second_task"])

    assert (
        context["second_task"].section_list_id
        == context["second_list"].id
    )