import re

import bcrypt
import pytest

from app.core import security
from app.core.security import (
    BCRYPT_MAX_PASSWORD_BYTES,
    CSRF_TOKEN_BYTES,
    SESSION_TOKEN_BYTES,
    PasswordValidationError,
    compare_values,
    generate_csrf_token,
    generate_secure_token,
    generate_session_token,
    hash_password,
    hash_token,
    password_hash_needs_update,
    validate_password,
    verify_password,
    verify_token_hash,
)


def test_validate_password_accepts_valid_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        security.settings,
        "password_min_length",
        8,
    )

    validate_password(
        "correct-horse-battery-staple",
        confirmation="correct-horse-battery-staple",
    )


def test_validate_password_rejects_mismatched_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        security.settings,
        "password_min_length",
        8,
    )

    with pytest.raises(
        PasswordValidationError,
        match="Passwords do not match.",
    ):
        validate_password(
            "correct-password",
            confirmation="different-password",
        )


def test_validate_password_rejects_password_below_minimum_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        security.settings,
        "password_min_length",
        12,
    )

    with pytest.raises(
        PasswordValidationError,
        match="Password must contain at least 12 characters.",
    ):
        validate_password(
            "short",
        )


def test_validate_password_uses_character_length_for_minimum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        security.settings,
        "password_min_length",
        4,
    )

    validate_password(
        "éééé",
    )


def test_validate_password_rejects_more_than_72_utf8_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        security.settings,
        "password_min_length",
        1,
    )

    password = "é" * 37

    assert len(password) == 37
    assert len(password.encode("utf-8")) == 74

    with pytest.raises(
        PasswordValidationError,
        match="Password cannot exceed 72 UTF-8 bytes.",
    ):
        validate_password(
            password,
        )


def test_validate_password_accepts_exactly_72_utf8_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        security.settings,
        "password_min_length",
        1,
    )

    password = "a" * BCRYPT_MAX_PASSWORD_BYTES

    validate_password(
        password,
    )


def test_hash_password_returns_bcrypt_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        security.settings,
        "password_min_length",
        8,
    )

    password = "correct-password"
    password_hash = hash_password(
        password,
    )

    assert password_hash != password
    assert password_hash.startswith(
        (
            "$2a$",
            "$2b$",
            "$2y$",
        ),
    )
    assert verify_password(
        password,
        password_hash,
    )


def test_hash_password_generates_different_hashes_for_same_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        security.settings,
        "password_min_length",
        8,
    )

    password = "correct-password"

    first_hash = hash_password(
        password,
    )
    second_hash = hash_password(
        password,
    )

    assert first_hash != second_hash
    assert verify_password(
        password,
        first_hash,
    )
    assert verify_password(
        password,
        second_hash,
    )


def test_hash_password_validates_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        security.settings,
        "password_min_length",
        12,
    )

    with pytest.raises(
        PasswordValidationError,
    ):
        hash_password(
            "short",
        )


def test_hash_password_can_skip_minimum_length_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        security.settings,
        "password_min_length",
        100,
    )

    password_hash = hash_password(
        "short",
        validate=False,
    )

    assert verify_password(
        "short",
        password_hash,
    )


def test_hash_password_still_rejects_more_than_72_bytes_when_validation_skipped(
) -> None:
    with pytest.raises(
        PasswordValidationError,
        match="Password cannot exceed 72 UTF-8 bytes.",
    ):
        hash_password(
            "a" * 73,
            validate=False,
        )


def test_verify_password_rejects_incorrect_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        security.settings,
        "password_min_length",
        8,
    )

    password_hash = hash_password(
        "correct-password",
    )

    assert not verify_password(
        "incorrect-password",
        password_hash,
    )


@pytest.mark.parametrize(
    "password_hash",
    [
        "",
        "not-a-bcrypt-hash",
        "$2b$invalid",
    ],
)
def test_verify_password_returns_false_for_malformed_hash(
    password_hash: str,
) -> None:
    assert not verify_password(
        "correct-password",
        password_hash,
    )


def test_verify_password_returns_false_for_password_over_72_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        security.settings,
        "password_min_length",
        1,
    )

    password_hash = hash_password(
        "correct-password",
    )

    assert not verify_password(
        "a" * 73,
        password_hash,
    )


def test_password_hash_needs_update_returns_false_for_current_cost() -> None:
    current_hash = bcrypt.hashpw(
        b"password",
        bcrypt.gensalt(),
    ).decode("utf-8")

    assert not password_hash_needs_update(
        current_hash,
    )


def test_password_hash_needs_update_returns_true_for_different_cost() -> None:
    generated_hash = bcrypt.hashpw(
        b"password",
        bcrypt.gensalt(),
    ).decode("utf-8")

    current_cost = int(
        generated_hash.split("$")[2],
    )

    different_cost = (
        current_cost - 1
        if current_cost > 4
        else current_cost + 1
    )

    different_cost_hash = bcrypt.hashpw(
        b"password",
        bcrypt.gensalt(
            rounds=different_cost,
        ),
    ).decode("utf-8")

    assert password_hash_needs_update(
        different_cost_hash,
    )


@pytest.mark.parametrize(
    "password_hash",
    [
        "",
        "invalid",
        "$2b$not-a-number$invalid",
    ],
)
def test_password_hash_needs_update_returns_true_for_invalid_hash(
    password_hash: str,
) -> None:
    assert password_hash_needs_update(
        password_hash,
    )


def test_generate_secure_token_returns_url_safe_value() -> None:
    token = generate_secure_token(
        byte_length=16,
    )

    assert token
    assert re.fullmatch(
        r"[A-Za-z0-9_-]+",
        token,
    )


def test_generate_secure_token_returns_unique_values() -> None:
    tokens = {
        generate_secure_token()
        for _ in range(25)
    }

    assert len(tokens) == 25


@pytest.mark.parametrize(
    "byte_length",
    [
        -1,
        0,
        1,
        15,
    ],
)
def test_generate_secure_token_rejects_lengths_below_16_bytes(
    byte_length: int,
) -> None:
    with pytest.raises(
        ValueError,
        match="Secure tokens must use at least 16 random bytes.",
    ):
        generate_secure_token(
            byte_length=byte_length,
        )


def test_generate_session_token_uses_configured_byte_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, int] = {}

    def fake_generate_secure_token(
        *,
        byte_length: int,
    ) -> str:
        captured["byte_length"] = byte_length

        return "session-token"

    monkeypatch.setattr(
        security,
        "generate_secure_token",
        fake_generate_secure_token,
    )

    token = generate_session_token()

    assert token == "session-token"
    assert captured["byte_length"] == SESSION_TOKEN_BYTES


def test_generate_csrf_token_uses_configured_byte_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, int] = {}

    def fake_generate_secure_token(
        *,
        byte_length: int,
    ) -> str:
        captured["byte_length"] = byte_length

        return "csrf-token"

    monkeypatch.setattr(
        security,
        "generate_secure_token",
        fake_generate_secure_token,
    )

    token = generate_csrf_token()

    assert token == "csrf-token"
    assert captured["byte_length"] == CSRF_TOKEN_BYTES


def test_hash_token_returns_deterministic_sha256_digest() -> None:
    first_hash = hash_token(
        "example-token",
    )
    second_hash = hash_token(
        "example-token",
    )

    assert first_hash == second_hash
    assert len(first_hash) == 64
    assert re.fullmatch(
        r"[0-9a-f]{64}",
        first_hash,
    )


def test_hash_token_returns_different_digest_for_different_values() -> None:
    assert hash_token(
        "first-token",
    ) != hash_token(
        "second-token",
    )


def test_compare_values_returns_true_for_matching_values() -> None:
    assert compare_values(
        "matching-value",
        "matching-value",
    )


def test_compare_values_returns_false_for_different_values() -> None:
    assert not compare_values(
        "first-value",
        "second-value",
    )


def test_verify_token_hash_accepts_matching_token() -> None:
    token = "example-token"
    expected_hash = hash_token(
        token,
    )

    assert verify_token_hash(
        token,
        expected_hash,
    )


def test_verify_token_hash_rejects_incorrect_token() -> None:
    expected_hash = hash_token(
        "correct-token",
    )

    assert not verify_token_hash(
        "incorrect-token",
        expected_hash,
    )


def test_dummy_password_hash_is_valid_bcrypt_hash() -> None:
    assert security.DUMMY_PASSWORD_HASH
    assert verify_password(
        "dummy-password-used-only-for-timing-protection",
        security.DUMMY_PASSWORD_HASH,
    )