from urllib.parse import urlencode

from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.config import settings
from app.services.user_service import (
    UserNotFoundError,
    UserPermissionError,
    UserService,
)
from app.web.dependencies.auth import (
    AdministratorUser,
    DatabaseSession,
)
from app.web.dependencies.csrf import ValidatedCSRFSession
from app.web.forms.auth import PasswordResetForm
from app.web.templating import templates


router = APIRouter(
    prefix="/admin/users",
    tags=[
        "admin users",
    ],
)


@router.get(
    "",
    response_class=HTMLResponse,
    name="admin_users",
)
def list_users(
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
    success: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    """
    Display all application users.

    Access is restricted to global administrators.
    """
    users = UserService.list_users(
        db,
        actor=administrator,
    )

    return templates.TemplateResponse(
        request=request,
        name="admin/users/index.html",
        context={
            "current_user": administrator,
            "users": users,
            "flash_messages": _build_flash_messages(
                success=success,
                error=error,
            ),
        },
        status_code=status.HTTP_200_OK,
    )


@router.get(
    "/{user_id}/reset-password",
    response_class=HTMLResponse,
    name="admin_user_reset_password",
)
def reset_password_page(
    user_id: int,
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
) -> HTMLResponse:
    """
    Display the password-reset form for a user.
    """
    try:
        user = UserService.require_user(
            db,
            user_id=user_id,
        )

    except UserNotFoundError:
        return _redirect_to_user_list(
            error="The requested user could not be found.",
        )

    return templates.TemplateResponse(
        request=request,
        name="admin/users/reset_password.html",
        context={
            "current_user": administrator,
            "user": user,
            "form": PasswordResetForm(),
            "csrf_token": request.cookies.get(
                _get_authenticated_csrf_cookie_name(),
                "",
            ),
            "flash_messages": [],
        },
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/{user_id}/reset-password",
    response_class=HTMLResponse,
    name="admin_user_reset_password_submit",
)
async def reset_password_submit(
    user_id: int,
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
    auth_session: ValidatedCSRFSession,
) -> HTMLResponse:
    """
    Reset a user's password and revoke all of their active sessions.
    """
    del auth_session

    try:
        user = UserService.require_user(
            db,
            user_id=user_id,
        )

    except UserNotFoundError:
        return _redirect_to_user_list(
            error="The requested user could not be found.",
        )

    form_data = await request.form()

    form = PasswordResetForm.from_form_data(
        form_data,
    )

    password_reset_request = form.validate()

    if password_reset_request is None:
        form.clear_passwords()

        return templates.TemplateResponse(
            request=request,
            name="admin/users/reset_password.html",
            context={
                "current_user": administrator,
                "user": user,
                "form": form,
                "csrf_token": _get_form_value(
                    form_data,
                    "csrf_token",
                )
                or "",
                "flash_messages": [],
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    try:
        UserService.reset_password_by_user_id(
            db,
            actor=administrator,
            user_id=user_id,
            new_password=password_reset_request.new_password,
        )

    except UserNotFoundError:
        return _redirect_to_user_list(
            error="The requested user could not be found.",
        )

    except UserPermissionError:
        return _redirect_to_user_list(
            error="You do not have permission to reset this password.",
        )

    return _redirect_to_user_list(
        success=f"The password for {user.username} was reset.",
    )


@router.post(
    "/{user_id}/activate",
    name="admin_user_activate",
)
def activate_user(
    user_id: int,
    db: DatabaseSession,
    administrator: AdministratorUser,
    auth_session: ValidatedCSRFSession,
) -> RedirectResponse:
    """
    Activate a user account.
    """
    del auth_session

    try:
        user = UserService.set_active_status(
            db,
            actor=administrator,
            user_id=user_id,
            is_active=True,
        )

    except UserNotFoundError:
        return _redirect_to_user_list(
            error="The requested user could not be found.",
        )

    except UserPermissionError:
        return _redirect_to_user_list(
            error="You do not have permission to activate this user.",
        )

    return _redirect_to_user_list(
        success=f"{user.username} was activated.",
    )


@router.post(
    "/{user_id}/deactivate",
    name="admin_user_deactivate",
)
def deactivate_user(
    user_id: int,
    db: DatabaseSession,
    administrator: AdministratorUser,
    auth_session: ValidatedCSRFSession,
) -> RedirectResponse:
    """
    Deactivate a user account and revoke all of their sessions.
    """
    del auth_session

    if user_id == administrator.id:
        return _redirect_to_user_list(
            error="You cannot deactivate your own account.",
        )

    try:
        user = UserService.set_active_status(
            db,
            actor=administrator,
            user_id=user_id,
            is_active=False,
        )

    except UserNotFoundError:
        return _redirect_to_user_list(
            error="The requested user could not be found.",
        )

    except UserPermissionError:
        return _redirect_to_user_list(
            error="You do not have permission to deactivate this user.",
        )

    return _redirect_to_user_list(
        success=f"{user.username} was deactivated.",
    )


def _redirect_to_user_list(
    *,
    success: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    query_parameters: dict[str, str] = {}

    if success:
        query_parameters["success"] = success

    if error:
        query_parameters["error"] = error

    url = "/admin/users"

    if query_parameters:
        url = f"{url}?{urlencode(query_parameters)}"

    return RedirectResponse(
        url=url,
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _build_flash_messages(
    *,
    success: str | None,
    error: str | None,
) -> list[dict[str, str | None]]:
    messages: list[dict[str, str | None]] = []

    if success:
        messages.append(
            {
                "category": "success",
                "title": "Success",
                "message": success,
            },
        )

    if error:
        messages.append(
            {
                "category": "error",
                "title": "Unable to complete request",
                "message": error,
            },
        )

    return messages


def _get_authenticated_csrf_cookie_name() -> str:
    """
    Return the authenticated CSRF cookie name.

    The application stores it alongside the session cookie using the
    `<session-cookie-name>_csrf` naming convention.
    """
    return f"{settings.session_cookie_name}_csrf"


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