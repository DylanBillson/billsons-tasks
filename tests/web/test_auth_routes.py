import re
from collections.abc import Generator
from http.cookies import SimpleCookie
from unittest.mock import patch
from urllib.parse import parse_qs, quote, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import AuditAction
from app.core.security import hash_token
from app.core.timezone import utc_now
from app.db.session import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.session import AuthSession
from app.web.routes.auth import (
    AUTH_CSRF_COOKIE_NAME,
    LOGIN_CSRF_COOKIE_MAX_AGE_SECONDS,
    LOGIN_CSRF_COOKIE_NAME,
    _build_login_flash_messages,
    _get_form_value,
    _get_safe_redirect_target,
    _get_session_cookie_max_age,
    _validate_login_csrf_token,
)
from app.web.forms.auth import LoginForm
from tests.factories import (
    DEFAULT_TEST_PASSWORD,
    create_auth_session,
    create_expired_auth_session,
    create_revoked_auth_session,
    create_user,
)


@pytest.fixture
def client(
    db: Session,
) -> Generator[TestClient, None, None]:
    """
    Provide a TestClient using the isolated test database session.

    HTTPS is used so secure authentication cookies are accepted and returned
    by the test client's cookie jar when SESSION_COOKIE_SECURE is enabled.
    """

    def override_get_db() -> Generator[
        Session,
        None,
        None,
    ]:
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(
            app,
            base_url="https://testserver",
            follow_redirects=False,
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(
            get_db,
            None,
        )


def extract_hidden_input(
    html: str,
    *,
    name: str,
) -> str:
    pattern = (
        rf'<input\s+[^>]*name="{re.escape(name)}"'
        rf'[^>]*value="([^"]*)"'
    )

    match = re.search(
        pattern,
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if match is None:
        reverse_pattern = (
            rf'<input\s+[^>]*value="([^"]*)"'
            rf'[^>]*name="{re.escape(name)}"'
        )

        match = re.search(
            reverse_pattern,
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )

    if match is None:
        raise AssertionError(
            f"Hidden input {name!r} was not found.",
        )

    return match.group(1)


def get_set_cookie_headers(
    response: object,
) -> list[str]:
    headers = getattr(
        response,
        "headers",
    )

    get_list = getattr(
        headers,
        "get_list",
        None,
    )

    if get_list is not None:
        return list(
            get_list(
                "set-cookie",
            ),
        )

    raw_header = headers.get(
        "set-cookie",
        "",
    )

    if not raw_header:
        return []

    return [
        raw_header,
    ]


def find_set_cookie_header(
    response: object,
    *,
    cookie_name: str,
) -> str:
    prefix = f"{cookie_name}="

    for header in get_set_cookie_headers(
        response,
    ):
        if header.startswith(prefix):
            return header

    raise AssertionError(
        f"No Set-Cookie header was found for "
        f"{cookie_name!r}.",
    )


def parse_cookie_value(
    response: object,
    *,
    cookie_name: str,
) -> str:
    header = find_set_cookie_header(
        response,
        cookie_name=cookie_name,
    )

    cookie = SimpleCookie()
    cookie.load(
        header,
    )

    morsel = cookie.get(
        cookie_name,
    )

    if morsel is None:
        raise AssertionError(
            f"Unable to parse cookie {cookie_name!r}.",
        )

    return morsel.value


def begin_login(
    client: TestClient,
    *,
    next_url: str | None = None,
) -> tuple[str, str]:
    url = "/login"

    if next_url is not None:
        url = (
            f"/login?next_url="
            f"{quote(next_url, safe='')}"
        )

    response = client.get(
        url,
    )

    assert response.status_code == 200

    form_token = extract_hidden_input(
        response.text,
        name="csrf_token",
    )
    cookie_token = parse_cookie_value(
        response,
        cookie_name=LOGIN_CSRF_COOKIE_NAME,
    )

    return form_token, cookie_token


def login_cookie_header(
    token: str,
) -> dict[str, str]:
    return {
        "cookie": (
            f"{LOGIN_CSRF_COOKIE_NAME}={token}"
        ),
    }


def authenticated_cookie_header(
    session_token: str,
    *,
    csrf_cookie_token: str | None = None,
) -> dict[str, str]:
    cookie_parts = [
        (
            f"{settings.session_cookie_name}="
            f"{session_token}"
        ),
    ]

    if csrf_cookie_token is not None:
        cookie_parts.append(
            f"{AUTH_CSRF_COOKIE_NAME}="
            f"{csrf_cookie_token}",
        )

    return {
        "cookie": "; ".join(
            cookie_parts,
        ),
    }


def assert_login_redirect(
    response: object,
    *,
    expected_next_url: str,
) -> None:
    headers = getattr(
        response,
        "headers",
    )
    location = headers["location"]
    parsed = urlsplit(
        location,
    )
    query = parse_qs(
        parsed.query,
    )

    assert getattr(
        response,
        "status_code",
    ) == 303
    assert parsed.path == "/login"
    assert query == {
        "next_url": [
            expected_next_url,
        ],
    }


def test_login_page_renders_for_anonymous_user(
    client: TestClient,
) -> None:
    response = client.get(
        "/login",
    )

    assert response.status_code == 200
    assert "Sign in" in response.text
    assert 'name="username"' in response.text
    assert 'name="password"' in response.text
    assert 'name="remember_me"' in response.text
    assert 'name="csrf_token"' in response.text
    assert 'name="next_url"' in response.text


def test_login_page_sets_login_csrf_cookie(
    client: TestClient,
) -> None:
    response = client.get(
        "/login",
    )

    form_token = extract_hidden_input(
        response.text,
        name="csrf_token",
    )
    cookie_token = parse_cookie_value(
        response,
        cookie_name=LOGIN_CSRF_COOKIE_NAME,
    )
    cookie_header = find_set_cookie_header(
        response,
        cookie_name=LOGIN_CSRF_COOKIE_NAME,
    )

    assert response.status_code == 200
    assert form_token
    assert cookie_token == form_token
    assert (
        f"Max-Age="
        f"{LOGIN_CSRF_COOKIE_MAX_AGE_SECONDS}"
        in cookie_header
    )
    assert "Path=/login" in cookie_header
    assert "HttpOnly" in cookie_header


def test_login_page_uses_fresh_csrf_token_each_time(
    client: TestClient,
) -> None:
    first_response = client.get(
        "/login",
    )
    second_response = client.get(
        "/login",
    )

    first_token = extract_hidden_input(
        first_response.text,
        name="csrf_token",
    )
    second_token = extract_hidden_input(
        second_response.text,
        name="csrf_token",
    )

    assert first_token != second_token


def test_login_page_preserves_safe_next_url(
    client: TestClient,
) -> None:
    response = client.get(
        "/login",
        params={
            "next_url": "/admin/users?page=2",
        },
    )

    next_url = extract_hidden_input(
        response.text,
        name="next_url",
    )

    assert response.status_code == 200
    assert next_url == "/admin/users?page=2"


@pytest.mark.parametrize(
    "unsafe_next_url",
    [
        "https://example.com",
        "http://example.com/path",
        "//example.com/path",
        "example.com/path",
        "admin/users",
        "javascript:alert(1)",
    ],
)
def test_login_page_rejects_unsafe_next_url(
    client: TestClient,
    unsafe_next_url: str,
) -> None:
    response = client.get(
        "/login",
        params={
            "next_url": unsafe_next_url,
        },
    )

    next_url = extract_hidden_input(
        response.text,
        name="next_url",
    )

    assert response.status_code == 200
    assert next_url == "/companies"


def test_login_page_redirects_authenticated_user(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    _, session_token, _ = create_auth_session(
        db,
        user=user,
    )

    response = client.get(
        "/login",
        headers=authenticated_cookie_header(
            session_token,
        ),
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/companies"


def test_login_page_redirects_authenticated_user_to_safe_next_url(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    _, session_token, _ = create_auth_session(
        db,
        user=user,
    )

    response = client.get(
        "/login",
        params={
            "next_url": "/admin/users",
        },
        headers=authenticated_cookie_header(
            session_token,
        ),
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/admin/users"
    )


def test_login_page_rejects_unsafe_redirect_for_authenticated_user(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    _, session_token, _ = create_auth_session(
        db,
        user=user,
    )

    response = client.get(
        "/login",
        params={
            "next_url": "https://example.com",
        },
        headers=authenticated_cookie_header(
            session_token,
        ),
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/companies"


def test_login_page_treats_expired_session_as_anonymous(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    _, session_token, _ = (
        create_expired_auth_session(
            db,
            user=user,
        )
    )

    response = client.get(
        "/login",
        headers=authenticated_cookie_header(
            session_token,
        ),
    )

    assert response.status_code == 200
    assert "Sign in" in response.text


def test_login_page_treats_revoked_session_as_anonymous(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    _, session_token, _ = (
        create_revoked_auth_session(
            db,
            user=user,
        )
    )

    response = client.get(
        "/login",
        headers=authenticated_cookie_header(
            session_token,
        ),
    )

    assert response.status_code == 200
    assert "Sign in" in response.text


def test_login_submit_authenticates_valid_credentials(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
        username="route-login-user",
        password=DEFAULT_TEST_PASSWORD,
    )
    form_token, cookie_token = begin_login(
        client,
    )

    response = client.post(
        "/login",
        data={
            "username": user.username,
            "password": DEFAULT_TEST_PASSWORD,
            "csrf_token": form_token,
            "next_url": "/",
        },
        headers=login_cookie_header(
            cookie_token,
        ),
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"

    session_token = parse_cookie_value(
        response,
        cookie_name=settings.session_cookie_name,
    )
    csrf_token = parse_cookie_value(
        response,
        cookie_name=AUTH_CSRF_COOKIE_NAME,
    )

    auth_session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash
            == hash_token(session_token),
        )
    )

    assert session_token
    assert csrf_token
    assert auth_session is not None
    assert auth_session.user_id == user.id
    assert auth_session.csrf_token_hash == hash_token(
        csrf_token,
    )
    assert auth_session.is_revoked is False


def test_login_submit_defaults_to_companies(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
        username="default-next-user",
        password=DEFAULT_TEST_PASSWORD,
    )
    form_token, cookie_token = begin_login(
        client,
    )

    response = client.post(
        "/login",
        data={
            "username": user.username,
            "password": DEFAULT_TEST_PASSWORD,
            "csrf_token": form_token,
        },
        headers=login_cookie_header(
            cookie_token,
        ),
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/companies"


def test_login_submit_redirects_to_safe_next_url(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
        username="safe-next-user",
        password=DEFAULT_TEST_PASSWORD,
    )
    form_token, cookie_token = begin_login(
        client,
        next_url="/admin/users?page=3",
    )

    response = client.post(
        "/login",
        data={
            "username": user.username,
            "password": DEFAULT_TEST_PASSWORD,
            "csrf_token": form_token,
            "next_url": "/admin/users?page=3",
        },
        headers=login_cookie_header(
            cookie_token,
        ),
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/admin/users?page=3"
    )


@pytest.mark.parametrize(
    "unsafe_next_url",
    [
        "https://example.com",
        "//example.com/path",
        "relative/path",
    ],
)
def test_login_submit_rejects_unsafe_next_url(
    client: TestClient,
    db: Session,
    unsafe_next_url: str,
) -> None:
    user = create_user(
        db,
        password=DEFAULT_TEST_PASSWORD,
    )
    form_token, cookie_token = begin_login(
        client,
    )

    response = client.post(
        "/login",
        data={
            "username": user.username,
            "password": DEFAULT_TEST_PASSWORD,
            "csrf_token": form_token,
            "next_url": unsafe_next_url,
        },
        headers=login_cookie_header(
            cookie_token,
        ),
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/companies"


def test_login_submit_sets_standard_session_cookie_max_age(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
        password=DEFAULT_TEST_PASSWORD,
    )
    form_token, cookie_token = begin_login(
        client,
    )

    response = client.post(
        "/login",
        data={
            "username": user.username,
            "password": DEFAULT_TEST_PASSWORD,
            "csrf_token": form_token,
        },
        headers=login_cookie_header(
            cookie_token,
        ),
    )

    session_cookie_header = find_set_cookie_header(
        response,
        cookie_name=settings.session_cookie_name,
    )
    csrf_cookie_header = find_set_cookie_header(
        response,
        cookie_name=AUTH_CSRF_COOKIE_NAME,
    )
    expected_max_age = (
        settings.session_duration_hours
        * 60
        * 60
    )

    assert response.status_code == 303
    assert (
        f"Max-Age={expected_max_age}"
        in session_cookie_header
    )
    assert (
        f"Max-Age={expected_max_age}"
        in csrf_cookie_header
    )
    assert "Path=/" in session_cookie_header
    assert "Path=/" in csrf_cookie_header
    assert "HttpOnly" in csrf_cookie_header


def test_login_submit_sets_remember_me_cookie_max_age(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
        password=DEFAULT_TEST_PASSWORD,
    )
    form_token, cookie_token = begin_login(
        client,
    )

    response = client.post(
        "/login",
        data={
            "username": user.username,
            "password": DEFAULT_TEST_PASSWORD,
            "remember_me": "true",
            "csrf_token": form_token,
        },
        headers=login_cookie_header(
            cookie_token,
        ),
    )

    session_cookie_header = find_set_cookie_header(
        response,
        cookie_name=settings.session_cookie_name,
    )
    expected_max_age = (
        settings.remember_me_duration_days
        * 24
        * 60
        * 60
    )

    session_token = parse_cookie_value(
        response,
        cookie_name=settings.session_cookie_name,
    )
    auth_session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash
            == hash_token(session_token),
        )
    )

    assert response.status_code == 303
    assert (
        f"Max-Age={expected_max_age}"
        in session_cookie_header
    )
    assert auth_session is not None
    assert auth_session.remember_me is True


def test_login_submit_deletes_temporary_login_csrf_cookie(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
        password=DEFAULT_TEST_PASSWORD,
    )
    form_token, cookie_token = begin_login(
        client,
    )

    response = client.post(
        "/login",
        data={
            "username": user.username,
            "password": DEFAULT_TEST_PASSWORD,
            "csrf_token": form_token,
        },
        headers=login_cookie_header(
            cookie_token,
        ),
    )

    login_cookie_header_value = (
        find_set_cookie_header(
            response,
            cookie_name=LOGIN_CSRF_COOKIE_NAME,
        )
    )

    assert response.status_code == 303
    assert "Max-Age=0" in login_cookie_header_value
    assert "Path=/login" in login_cookie_header_value


def test_login_submit_records_client_details(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
        password=DEFAULT_TEST_PASSWORD,
    )
    form_token, cookie_token = begin_login(
        client,
    )

    response = client.post(
        "/login",
        data={
            "username": user.username,
            "password": DEFAULT_TEST_PASSWORD,
            "csrf_token": form_token,
        },
        headers={
            **login_cookie_header(
                cookie_token,
            ),
            "user-agent": "Route authentication test",
        },
    )

    session_token = parse_cookie_value(
        response,
        cookie_name=settings.session_cookie_name,
    )
    auth_session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash
            == hash_token(session_token),
        )
    )

    assert response.status_code == 303
    assert auth_session is not None
    assert auth_session.ip_address == "testclient"
    assert auth_session.user_agent == (
        "Route authentication test"
    )


def test_login_submit_records_login_audit_event(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
        username="route-audit-user",
        password=DEFAULT_TEST_PASSWORD,
    )
    form_token, cookie_token = begin_login(
        client,
    )

    response = client.post(
        "/login",
        data={
            "username": user.username,
            "password": DEFAULT_TEST_PASSWORD,
            "csrf_token": form_token,
        },
        headers=login_cookie_header(
            cookie_token,
        ),
    )

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action == AuditAction.LOGIN.value,
            AuditLog.user_id == user.id,
        )
    )

    assert response.status_code == 303
    assert audit_log is not None
    assert audit_log.metadata_json["username"] == (
        "route-audit-user"
    )


def test_login_submit_rejects_missing_login_csrf_token(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
        username="missing-login-csrf-user",
        password=DEFAULT_TEST_PASSWORD,
    )
    _, cookie_token = begin_login(
        client,
    )

    response = client.post(
        "/login",
        data={
            "username": user.username,
            "password": DEFAULT_TEST_PASSWORD,
        },
        headers=login_cookie_header(
            cookie_token,
        ),
    )

    assert response.status_code == 403
    assert (
        "The security token is missing or invalid."
        in response.text
    )

    auth_session = db.scalar(
        select(AuthSession).where(
            AuthSession.user_id == user.id,
        )
    )

    assert auth_session is None


def test_login_submit_rejects_missing_login_csrf_cookie(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
        username="missing-login-cookie-user",
        password=DEFAULT_TEST_PASSWORD,
    )
    form_token, _ = begin_login(
        client,
    )

    client.cookies.clear()

    response = client.post(
        "/login",
        data={
            "username": user.username,
            "password": DEFAULT_TEST_PASSWORD,
            "csrf_token": form_token,
        },
    )

    assert response.status_code == 403
    assert (
        "The security token is missing or invalid."
        in response.text
    )


def test_login_submit_rejects_mismatched_login_csrf_token(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
        username="mismatched-login-csrf-user",
        password=DEFAULT_TEST_PASSWORD,
    )
    _, cookie_token = begin_login(
        client,
    )

    response = client.post(
        "/login",
        data={
            "username": user.username,
            "password": DEFAULT_TEST_PASSWORD,
            "csrf_token": "different-token",
        },
        headers=login_cookie_header(
            cookie_token,
        ),
    )

    assert response.status_code == 403
    assert (
        "The security token is missing or invalid."
        in response.text
    )


def test_failed_login_csrf_validation_sets_fresh_token(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
        password=DEFAULT_TEST_PASSWORD,
    )

    with patch(
        "app.web.routes.auth.generate_csrf_token",
        side_effect=[
            "initial-login-token",
            "replacement-login-token",
        ],
    ):
        first_response = client.get(
            "/login",
        )

        response = client.post(
            "/login",
            data={
                "username": user.username,
                "password": DEFAULT_TEST_PASSWORD,
                "csrf_token": "wrong-token",
            },
            headers=login_cookie_header(
                "initial-login-token",
            ),
        )

    replacement_form_token = extract_hidden_input(
        response.text,
        name="csrf_token",
    )
    replacement_cookie_token = parse_cookie_value(
        response,
        cookie_name=LOGIN_CSRF_COOKIE_NAME,
    )

    assert first_response.status_code == 200
    assert response.status_code == 403
    assert replacement_form_token == (
        "replacement-login-token"
    )
    assert replacement_cookie_token == (
        "replacement-login-token"
    )


def test_login_submit_returns_422_for_invalid_form(
    client: TestClient,
) -> None:
    form_token, cookie_token = begin_login(
        client,
    )

    response = client.post(
        "/login",
        data={
            "username": "",
            "password": "",
            "csrf_token": form_token,
        },
        headers=login_cookie_header(
            cookie_token,
        ),
    )

    assert response.status_code == 422
    assert "Sign in" in response.text
    assert 'class="is-invalid"' in response.text
    assert 'name="password"' in response.text


def test_invalid_form_preserves_username(
    client: TestClient,
) -> None:
    form_token, cookie_token = begin_login(
        client,
    )

    response = client.post(
        "/login",
        data={
            "username": "  preserved-user  ",
            "password": "",
            "csrf_token": form_token,
        },
        headers=login_cookie_header(
            cookie_token,
        ),
    )

    assert response.status_code == 422
    assert 'value="preserved-user"' in response.text


def test_invalid_form_does_not_render_password_value(
    client: TestClient,
) -> None:
    form_token, cookie_token = begin_login(
        client,
    )

    response = client.post(
        "/login",
        data={
            "username": "",
            "password": "Sensitive-password-123!",
            "csrf_token": form_token,
        },
        headers=login_cookie_header(
            cookie_token,
        ),
    )

    assert response.status_code == 422
    assert "Sensitive-password-123!" not in response.text


def test_login_submit_rejects_invalid_credentials(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
        username="invalid-route-password-user",
        password=DEFAULT_TEST_PASSWORD,
    )
    form_token, cookie_token = begin_login(
        client,
    )

    response = client.post(
        "/login",
        data={
            "username": user.username,
            "password": "Incorrect-password-123!",
            "csrf_token": form_token,
        },
        headers=login_cookie_header(
            cookie_token,
        ),
    )

    assert response.status_code == 401
    assert "Invalid username or password." in response.text
    assert "Incorrect-password-123!" not in response.text


def test_login_submit_uses_generic_error_for_unknown_username(
    client: TestClient,
) -> None:
    form_token, cookie_token = begin_login(
        client,
    )

    response = client.post(
        "/login",
        data={
            "username": "unknown-route-user",
            "password": DEFAULT_TEST_PASSWORD,
            "csrf_token": form_token,
        },
        headers=login_cookie_header(
            cookie_token,
        ),
    )

    assert response.status_code == 401
    assert "Invalid username or password." in response.text
    assert "unknown username" not in response.text.lower()


def test_invalid_credentials_preserve_username_and_remember_me(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
        username="preserved-route-user",
        password=DEFAULT_TEST_PASSWORD,
    )
    form_token, cookie_token = begin_login(
        client,
    )

    response = client.post(
        "/login",
        data={
            "username": user.username,
            "password": "Incorrect-password-123!",
            "remember_me": "true",
            "csrf_token": form_token,
        },
        headers=login_cookie_header(
            cookie_token,
        ),
    )

    assert response.status_code == 401
    assert (
        'value="preserved-route-user"'
        in response.text
    )
    assert re.search(
        (
            r'name="remember_me"'
            r'[^>]*checked'
        ),
        response.text,
        flags=re.IGNORECASE | re.DOTALL,
    )


def test_invalid_credentials_set_fresh_login_csrf_token(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
        password=DEFAULT_TEST_PASSWORD,
    )

    with patch(
        "app.web.routes.auth.generate_csrf_token",
        side_effect=[
            "first-token",
            "second-token",
        ],
    ):
        client.get(
            "/login",
        )

        response = client.post(
            "/login",
            data={
                "username": user.username,
                "password": "Incorrect-password-123!",
                "csrf_token": "first-token",
            },
            headers=login_cookie_header(
                "first-token",
            ),
        )

    assert response.status_code == 401
    assert (
        extract_hidden_input(
            response.text,
            name="csrf_token",
        )
        == "second-token"
    )
    assert (
        parse_cookie_value(
            response,
            cookie_name=LOGIN_CSRF_COOKIE_NAME,
        )
        == "second-token"
    )


def test_logout_requires_authentication_for_browser_request(
    client: TestClient,
) -> None:
    response = client.post(
        "/logout",
        data={
            "csrf_token": "unused-token",
        },
        headers={
            "accept": "text/html",
        },
    )

    assert_login_redirect(
        response,
        expected_next_url="/logout",
    )


def test_logout_requires_authentication_for_json_request(
    client: TestClient,
) -> None:
    response = client.post(
        "/logout",
        data={
            "csrf_token": "unused-token",
        },
        headers={
            "accept": "application/json",
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication is required.",
    }


def test_logout_expired_session_redirects_browser_to_login(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    _, session_token, csrf_token = (
        create_expired_auth_session(
            db,
            user=user,
        )
    )

    response = client.post(
        "/logout",
        data={
            "csrf_token": csrf_token,
        },
        headers={
            **authenticated_cookie_header(
                session_token,
            ),
            "accept": "text/html",
        },
    )

    assert_login_redirect(
        response,
        expected_next_url="/logout",
    )


def test_logout_revoked_session_redirects_browser_to_login(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    _, session_token, csrf_token = (
        create_revoked_auth_session(
            db,
            user=user,
        )
    )

    response = client.post(
        "/logout",
        data={
            "csrf_token": csrf_token,
        },
        headers={
            **authenticated_cookie_header(
                session_token,
            ),
            "accept": "text/html",
        },
    )

    assert_login_redirect(
        response,
        expected_next_url="/logout",
    )


def test_logout_requires_csrf_token(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    auth_session, session_token, _ = (
        create_auth_session(
            db,
            user=user,
        )
    )

    response = client.post(
        "/logout",
        headers=authenticated_cookie_header(
            session_token,
        ),
    )

    db.refresh(
        auth_session,
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "The security token is missing.",
    }
    assert auth_session.is_revoked is False


def test_logout_rejects_invalid_csrf_token(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    auth_session, session_token, _ = (
        create_auth_session(
            db,
            user=user,
        )
    )

    response = client.post(
        "/logout",
        data={
            "csrf_token": "invalid-csrf-token",
        },
        headers=authenticated_cookie_header(
            session_token,
        ),
    )

    db.refresh(
        auth_session,
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": (
            "The security token is invalid or "
            "has expired."
        ),
    }
    assert auth_session.is_revoked is False


def test_logout_accepts_valid_form_csrf_token(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    auth_session, session_token, csrf_token = (
        create_auth_session(
            db,
            user=user,
        )
    )

    response = client.post(
        "/logout",
        data={
            "csrf_token": csrf_token,
        },
        headers=authenticated_cookie_header(
            session_token,
            csrf_cookie_token=csrf_token,
        ),
    )

    db.refresh(
        auth_session,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert auth_session.is_revoked is True
    assert auth_session.revoked_at is not None


def test_logout_accepts_valid_csrf_header(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    auth_session, session_token, csrf_token = (
        create_auth_session(
            db,
            user=user,
        )
    )

    response = client.post(
        "/logout",
        headers={
            **authenticated_cookie_header(
                session_token,
            ),
            "x-csrf-token": csrf_token,
        },
    )

    db.refresh(
        auth_session,
    )

    assert response.status_code == 303
    assert auth_session.is_revoked is True


def test_logout_header_csrf_token_takes_precedence_over_form(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    auth_session, session_token, csrf_token = (
        create_auth_session(
            db,
            user=user,
        )
    )

    response = client.post(
        "/logout",
        data={
            "csrf_token": "invalid-form-token",
        },
        headers={
            **authenticated_cookie_header(
                session_token,
            ),
            "x-csrf-token": csrf_token,
        },
    )

    db.refresh(
        auth_session,
    )

    assert response.status_code == 303
    assert auth_session.is_revoked is True


def test_logout_deletes_authentication_cookies(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
    )
    _, session_token, csrf_token = (
        create_auth_session(
            db,
            user=user,
        )
    )

    response = client.post(
        "/logout",
        data={
            "csrf_token": csrf_token,
        },
        headers=authenticated_cookie_header(
            session_token,
            csrf_cookie_token=csrf_token,
        ),
    )

    session_cookie_header = find_set_cookie_header(
        response,
        cookie_name=settings.session_cookie_name,
    )
    csrf_cookie_header = find_set_cookie_header(
        response,
        cookie_name=AUTH_CSRF_COOKIE_NAME,
    )

    assert response.status_code == 303
    assert "Max-Age=0" in session_cookie_header
    assert "Max-Age=0" in csrf_cookie_header
    assert "Path=/" in session_cookie_header
    assert "Path=/" in csrf_cookie_header


def test_logout_records_audit_event(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
        username="logout-route-audit-user",
    )
    auth_session, session_token, csrf_token = (
        create_auth_session(
            db,
            user=user,
        )
    )

    response = client.post(
        "/logout",
        data={
            "csrf_token": csrf_token,
        },
        headers={
            **authenticated_cookie_header(
                session_token,
            ),
            "user-agent": "Logout route test",
        },
    )

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action == AuditAction.LOGOUT.value,
            AuditLog.entity_type == "auth_session",
            AuditLog.entity_id == auth_session.id,
        )
    )

    assert response.status_code == 303
    assert audit_log is not None
    assert audit_log.user_id == user.id
    assert audit_log.metadata_json == {
        "username": "logout-route-audit-user",
    }
    assert audit_log.ip_address == "testclient"
    assert audit_log.user_agent == "Logout route test"


def test_login_then_logout_complete_browser_flow(
    client: TestClient,
    db: Session,
) -> None:
    user = create_user(
        db,
        username="browser-flow-user",
        password=DEFAULT_TEST_PASSWORD,
    )
    login_form_token, login_cookie_token = (
        begin_login(
            client,
        )
    )

    login_response = client.post(
        "/login",
        data={
            "username": user.username,
            "password": DEFAULT_TEST_PASSWORD,
            "csrf_token": login_form_token,
        },
        headers=login_cookie_header(
            login_cookie_token,
        ),
    )

    session_token = parse_cookie_value(
        login_response,
        cookie_name=settings.session_cookie_name,
    )
    auth_csrf_token = parse_cookie_value(
        login_response,
        cookie_name=AUTH_CSRF_COOKIE_NAME,
    )

    logout_response = client.post(
        "/logout",
        data={
            "csrf_token": auth_csrf_token,
        },
        headers=authenticated_cookie_header(
            session_token,
            csrf_cookie_token=auth_csrf_token,
        ),
    )

    auth_session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash
            == hash_token(session_token),
        )
    )

    assert login_response.status_code == 303
    assert logout_response.status_code == 303
    assert auth_session is not None
    assert auth_session.is_revoked is True


@pytest.mark.parametrize(
    (
        "remember_me",
        "expected",
    ),
    [
        (
            False,
            settings.session_duration_hours
            * 60
            * 60,
        ),
        (
            True,
            settings.remember_me_duration_days
            * 24
            * 60
            * 60,
        ),
    ],
)
def test_get_session_cookie_max_age(
    remember_me: bool,
    expected: int,
) -> None:
    result = _get_session_cookie_max_age(
        remember_me=remember_me,
    )

    assert result == expected


@pytest.mark.parametrize(
    (
        "supplied_token",
        "cookie_token",
        "expected",
    ),
    [
        (
            None,
            None,
            False,
        ),
        (
            "token",
            None,
            False,
        ),
        (
            None,
            "token",
            False,
        ),
        (
            "",
            "token",
            False,
        ),
        (
            "   ",
            "token",
            False,
        ),
        (
            "token",
            "",
            False,
        ),
        (
            "token",
            "different",
            False,
        ),
        (
            " token ",
            " token ",
            True,
        ),
        (
            "matching-token",
            "matching-token",
            True,
        ),
    ],
)
def test_validate_login_csrf_token(
    supplied_token: str | None,
    cookie_token: str | None,
    expected: bool,
) -> None:
    result = _validate_login_csrf_token(
        supplied_token=supplied_token,
        cookie_token=cookie_token,
    )

    assert result is expected


def test_validate_login_csrf_token_handles_comparison_error(
) -> None:
    with patch(
        "app.web.routes.auth.compare_values",
        side_effect=ValueError(
            "Invalid comparison",
        ),
    ):
        result = _validate_login_csrf_token(
            supplied_token="token",
            cookie_token="token",
        )

    assert result is False


@pytest.mark.parametrize(
    (
        "value",
        "default",
        "expected",
    ),
    [
        (
            None,
            "/default",
            "/default",
        ),
        (
            "",
            "/default",
            "/default",
        ),
        (
            "   ",
            "/default",
            "/default",
        ),
        (
            "/",
            "/default",
            "/",
        ),
        (
            "/admin/users",
            "/default",
            "/admin/users",
        ),
        (
            "/admin/users?page=2#users",
            "/default",
            "/admin/users?page=2#users",
        ),
        (
            "https://example.com",
            "/default",
            "/default",
        ),
        (
            "http://example.com/path",
            "/default",
            "/default",
        ),
        (
            "//example.com/path",
            "/default",
            "/default",
        ),
        (
            "relative/path",
            "/default",
            "/default",
        ),
        (
            "admin/users",
            "/default",
            "/default",
        ),
        (
            "javascript:alert(1)",
            "/default",
            "/default",
        ),
        (
            "  /admin/users  ",
            "/default",
            "/admin/users",
        ),
    ],
)
def test_get_safe_redirect_target(
    value: str | None,
    default: str,
    expected: str,
) -> None:
    result = _get_safe_redirect_target(
        value,
        default=default,
    )

    assert result == expected


class FormDataWithGetter:
    def __init__(
        self,
        values: dict[str, object],
    ) -> None:
        self.values = values

    def get(
        self,
        field_name: str,
    ) -> object | None:
        return self.values.get(
            field_name,
        )


class FormDataWithoutGetter:
    pass


@pytest.mark.parametrize(
    (
        "form_data",
        "field_name",
        "expected",
    ),
    [
        (
            FormDataWithGetter(
                {
                    "username": "  test-user  ",
                },
            ),
            "username",
            "test-user",
        ),
        (
            FormDataWithGetter(
                {
                    "username": "",
                },
            ),
            "username",
            None,
        ),
        (
            FormDataWithGetter(
                {
                    "username": "   ",
                },
            ),
            "username",
            None,
        ),
        (
            FormDataWithGetter(
                {},
            ),
            "username",
            None,
        ),
        (
            FormDataWithGetter(
                {
                    "number": 123,
                },
            ),
            "number",
            "123",
        ),
        (
            FormDataWithoutGetter(),
            "username",
            None,
        ),
    ],
)
def test_get_form_value(
    form_data: object,
    field_name: str,
    expected: str | None,
) -> None:
    result = _get_form_value(
        form_data,
        field_name,
    )

    assert result == expected


def test_build_login_flash_messages(
) -> None:
    form = LoginForm()
    form.errors.add_form_error(
        "First login error.",
    )
    form.errors.add_form_error(
        "Second login error.",
    )

    result = _build_login_flash_messages(
        form,
    )

    assert result == [
        {
            "category": "error",
            "title": "Unable to sign in",
            "message": "First login error.",
        },
        {
            "category": "error",
            "title": "Unable to sign in",
            "message": "Second login error.",
        },
    ]


def test_build_login_flash_messages_ignores_field_errors(
) -> None:
    form = LoginForm()
    form.errors.add_field_error(
        "username",
        "Username is invalid.",
    )

    result = _build_login_flash_messages(
        form,
    )

    assert result == []