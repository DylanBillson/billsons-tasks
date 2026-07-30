from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import GlobalRole
from app.db.session import get_db
from app.models.session import AuthSession
from app.models.user import User
from app.services.auth_service import AuthService


class AuthenticationRequiredError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required.",
        )


class AdministratorRequiredError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access is required.",
        )


def get_client_ip_address(
    request: Request,
) -> str | None:
    """
    Return the request's client IP address.

    Proxy headers are intentionally not trusted here. Traefik or another
    trusted-proxy middleware can later normalise request.client when required.
    """
    if request.client is None:
        return None

    return request.client.host


def get_user_agent(
    request: Request,
) -> str | None:
    return request.headers.get(
        "user-agent",
    )


def get_session_token(
    request: Request,
) -> str | None:
    token = request.cookies.get(
        settings.session_cookie_name,
    )

    if token is None:
        return None

    normalised_token = token.strip()

    if not normalised_token:
        return None

    return normalised_token


def get_optional_auth_session(
    request: Request,
    db: Annotated[
        Session,
        Depends(get_db),
    ],
) -> AuthSession | None:
    """
    Resolve the current database-backed authentication session.

    Invalid, expired or revoked sessions are treated as unauthenticated.
    """
    auth_session = AuthService.resolve_session(
        db,
        session_token=get_session_token(
            request,
        ),
        update_last_seen=True,
        ip_address=get_client_ip_address(
            request,
        ),
        user_agent=get_user_agent(
            request,
        ),
    )

    request.state.auth_session = auth_session
    request.state.current_user = (
        auth_session.user
        if auth_session is not None
        else None
    )

    return auth_session


def require_auth_session(
    auth_session: Annotated[
        AuthSession | None,
        Depends(get_optional_auth_session),
    ],
) -> AuthSession:
    if auth_session is None:
        raise AuthenticationRequiredError()

    return auth_session


def get_optional_current_user(
    auth_session: Annotated[
        AuthSession | None,
        Depends(get_optional_auth_session),
    ],
) -> User | None:
    if auth_session is None:
        return None

    return auth_session.user


def require_current_user(
    user: Annotated[
        User | None,
        Depends(get_optional_current_user),
    ],
) -> User:
    if user is None:
        raise AuthenticationRequiredError()

    return user


def require_administrator(
    user: Annotated[
        User,
        Depends(require_current_user),
    ],
) -> User:
    if user.global_role != GlobalRole.ADMINISTRATOR.value:
        raise AdministratorRequiredError()

    return user


def require_non_administrator(
    user: Annotated[
        User,
        Depends(require_current_user),
    ],
) -> User:
    """
    Require an authenticated standard user.

    This dependency is available for pages that administrators should not use
    directly, although most application pages will normally accept both roles.
    """
    if user.global_role == GlobalRole.ADMINISTRATOR.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This page is only available to standard users.",
        )

    return user


DatabaseSession = Annotated[
    Session,
    Depends(get_db),
]

OptionalAuthSession = Annotated[
    AuthSession | None,
    Depends(get_optional_auth_session),
]

CurrentAuthSession = Annotated[
    AuthSession,
    Depends(require_auth_session),
]

OptionalCurrentUser = Annotated[
    User | None,
    Depends(get_optional_current_user),
]

CurrentUser = Annotated[
    User,
    Depends(require_current_user),
]

AdministratorUser = Annotated[
    User,
    Depends(require_administrator),
]