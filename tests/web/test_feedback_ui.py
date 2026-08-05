from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from tests.factories import (
    create_auth_session,
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


def test_authenticated_page_renders_feedback_trigger(
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

    response = client.get(
        "/",
    )

    assert response.status_code == 200

    assert "data-feedback-open" in response.text
    assert 'aria-controls="feedback-modal"' in response.text
    assert 'aria-haspopup="dialog"' in response.text


def test_authenticated_page_renders_feedback_dialog(
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

    response = client.get(
        "/",
    )

    assert response.status_code == 200

    assert "<dialog" in response.text
    assert 'id="feedback-modal"' in response.text
    assert "data-feedback-modal" in response.text

    assert (
        'aria-labelledby="feedback-modal-title"'
        in response.text
    )

    assert (
        'aria-describedby="feedback-modal-description"'
        in response.text
    )


def test_feedback_dialog_contains_required_explanation(
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

    response = client.get(
        "/",
    )

    assert response.status_code == 200

    assert (
        "Send a quick note about an issue, bug, suggestion,"
        in response.text
    )

    assert (
        "or anything that needs attention."
        in response.text
    )


def test_feedback_form_posts_to_feedback_route(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    csrf_token = _authenticate(
        client,
        db,
        user=user,
    )

    response = client.get(
        "/",
    )

    assert response.status_code == 200

    assert (
        'action="http://testserver/feedback"'
        in response.text
    )

    assert 'method="post"' in response.text

    assert (
        f'value="{csrf_token}"'
        in response.text
    )


def test_feedback_form_contains_message_and_page_fields(
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

    response = client.get(
        "/",
    )

    assert response.status_code == 200

    assert 'name="message"' in response.text
    assert 'maxlength="5000"' in response.text
    assert "required" in response.text

    assert 'name="page_url"' in response.text
    assert "data-feedback-page-url" in response.text
    assert "data-feedback-character-count" in response.text


def test_feedback_form_contains_close_and_submit_controls(
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

    response = client.get(
        "/",
    )

    assert response.status_code == 200

    assert response.text.count(
        "data-feedback-close",
    ) >= 2

    assert 'data-loading-text="Sending…"' in response.text
    assert ">Send<" in response.text.replace(
        "\n",
        "",
    ).replace(
        " ",
        "",
    )


def test_feedback_javascript_is_loaded(
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

    response = client.get(
        "/",
    )

    assert response.status_code == 200

    assert (
        'src="http://testserver/static/js/feedback.js"'
        in response.text
    )


def test_unauthenticated_page_does_not_render_feedback_ui(
    client: TestClient,
) -> None:
    response = client.get(
        "/login",
    )

    assert response.status_code == 200
    assert "data-feedback-open" not in response.text
    assert "data-feedback-modal" not in response.text
    assert "data-feedback-form" not in response.text