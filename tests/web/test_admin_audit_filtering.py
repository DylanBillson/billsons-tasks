from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timezone import utc_now
from app.main import app
from app.web.routes.admin_audit import (
    router as admin_audit_router,
)
from tests.factories import (
    create_administrator,
    create_audit_log,
    create_auth_session,
    create_user,
)


def _route_is_registered(
    *,
    path: str,
    name: str,
) -> bool:
    return any(
        route.path == path
        and route.name == name
        for route in app.routes
    )


if not _route_is_registered(
    path="/admin/audit",
    name="admin_audit",
):
    app.include_router(
        admin_audit_router,
    )


def _authenticate(
    client: TestClient,
    db: Session,
    *,
    user,
) -> None:
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


def test_filter_audit_logs_by_search(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    matching = create_audit_log(
        db,
        action="task_updated",
        summary="Coffee stock was updated.",
    )

    hidden = create_audit_log(
        db,
        action="task_updated",
        summary="Cellar stock was updated.",
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        "/admin/audit?search=coffee",
    )

    assert response.status_code == 200
    assert matching.summary in response.text
    assert hidden.summary not in response.text


def test_filter_audit_logs_by_user(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    first_user = create_user(
        db,
        display_name="First Audit User",
    )

    second_user = create_user(
        db,
        display_name="Second Audit User",
    )

    matching = create_audit_log(
        db,
        action="login",
        summary="First user signed in.",
        user=first_user,
    )

    hidden = create_audit_log(
        db,
        action="login",
        summary="Second user signed in.",
        user=second_user,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        (
            "/admin/audit"
            f"?user_id={first_user.id}"
        ),
    )

    assert response.status_code == 200
    assert matching.summary in response.text
    assert hidden.summary not in response.text


def test_filter_audit_logs_by_action(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    matching = create_audit_log(
        db,
        action="company_created",
        summary="A company was created.",
    )

    hidden = create_audit_log(
        db,
        action="company_archived",
        summary="A company was archived.",
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        (
            "/admin/audit"
            "?action=company_created"
        ),
    )

    assert response.status_code == 200
    assert matching.summary in response.text
    assert hidden.summary not in response.text


def test_filter_audit_logs_by_entity(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    matching = create_audit_log(
        db,
        action="task_updated",
        summary="Matching task updated.",
        entity_type="task",
        entity_id=20,
    )

    hidden = create_audit_log(
        db,
        action="task_updated",
        summary="Other task updated.",
        entity_type="task",
        entity_id=21,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        (
            "/admin/audit"
            "?entity_type=task"
            "&entity_id=20"
        ),
    )

    assert response.status_code == 200
    assert matching.summary in response.text
    assert hidden.summary not in response.text


def test_filter_audit_logs_by_date(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    now = utc_now()

    matching = create_audit_log(
        db,
        action="recent_action",
        summary="Recent audit event.",
    )

    hidden = create_audit_log(
        db,
        action="old_action",
        summary="Old audit event.",
    )

    matching.created_at = now
    hidden.created_at = now - timedelta(
        days=30,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    created_from = (
        now.date()
        - timedelta(
            days=2,
        )
    ).isoformat()

    response = client.get(
        (
            "/admin/audit"
            f"?created_from={created_from}"
        ),
    )

    assert response.status_code == 200
    assert matching.summary in response.text
    assert hidden.summary not in response.text


def test_audit_log_pagination(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    now = utc_now()

    newest = create_audit_log(
        db,
        action="newest_action",
        summary="Newest audit event.",
    )

    older = create_audit_log(
        db,
        action="older_action",
        summary="Older audit event.",
    )

    newest.created_at = now
    older.created_at = now - timedelta(
        minutes=1,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    first_page = client.get(
        "/admin/audit?page=1&page_size=1",
    )

    second_page = client.get(
        "/admin/audit?page=2&page_size=1",
    )

    assert first_page.status_code == 200
    assert second_page.status_code == 200

    assert newest.summary in first_page.text
    assert older.summary not in first_page.text

    assert older.summary in second_page.text
    assert newest.summary not in second_page.text


def test_audit_pagination_preserves_filters(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    now = utc_now()

    for index in range(
        2,
    ):
        audit_log = create_audit_log(
            db,
            action="task_created",
            summary=f"Coffee event {index}",
        )

        audit_log.created_at = (
            now
            - timedelta(
                minutes=index,
            )
        )

    create_audit_log(
        db,
        action="task_deleted",
        summary="Hidden cellar event",
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=administrator,
    )

    response = client.get(
        (
            "/admin/audit"
            "?search=coffee"
            "&action=task_created"
            "&page=1"
            "&page_size=1"
        ),
    )

    assert response.status_code == 200

    assert (
        "search=coffee"
        in response.text
    )

    assert (
        "action=task_created"
        in response.text
    )

    assert (
        "page=2"
        in response.text
    )


def test_invalid_audit_filter_returns_422(
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
        "/admin/audit?entity_id=invalid",
    )

    assert response.status_code == 422

    assert (
        "Check the selected filters"
        in response.text
    )


def test_reversed_audit_date_range_returns_422(
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
        (
            "/admin/audit"
            "?created_from=2026-08-03"
            "&created_to=2026-08-01"
        ),
    )

    assert response.status_code == 422

    assert (
        "Check the selected filters"
        in response.text
    )