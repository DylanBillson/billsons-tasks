from app.core.security import (
    compare_values,
    generate_csrf_token,
    hash_token,
)
from app.models.session import AuthSession


class CSRFError(ValueError):
    """Base exception for CSRF validation failures."""


class MissingCSRFTokenError(CSRFError):
    """Raised when no CSRF token was submitted."""


class InvalidCSRFTokenError(CSRFError):
    """Raised when the submitted CSRF token is invalid."""


def create_csrf_token() -> tuple[str, str]:
    """
    Generate a raw CSRF token and its persistent hash.

    The raw token is returned to the browser. Only the hash should be stored
    in the database.
    """
    token = generate_csrf_token()

    return (
        token,
        hash_token(token),
    )


def verify_csrf_token(
    *,
    supplied_token: str | None,
    expected_token_hash: str,
) -> bool:
    """
    Verify a raw CSRF token against a stored SHA-256 token hash.

    Missing, empty or malformed values return False rather than exposing an
    exception to the request-handling layer.
    """
    if supplied_token is None:
        return False

    normalised_token = supplied_token.strip()

    if not normalised_token:
        return False

    try:
        supplied_hash = hash_token(
            normalised_token,
        )

        return compare_values(
            supplied_hash,
            expected_token_hash,
        )

    except (
        TypeError,
        ValueError,
        UnicodeError,
    ):
        return False


def validate_csrf_token(
    *,
    supplied_token: str | None,
    expected_token_hash: str,
) -> None:
    """
    Validate a submitted CSRF token.

    Raises a specific exception so the web layer can return a consistent
    forbidden response or render an appropriate error page.
    """
    if supplied_token is None or not supplied_token.strip():
        raise MissingCSRFTokenError(
            "CSRF token is required.",
        )

    if not verify_csrf_token(
        supplied_token=supplied_token,
        expected_token_hash=expected_token_hash,
    ):
        raise InvalidCSRFTokenError(
            "CSRF token is invalid.",
        )


def validate_session_csrf_token(
    *,
    auth_session: AuthSession,
    supplied_token: str | None,
) -> None:
    """
    Validate a submitted CSRF token against an authentication session.

    Revoked or expired sessions are rejected even when the supplied token
    matches the stored hash.
    """
    if not auth_session.is_valid:
        raise InvalidCSRFTokenError(
            "The authentication session is no longer valid.",
        )

    validate_csrf_token(
        supplied_token=supplied_token,
        expected_token_hash=auth_session.csrf_token_hash,
    )