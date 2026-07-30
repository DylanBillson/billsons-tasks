import hashlib
import hmac
import secrets

import bcrypt

from app.core.config import settings


BCRYPT_MAX_PASSWORD_BYTES = 72
SESSION_TOKEN_BYTES = 32
CSRF_TOKEN_BYTES = 32


class PasswordValidationError(ValueError):
    """Raised when a password does not meet application requirements."""


def validate_password(
    password: str,
    *,
    confirmation: str | None = None,
) -> None:
    """
    Validate a plaintext password against application requirements.

    The password is never modified or normalised because leading and trailing
    whitespace may be intentional.
    """
    if confirmation is not None and password != confirmation:
        raise PasswordValidationError(
            "Passwords do not match.",
        )

    if len(password) < settings.password_min_length:
        raise PasswordValidationError(
            "Password must contain at least "
            f"{settings.password_min_length} characters.",
        )

    password_bytes = password.encode("utf-8")

    if len(password_bytes) > BCRYPT_MAX_PASSWORD_BYTES:
        raise PasswordValidationError(
            "Password cannot exceed 72 UTF-8 bytes.",
        )


def hash_password(
    password: str,
    *,
    validate: bool = True,
) -> str:
    """
    Hash a plaintext password using bcrypt.

    Passwords should normally be validated before hashing. The validation flag
    exists for controlled internal uses such as generating a dummy hash.
    """
    if validate:
        validate_password(password)

    password_bytes = password.encode("utf-8")

    if len(password_bytes) > BCRYPT_MAX_PASSWORD_BYTES:
        raise PasswordValidationError(
            "Password cannot exceed 72 UTF-8 bytes.",
        )

    password_hash = bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt(),
    )

    return password_hash.decode("utf-8")


def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    """
    Verify a plaintext password against a bcrypt hash.

    Invalid or malformed hashes return False rather than exposing an exception
    to the authentication flow.
    """
    try:
        password_bytes = password.encode("utf-8")

        if len(password_bytes) > BCRYPT_MAX_PASSWORD_BYTES:
            return False

        return bcrypt.checkpw(
            password_bytes,
            password_hash.encode("utf-8"),
        )

    except (
        TypeError,
        ValueError,
    ):
        return False


def password_hash_needs_update(
    password_hash: str,
) -> bool:
    """
    Return whether a stored bcrypt hash should be replaced.

    This currently checks whether the hash uses bcrypt's configured default
    cost. It allows passwords to be transparently rehashed after a successful
    login when bcrypt's default cost changes.
    """
    try:
        hash_parts = password_hash.split("$")

        if len(hash_parts) < 4:
            return True

        stored_rounds = int(hash_parts[2])

        generated_hash = bcrypt.hashpw(
            b"bcrypt-cost-check",
            bcrypt.gensalt(),
        ).decode("utf-8")

        generated_parts = generated_hash.split("$")
        current_rounds = int(generated_parts[2])

        return stored_rounds != current_rounds

    except (
        TypeError,
        ValueError,
    ):
        return True


def generate_secure_token(
    *,
    byte_length: int = SESSION_TOKEN_BYTES,
) -> str:
    """
    Generate a URL-safe cryptographically secure token.

    Only the raw token should be sent to the client. Database records should
    store the result of hash_token() instead.
    """
    if byte_length < 16:
        raise ValueError(
            "Secure tokens must use at least 16 random bytes.",
        )

    return secrets.token_urlsafe(byte_length)


def generate_session_token() -> str:
    """Generate a new authentication session token."""
    return generate_secure_token(
        byte_length=SESSION_TOKEN_BYTES,
    )


def generate_csrf_token() -> str:
    """Generate a new CSRF token."""
    return generate_secure_token(
        byte_length=CSRF_TOKEN_BYTES,
    )


def hash_token(
    token: str,
) -> str:
    """
    Create a deterministic SHA-256 digest for a secure random token.

    Session tokens are already high-entropy random values, so a fast
    cryptographic hash is appropriate. Password hashes must continue to use
    bcrypt instead.
    """
    return hashlib.sha256(
        token.encode("utf-8"),
    ).hexdigest()


def compare_values(
    supplied_value: str,
    expected_value: str,
) -> bool:
    """Compare two strings using a constant-time comparison."""
    return hmac.compare_digest(
        supplied_value.encode("utf-8"),
        expected_value.encode("utf-8"),
    )


def verify_token_hash(
    token: str,
    expected_hash: str,
) -> bool:
    """Hash a supplied token and compare it with a stored digest."""
    return compare_values(
        hash_token(token),
        expected_hash,
    )


# Used when a username does not exist so failed login attempts still perform a
# bcrypt verification and reveal less timing information.
DUMMY_PASSWORD_HASH = hash_password(
    "dummy-password-used-only-for-timing-protection",
    validate=False,
)