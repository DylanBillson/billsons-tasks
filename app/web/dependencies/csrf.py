from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.core.csrf import (
    InvalidCSRFTokenError,
    MissingCSRFTokenError,
    validate_session_csrf_token,
)
from app.models.session import AuthSession
from app.web.dependencies.auth import CurrentAuthSession


CSRF_FORM_FIELD_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"

SAFE_HTTP_METHODS = {
    "GET",
    "HEAD",
    "OPTIONS",
    "TRACE",
}


class CSRFValidationError(HTTPException):
    def __init__(
        self,
        *,
        detail: str = "The security token is missing or invalid.",
    ) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


async def get_submitted_csrf_token(
    request: Request,
) -> str | None:
    """
    Read the submitted CSRF token from a request.

    HTML forms should submit the token using the `csrf_token` field. API-style
    requests may provide the same token in the `X-CSRF-Token` header.
    """
    header_token = request.headers.get(
        CSRF_HEADER_NAME,
    )

    if header_token is not None:
        normalised_header_token = header_token.strip()

        if normalised_header_token:
            return normalised_header_token

    content_type = request.headers.get(
        "content-type",
        "",
    ).lower()

    if (
        "application/x-www-form-urlencoded" not in content_type
        and "multipart/form-data" not in content_type
    ):
        return None

    form_data = await request.form()

    raw_token = form_data.get(
        CSRF_FORM_FIELD_NAME,
    )

    if raw_token is None:
        return None

    token = str(
        raw_token,
    ).strip()

    if not token:
        return None

    return token


async def validate_csrf_request(
    request: Request,
    auth_session: CurrentAuthSession,
) -> None:
    """
    Validate CSRF protection for an authenticated unsafe request.

    Safe methods are ignored. POST, PUT, PATCH, DELETE and any other unsafe
    methods require a token tied to the current authentication session.
    """
    if request.method.upper() in SAFE_HTTP_METHODS:
        return

    supplied_token = await get_submitted_csrf_token(
        request,
    )

    try:
        validate_session_csrf_token(
            auth_session=auth_session,
            supplied_token=supplied_token,
        )

    except MissingCSRFTokenError as exc:
        raise CSRFValidationError(
            detail="The security token is missing.",
        ) from exc

    except InvalidCSRFTokenError as exc:
        raise CSRFValidationError(
            detail="The security token is invalid or has expired.",
        ) from exc


async def require_csrf_token(
    request: Request,
    auth_session: CurrentAuthSession,
) -> AuthSession:
    """
    FastAPI dependency for authenticated state-changing routes.

    Returning the validated authentication session lets routes use one
    dependency for both authentication and CSRF validation.
    """
    await validate_csrf_request(
        request,
        auth_session,
    )

    return auth_session


ValidatedCSRFSession = Annotated[
    AuthSession,
    Depends(require_csrf_token),
]