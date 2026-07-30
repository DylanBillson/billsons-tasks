from types import SimpleNamespace
from typing import cast

import pytest

from app.core import csrf
from app.core.csrf import (
    CSRFError,
    InvalidCSRFTokenError,
    MissingCSRFTokenError,
    create_csrf_token,
    validate_csrf_token,
    validate_session_csrf_token,
    verify_csrf_token,
)
from app.core.security import hash_token
from app.models.session import AuthSession


def make_auth_session(
    *,
    csrf_token_hash: str,
    is_valid: bool = True,
) -> AuthSession:
    """
    Create the minimum session-like object required by the CSRF helpers.

    These are unit tests for app.core.csrf, so constructing a complete
    SQLAlchemy model instance is unnecessary.
    """
    return cast(
        AuthSession,
        SimpleNamespace(
            csrf_token_hash=csrf_token_hash,
            is_valid=is_valid,
        ),
    )


def test_csrf_exceptions_inherit_from_csrf_error() -> None:
    assert issubclass(
        MissingCSRFTokenError,
        CSRFError,
    )
    assert issubclass(
        InvalidCSRFTokenError,
        CSRFError,
    )


def test_create_csrf_token_returns_raw_token_and_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        csrf,
        "generate_csrf_token",
        lambda: "generated-csrf-token",
    )

    token, token_hash = create_csrf_token()

    assert token == "generated-csrf-token"
    assert token_hash == hash_token(
        "generated-csrf-token",
    )
    assert token_hash != token


def test_create_csrf_token_hashes_generated_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    monkeypatch.setattr(
        csrf,
        "generate_csrf_token",
        lambda: "raw-token",
    )

    def fake_hash_token(
        token: str,
    ) -> str:
        calls.append(token)

        return "stored-token-hash"

    monkeypatch.setattr(
        csrf,
        "hash_token",
        fake_hash_token,
    )

    result = create_csrf_token()

    assert result == (
        "raw-token",
        "stored-token-hash",
    )
    assert calls == [
        "raw-token",
    ]


def test_verify_csrf_token_accepts_matching_token() -> None:
    token = "valid-csrf-token"

    assert verify_csrf_token(
        supplied_token=token,
        expected_token_hash=hash_token(token),
    )


def test_verify_csrf_token_rejects_incorrect_token() -> None:
    assert not verify_csrf_token(
        supplied_token="incorrect-token",
        expected_token_hash=hash_token(
            "correct-token",
        ),
    )


def test_verify_csrf_token_rejects_missing_token() -> None:
    assert not verify_csrf_token(
        supplied_token=None,
        expected_token_hash=hash_token(
            "expected-token",
        ),
    )


@pytest.mark.parametrize(
    "supplied_token",
    [
        "",
        " ",
        "\t",
        "\n",
        " \t\n ",
    ],
)
def test_verify_csrf_token_rejects_empty_or_whitespace_token(
    supplied_token: str,
) -> None:
    assert not verify_csrf_token(
        supplied_token=supplied_token,
        expected_token_hash=hash_token(
            "expected-token",
        ),
    )


def test_verify_csrf_token_strips_surrounding_whitespace() -> None:
    token = "valid-csrf-token"

    assert verify_csrf_token(
        supplied_token=f"  {token}\n",
        expected_token_hash=hash_token(token),
    )


def test_verify_csrf_token_does_not_modify_internal_whitespace() -> None:
    token = "token with spaces"

    assert verify_csrf_token(
        supplied_token=f"  {token}  ",
        expected_token_hash=hash_token(token),
    )


def test_verify_csrf_token_uses_constant_time_comparison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    def fake_hash_token(
        token: str,
    ) -> str:
        assert token == "supplied-token"

        return "supplied-token-hash"

    def fake_compare_values(
        supplied_value: str,
        expected_value: str,
    ) -> bool:
        calls.append(
            (
                supplied_value,
                expected_value,
            ),
        )

        return True

    monkeypatch.setattr(
        csrf,
        "hash_token",
        fake_hash_token,
    )
    monkeypatch.setattr(
        csrf,
        "compare_values",
        fake_compare_values,
    )

    result = verify_csrf_token(
        supplied_token="supplied-token",
        expected_token_hash="expected-token-hash",
    )

    assert result is True
    assert calls == [
        (
            "supplied-token-hash",
            "expected-token-hash",
        ),
    ]


@pytest.mark.parametrize(
    "exception",
    [
        TypeError("invalid value"),
        ValueError("invalid value"),
        UnicodeError("invalid value"),
    ],
)
def test_verify_csrf_token_returns_false_when_hashing_fails(
    monkeypatch: pytest.MonkeyPatch,
    exception: Exception,
) -> None:
    def fake_hash_token(
        token: str,
    ) -> str:
        raise exception

    monkeypatch.setattr(
        csrf,
        "hash_token",
        fake_hash_token,
    )

    assert not verify_csrf_token(
        supplied_token="supplied-token",
        expected_token_hash="expected-token-hash",
    )


@pytest.mark.parametrize(
    "exception",
    [
        TypeError("invalid value"),
        ValueError("invalid value"),
        UnicodeError("invalid value"),
    ],
)
def test_verify_csrf_token_returns_false_when_comparison_fails(
    monkeypatch: pytest.MonkeyPatch,
    exception: Exception,
) -> None:
    def fake_compare_values(
        supplied_value: str,
        expected_value: str,
    ) -> bool:
        raise exception

    monkeypatch.setattr(
        csrf,
        "compare_values",
        fake_compare_values,
    )

    assert not verify_csrf_token(
        supplied_token="supplied-token",
        expected_token_hash=hash_token(
            "supplied-token",
        ),
    )


def test_validate_csrf_token_accepts_matching_token() -> None:
    token = "valid-csrf-token"

    validate_csrf_token(
        supplied_token=token,
        expected_token_hash=hash_token(token),
    )


@pytest.mark.parametrize(
    "supplied_token",
    [
        None,
        "",
        " ",
        "\t",
        "\n",
        " \t\n ",
    ],
)
def test_validate_csrf_token_raises_missing_error_for_missing_or_empty_token(
    supplied_token: str | None,
) -> None:
    with pytest.raises(
        MissingCSRFTokenError,
        match=r"^CSRF token is required\.$",
    ):
        validate_csrf_token(
            supplied_token=supplied_token,
            expected_token_hash=hash_token(
                "expected-token",
            ),
        )


def test_validate_csrf_token_raises_invalid_error_for_incorrect_token() -> None:
    with pytest.raises(
        InvalidCSRFTokenError,
        match=r"^CSRF token is invalid\.$",
    ):
        validate_csrf_token(
            supplied_token="incorrect-token",
            expected_token_hash=hash_token(
                "correct-token",
            ),
        )


def test_validate_csrf_token_uses_verification_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str | None, str]] = []

    def fake_verify_csrf_token(
        *,
        supplied_token: str | None,
        expected_token_hash: str,
    ) -> bool:
        calls.append(
            (
                supplied_token,
                expected_token_hash,
            ),
        )

        return True

    monkeypatch.setattr(
        csrf,
        "verify_csrf_token",
        fake_verify_csrf_token,
    )

    validate_csrf_token(
        supplied_token="supplied-token",
        expected_token_hash="expected-token-hash",
    )

    assert calls == [
        (
            "supplied-token",
            "expected-token-hash",
        ),
    ]


def test_validate_session_csrf_token_accepts_valid_session_and_token() -> None:
    token = "valid-csrf-token"
    auth_session = make_auth_session(
        csrf_token_hash=hash_token(token),
        is_valid=True,
    )

    validate_session_csrf_token(
        auth_session=auth_session,
        supplied_token=token,
    )


def test_validate_session_csrf_token_rejects_invalid_session() -> None:
    token = "valid-csrf-token"
    auth_session = make_auth_session(
        csrf_token_hash=hash_token(token),
        is_valid=False,
    )

    with pytest.raises(
        InvalidCSRFTokenError,
        match=(
            r"^The authentication session is no longer valid\.$"
        ),
    ):
        validate_session_csrf_token(
            auth_session=auth_session,
            supplied_token=token,
        )


def test_validate_session_csrf_token_rejects_invalid_session_before_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth_session = make_auth_session(
        csrf_token_hash="stored-token-hash",
        is_valid=False,
    )

    called = False

    def fake_validate_csrf_token(
        *,
        supplied_token: str | None,
        expected_token_hash: str,
    ) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(
        csrf,
        "validate_csrf_token",
        fake_validate_csrf_token,
    )

    with pytest.raises(
        InvalidCSRFTokenError,
        match=(
            r"^The authentication session is no longer valid\.$"
        ),
    ):
        validate_session_csrf_token(
            auth_session=auth_session,
            supplied_token="supplied-token",
        )

    assert called is False


def test_validate_session_csrf_token_uses_session_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth_session = make_auth_session(
        csrf_token_hash="session-csrf-token-hash",
        is_valid=True,
    )

    calls: list[tuple[str | None, str]] = []

    def fake_validate_csrf_token(
        *,
        supplied_token: str | None,
        expected_token_hash: str,
    ) -> None:
        calls.append(
            (
                supplied_token,
                expected_token_hash,
            ),
        )

    monkeypatch.setattr(
        csrf,
        "validate_csrf_token",
        fake_validate_csrf_token,
    )

    validate_session_csrf_token(
        auth_session=auth_session,
        supplied_token="supplied-token",
    )

    assert calls == [
        (
            "supplied-token",
            "session-csrf-token-hash",
        ),
    ]


def test_validate_session_csrf_token_propagates_missing_token_error() -> None:
    auth_session = make_auth_session(
        csrf_token_hash=hash_token(
            "expected-token",
        ),
        is_valid=True,
    )

    with pytest.raises(
        MissingCSRFTokenError,
        match=r"^CSRF token is required\.$",
    ):
        validate_session_csrf_token(
            auth_session=auth_session,
            supplied_token=None,
        )


def test_validate_session_csrf_token_propagates_invalid_token_error() -> None:
    auth_session = make_auth_session(
        csrf_token_hash=hash_token(
            "correct-token",
        ),
        is_valid=True,
    )

    with pytest.raises(
        InvalidCSRFTokenError,
        match=r"^CSRF token is invalid\.$",
    ):
        validate_session_csrf_token(
            auth_session=auth_session,
            supplied_token="incorrect-token",
        )