from urllib.parse import urlsplit

from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.config import settings
from app.core.security import (
    compare_values,
    generate_csrf_token,
)
from app.services.auth_service import (
    AuthService,
    InvalidCredentialsError,
)
from app.web.dependencies.auth import (
    DatabaseSession,
    OptionalCurrentUser,
    get_client_ip_address,
    get_session_token,
    get_user_agent,
)
from app.web.dependencies.csrf import (
    CSRF_FORM_FIELD_NAME,
    ValidatedCSRFSession,
)
from app.web.forms.auth import LoginForm
from app.web.templating import templates


router = APIRouter(
    tags=[
        "authentication",
    ],
)


LOGIN_CSRF_COOKIE_NAME = (
    f"{settings.session_cookie_name}_login_csrf"
)

AUTH_CSRF_COOKIE_NAME = (
    f"{settings.session_cookie_name}_csrf"
)

LOGIN_CSRF_COOKIE_MAX_AGE_SECONDS = 15 * 60


@router.get(
    "/login",
    response_class=HTMLResponse,
    name="login",
)
def login_page(
    request: Request,
    current_user: OptionalCurrentUser,
    next_url: str | None = None,
) -> HTMLResponse:
    """
    Render the login page.

    Authenticated users are redirected away from the login form. Anonymous
    visitors receive a temporary double-submit CSRF token used only for the
    login request.
    """
    if current_user is not None:
        return RedirectResponse(
            url=_get_safe_redirect_target(
                next_url,
                default="/",
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    login_csrf_token = generate_csrf_token()

    response = templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={
            "form": LoginForm(),
            "login_csrf_token": login_csrf_token,
            "next_url": _get_safe_redirect_target(
                next_url,
                default="",
            ),
            "flash_messages": [],
        },
        status_code=status.HTTP_200_OK,
    )

    _set_login_csrf_cookie(
        response,
        token=login_csrf_token,
    )

    return response


@router.post(
    "/login",
    response_class=HTMLResponse,
    name="login_submit",
)
async def login_submit(
    request: Request,
    db: DatabaseSession,
) -> HTMLResponse:
    """
    Authenticate a submitted username and password.

    Successful authentication creates a database-backed session and sets both
    the session cookie and the authenticated CSRF-token cookie.
    """
    form_data = await request.form()

    login_form = LoginForm.from_form_data(
        form_data,
    )

    submitted_login_csrf_token = _get_form_value(
        form_data,
        CSRF_FORM_FIELD_NAME,
    )

    expected_login_csrf_token = request.cookies.get(
        LOGIN_CSRF_COOKIE_NAME,
    )

    next_url = _get_safe_redirect_target(
        _get_form_value(
            form_data,
            "next_url",
        ),
        default="/",
    )

    if not _validate_login_csrf_token(
        supplied_token=submitted_login_csrf_token,
        cookie_token=expected_login_csrf_token,
    ):
        login_form.errors.add_form_error(
            "The security token is missing or invalid. "
            "Please submit the form again.",
        )

        login_form.clear_password()

        return _render_failed_login(
            request=request,
            form=login_form,
            next_url=next_url,
            status_code=status.HTTP_403_FORBIDDEN,
        )

    login_request = login_form.validate()

    if login_request is None:
        login_form.clear_password()

        return _render_failed_login(
            request=request,
            form=login_form,
            next_url=next_url,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    try:
        login_result = AuthService.authenticate(
            db,
            login=login_request,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except InvalidCredentialsError:
        login_form.errors.add_form_error(
            "Invalid username or password.",
        )

        login_form.clear_password()

        return _render_failed_login(
            request=request,
            form=login_form,
            next_url=next_url,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    response = RedirectResponse(
        url=next_url,
        status_code=status.HTTP_303_SEE_OTHER,
    )

    _set_authentication_cookies(
        response,
        session_token=login_result.session_token,
        csrf_token=login_result.csrf_token,
        remember_me=login_result.remember_me,
    )

    response.delete_cookie(
        key=LOGIN_CSRF_COOKIE_NAME,
        path="/login",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite=settings.session_cookie_samesite,
    )

    return response


@router.post(
    "/logout",
    name="logout",
)
def logout(
    request: Request,
    auth_session: ValidatedCSRFSession,
    db: DatabaseSession,
) -> RedirectResponse:
    """
    Revoke the current authentication session and remove its browser cookies.

    Authentication and CSRF validation are completed by
    `ValidatedCSRFSession` before the route executes.
    """
    del auth_session

    AuthService.logout(
        db,
        session_token=get_session_token(
            request,
        ),
        ip_address=get_client_ip_address(
            request,
        ),
        user_agent=get_user_agent(
            request,
        ),
    )

    response = RedirectResponse(
        url="/login",
        status_code=status.HTTP_303_SEE_OTHER,
    )

    _delete_authentication_cookies(
        response,
    )

    return response


def _render_failed_login(
    *,
    request: Request,
    form: LoginForm,
    next_url: str,
    status_code: int,
) -> HTMLResponse:
    """
    Re-render the login page with a fresh temporary login CSRF token.
    """
    login_csrf_token = generate_csrf_token()

    response = templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={
            "form": form,
            "login_csrf_token": login_csrf_token,
            "next_url": next_url,
            "flash_messages": _build_login_flash_messages(
                form,
            ),
        },
        status_code=status_code,
    )

    _set_login_csrf_cookie(
        response,
        token=login_csrf_token,
    )

    return response


def _set_login_csrf_cookie(
    response: HTMLResponse,
    *,
    token: str,
) -> None:
    response.set_cookie(
        key=LOGIN_CSRF_COOKIE_NAME,
        value=token,
        max_age=LOGIN_CSRF_COOKIE_MAX_AGE_SECONDS,
        path="/login",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite=settings.session_cookie_samesite,
    )


def _set_authentication_cookies(
    response: RedirectResponse,
    *,
    session_token: str,
    csrf_token: str,
    remember_me: bool,
) -> None:
    max_age = _get_session_cookie_max_age(
        remember_me=remember_me,
    )

    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_token,
        max_age=max_age,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=settings.session_cookie_httponly,
        samesite=settings.session_cookie_samesite,
    )

    response.set_cookie(
        key=AUTH_CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=max_age,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite=settings.session_cookie_samesite,
    )


def _delete_authentication_cookies(
    response: RedirectResponse,
) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=settings.session_cookie_httponly,
        samesite=settings.session_cookie_samesite,
    )

    response.delete_cookie(
        key=AUTH_CSRF_COOKIE_NAME,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite=settings.session_cookie_samesite,
    )


def _get_session_cookie_max_age(
    *,
    remember_me: bool,
) -> int:
    if remember_me:
        return (
            settings.remember_me_duration_days
            * 24
            * 60
            * 60
        )

    return (
        settings.session_duration_hours
        * 60
        * 60
    )


def _validate_login_csrf_token(
    *,
    supplied_token: str | None,
    cookie_token: str | None,
) -> bool:
    if supplied_token is None or cookie_token is None:
        return False

    supplied_token = supplied_token.strip()
    cookie_token = cookie_token.strip()

    if not supplied_token or not cookie_token:
        return False

    try:
        return compare_values(
            supplied_token,
            cookie_token,
        )
    except (
        TypeError,
        ValueError,
        UnicodeError,
    ):
        return False


def _build_login_flash_messages(
    form: LoginForm,
) -> list[dict[str, str | None]]:
    return [
        {
            "category": "error",
            "title": "Unable to sign in",
            "message": message,
        }
        for message in form.errors.form_errors
    ]


def _get_form_value(
    form_data: object,
    field_name: str,
) -> str | None:
    getter = getattr(
        form_data,
        "get",
        None,
    )

    if getter is None:
        return None

    raw_value = getter(
        field_name,
    )

    if raw_value is None:
        return None

    value = str(
        raw_value,
    ).strip()

    return value or None


def _get_safe_redirect_target(
    value: str | None,
    *,
    default: str,
) -> str:
    """
    Accept only local absolute-path redirects.

    This prevents a crafted `next_url` value from turning the login endpoint
    into an open redirect to another domain.
    """
    if value is None:
        return default

    candidate = value.strip()

    if not candidate:
        return default

    parsed = urlsplit(
        candidate,
    )

    if parsed.scheme or parsed.netloc:
        return default

    if not candidate.startswith("/"):
        return default

    if candidate.startswith("//"):
        return default

    return candidate