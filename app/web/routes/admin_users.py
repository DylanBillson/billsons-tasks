from urllib.parse import urlencode

from fastapi import APIRouter, Request, status
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
    Response,
)

from app.core.config import settings
from app.services.user_service import (
    AnonymisedUserStatusError,
    UserNotFoundError,
    UserPermissionError,
    UserSelfDeactivationError,
    UserService,
    UserServiceError,
)
from app.web.dependencies.auth import (
    AdministratorUser,
    DatabaseSession,
    get_client_ip_address,
    get_user_agent,
)
from app.web.dependencies.csrf import ValidatedCSRFSession
from app.web.forms.admin_user import (
    UserAnonymisationForm,
    UserDeactivationForm,
)
from app.web.forms.auth import PasswordResetForm
from app.web.templating import templates
from app.services.anonymisation_service import (
    AnonymisationConfirmationError,
    AnonymisationPermissionError,
    AnonymisationService,
    AnonymisationServiceError,
    AnonymisationUserNotFoundError,
)

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
    users = UserService.list_users(
        db,
        include_inactive=True,
        include_anonymised=True,
    )

    return templates.TemplateResponse(
        request=request,
        name="admin/users/index.html",
        context={
            "current_user": administrator,
            "users": users,
            "csrf_token": _get_authenticated_csrf_token(
                request,
            ),
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
) -> Response:
    try:
        user = UserService.require_user(
            db,
            user_id=user_id,
        )

    except UserNotFoundError:
        return _redirect_to_user_list(
            error=(
                "The requested user could not be found."
            ),
        )

    return templates.TemplateResponse(
        request=request,
        name="admin/users/reset_password.html",
        context={
            "current_user": administrator,
            "user": user,
            "form": PasswordResetForm(),
            "csrf_token": _get_authenticated_csrf_token(
                request,
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
) -> Response:
    del auth_session

    try:
        user = UserService.require_user(
            db,
            user_id=user_id,
        )

    except UserNotFoundError:
        return _redirect_to_user_list(
            error=(
                "The requested user could not be found."
            ),
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
                "csrf_token": (
                    _get_form_value(
                        form_data,
                        "csrf_token",
                    )
                    or ""
                ),
                "flash_messages": [],
            },
            status_code=(
                status.HTTP_422_UNPROCESSABLE_CONTENT
            ),
        )

    try:
        UserService.reset_password_by_user_id(
            db,
            actor=administrator,
            user_id=user_id,
            new_password=(
                password_reset_request.new_password
            ),
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except UserNotFoundError:
        return _redirect_to_user_list(
            error=(
                "The requested user could not be found."
            ),
        )

    except UserPermissionError:
        return _redirect_to_user_list(
            error=(
                "You do not have permission to reset "
                "this password."
            ),
        )

    except UserServiceError as exc:
        form.errors.add_form_error(
            str(
                exc,
            ),
        )

        form.clear_passwords()

        return templates.TemplateResponse(
            request=request,
            name="admin/users/reset_password.html",
            context={
                "current_user": administrator,
                "user": user,
                "form": form,
                "csrf_token": (
                    _get_form_value(
                        form_data,
                        "csrf_token",
                    )
                    or ""
                ),
                "flash_messages": [],
            },
            status_code=(
                status.HTTP_422_UNPROCESSABLE_CONTENT
            ),
        )

    return _redirect_to_user_list(
        success=(
            f"The password for {user.username} was reset."
        ),
    )


@router.post(
    "/{user_id}/activate",
    name="admin_user_activate",
)
def activate_user(
    user_id: int,
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
    auth_session: ValidatedCSRFSession,
) -> RedirectResponse:
    del auth_session

    try:
        user = UserService.require_user(
            db,
            user_id=user_id,
        )

        UserService.set_active_status(
            db,
            acting_user=administrator,
            target_user=user,
            is_active=True,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except UserNotFoundError:
        return _redirect_to_user_list(
            error=(
                "The requested user could not be found."
            ),
        )

    except UserPermissionError:
        return _redirect_to_user_list(
            error=(
                "You do not have permission to activate "
                "this user."
            ),
        )

    except UserServiceError as exc:
        return _redirect_to_user_list(
            error=str(
                exc,
            ),
        )

    return _redirect_to_user_list(
        success=(
            f"{user.username} was activated."
        ),
    )


@router.get(
    "/{user_id}/deactivate",
    response_class=HTMLResponse,
    name="admin_user_deactivate",
)
def deactivate_user_page(
    user_id: int,
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
) -> Response:
    try:
        user = UserService.require_user(
            db,
            user_id=user_id,
        )

    except UserNotFoundError:
        return _redirect_to_user_list(
            error=(
                "The requested user could not be found."
            ),
        )

    if user.is_anonymised:
        return _redirect_to_user_list(
            error=(
                "An anonymised user cannot be deactivated."
            ),
        )

    if not user.is_active:
        return _redirect_to_user_list(
            error=(
                f"{user.username} is already inactive."
            ),
        )

    if user.id == administrator.id:
        return _redirect_to_user_list(
            error=(
                "You cannot deactivate your own account."
            ),
        )

    return templates.TemplateResponse(
        request=request,
        name="admin/users/deactivate.html",
        context={
            "current_user": administrator,
            "user": user,
            "form": UserDeactivationForm(),
            "csrf_token": _get_authenticated_csrf_token(
                request,
            ),
            "flash_messages": [],
        },
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/{user_id}/deactivate",
    response_class=HTMLResponse,
    name="admin_user_deactivate_submit",
)
async def deactivate_user_submit(
    user_id: int,
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
    auth_session: ValidatedCSRFSession,
) -> Response:
    del auth_session

    try:
        user = UserService.require_user(
            db,
            user_id=user_id,
        )

    except UserNotFoundError:
        return _redirect_to_user_list(
            error=(
                "The requested user could not be found."
            ),
        )

    form_data = await request.form()

    form = UserDeactivationForm.from_form_data(
        form_data,
    )

    if not form.validate():
        return templates.TemplateResponse(
            request=request,
            name="admin/users/deactivate.html",
            context={
                "current_user": administrator,
                "user": user,
                "form": form,
                "csrf_token": (
                    _get_form_value(
                        form_data,
                        "csrf_token",
                    )
                    or ""
                ),
                "flash_messages": [],
            },
            status_code=(
                status.HTTP_422_UNPROCESSABLE_CONTENT
            ),
        )

    try:
        result = UserService.set_active_status(
            db,
            acting_user=administrator,
            target_user=user,
            is_active=False,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except UserSelfDeactivationError as exc:
        return _redirect_to_user_list(
            error=str(
                exc,
            ),
        )

    except AnonymisedUserStatusError as exc:
        return _redirect_to_user_list(
            error=str(
                exc,
            ),
        )

    except UserPermissionError:
        return _redirect_to_user_list(
            error=(
                "You do not have permission to deactivate "
                "this user."
            ),
        )

    return _redirect_to_user_list(
        success=(
            f"{user.username} was deactivated. "
            f"{result.revoked_session_count} active "
            "session"
            f"{'' if result.revoked_session_count == 1 else 's'} "
            "were revoked."
        ),
    )

@router.get(
    "/{user_id}/anonymise",
    response_class=HTMLResponse,
    name="admin_user_anonymise",
)
def anonymise_user_page(
    user_id: int,
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
) -> Response:
    try:
        preview = AnonymisationService.get_preview(
            db,
            actor=administrator,
            user_id=user_id,
        )

        user = UserService.require_user(
            db,
            user_id=user_id,
        )

    except (
        AnonymisationUserNotFoundError,
        UserNotFoundError,
    ):
        return _redirect_to_user_list(
            error=(
                "The requested user could not be found."
            ),
        )

    except AnonymisationServiceError as exc:
        return _redirect_to_user_list(
            error=str(
                exc,
            ),
        )

    return templates.TemplateResponse(
        request=request,
        name="admin/users/anonymise.html",
        context={
            "current_user": administrator,
            "user": user,
            "preview": preview,
            "form": UserAnonymisationForm(),
            "csrf_token": (
                _get_authenticated_csrf_token(
                    request,
                )
            ),
            "flash_messages": [],
        },
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/{user_id}/anonymise",
    response_class=HTMLResponse,
    name="admin_user_anonymise_submit",
)
async def anonymise_user_submit(
    user_id: int,
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
    auth_session: ValidatedCSRFSession,
) -> Response:
    del auth_session

    try:
        user = UserService.require_user(
            db,
            user_id=user_id,
        )

        preview = AnonymisationService.get_preview(
            db,
            actor=administrator,
            user_id=user_id,
        )

    except (
        AnonymisationUserNotFoundError,
        UserNotFoundError,
    ):
        return _redirect_to_user_list(
            error=(
                "The requested user could not be found."
            ),
        )

    except AnonymisationServiceError as exc:
        return _redirect_to_user_list(
            error=str(
                exc,
            ),
        )

    form_data = await request.form()

    form = UserAnonymisationForm.from_form_data(
        form_data,
    )

    if not form.validate():
        return templates.TemplateResponse(
            request=request,
            name="admin/users/anonymise.html",
            context={
                "current_user": administrator,
                "user": user,
                "preview": preview,
                "form": form,
                "csrf_token": (
                    _get_form_value(
                        form_data,
                        "csrf_token",
                    )
                    or ""
                ),
                "flash_messages": [],
            },
            status_code=(
                status.HTTP_422_UNPROCESSABLE_CONTENT
            ),
        )

    try:
        result = (
            AnonymisationService.anonymise_user(
                db,
                actor=administrator,
                user_id=user_id,
                confirmation_phrase=(
                    form.confirmation_phrase
                ),
                ip_address=(
                    get_client_ip_address(
                        request,
                    )
                ),
                user_agent=get_user_agent(
                    request,
                ),
            )
        )

    except (
        AnonymisationConfirmationError,
        AnonymisationPermissionError,
        AnonymisationServiceError,
    ) as exc:
        return _redirect_to_user_list(
            error=str(
                exc,
            ),
        )

    return _redirect_to_user_list(
        success=(
            f"{result.anonymised_display_name} "
            "was anonymised permanently."
        ),
    )

def _redirect_to_user_list(
    *,
    success: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    query_parameters: dict[
        str,
        str,
    ] = {}

    if success:
        query_parameters[
            "success"
        ] = success

    if error:
        query_parameters[
            "error"
        ] = error

    url = "/admin/users"

    if query_parameters:
        url = (
            f"{url}?"
            f"{urlencode(query_parameters)}"
        )

    return RedirectResponse(
        url=url,
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _build_flash_messages(
    *,
    success: str | None,
    error: str | None,
) -> list[
    dict[
        str,
        str | None,
    ]
]:
    messages: list[
        dict[
            str,
            str | None,
        ]
    ] = []

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
                "title": (
                    "Unable to complete request"
                ),
                "message": error,
            },
        )

    return messages


def _get_authenticated_csrf_cookie_name() -> str:
    return (
        f"{settings.session_cookie_name}_csrf"
    )


def _get_authenticated_csrf_token(
    request: Request,
) -> str:
    return request.cookies.get(
        _get_authenticated_csrf_cookie_name(),
        "",
    )


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