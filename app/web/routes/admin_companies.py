from urllib.parse import urlencode

from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth.permissions import PermissionDeniedError
from app.core.config import settings
from app.repositories.user_repository import UserRepository
from app.services.company_membership_service import (
    CompanyMembershipAlreadyExistsError,
    CompanyMembershipNotFoundError,
    CompanyMembershipService,
    CompanyMembershipServiceError,
    CompanyMembershipUserNotFoundError,
    CompanyMembershipUserUnavailableError,
)
from app.services.company_service import (
    CompanyNameAlreadyExistsError,
    CompanyNotFoundError,
    CompanyService,
    CompanyServiceError,
)
from app.web.dependencies.auth import (
    AdministratorUser,
    DatabaseSession,
    get_client_ip_address,
    get_user_agent,
)
from app.web.dependencies.csrf import ValidatedCSRFSession
from app.web.forms.company import (
    CompanyForm,
    CompanyMembershipCreateForm,
    CompanyMembershipUpdateForm,
)
from app.web.templating import templates


router = APIRouter(
    prefix="/admin/companies",
    tags=[
        "admin companies",
    ],
)


@router.get(
    "",
    response_class=HTMLResponse,
    name="admin_companies",
)
def list_companies(
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
    success: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    """
    Display active and archived companies.

    Access is restricted to global administrators.
    """
    companies = CompanyService.list_companies_for_actor(
        db,
        actor=administrator,
        include_archived=True,
    )

    return templates.TemplateResponse(
        request=request,
        name="admin/companies/index.html",
        context={
            "current_user": administrator,
            "companies": companies,
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
    "/create",
    response_class=HTMLResponse,
    name="admin_company_create",
)
def create_company_page(
    request: Request,
    administrator: AdministratorUser,
) -> HTMLResponse:
    """
    Display the company creation form.
    """
    return templates.TemplateResponse(
        request=request,
        name="admin/companies/create.html",
        context={
            "current_user": administrator,
            "form": CompanyForm(),
            "csrf_token": _get_authenticated_csrf_token(
                request,
            ),
            "flash_messages": [],
        },
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/create",
    response_class=HTMLResponse,
    name="admin_company_create_submit",
)
async def create_company_submit(
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
    auth_session: ValidatedCSRFSession,
) -> HTMLResponse:
    """
    Validate and create a company.
    """
    del auth_session

    form_data = await request.form()

    form = CompanyForm.from_form_data(
        form_data,
    )

    company_create = form.validate_create()

    if company_create is None:
        return templates.TemplateResponse(
            request=request,
            name="admin/companies/create.html",
            context={
                "current_user": administrator,
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
        company = CompanyService.create_company(
            db,
            actor=administrator,
            company_create=company_create,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except CompanyNameAlreadyExistsError as exc:
        form.errors.add_field_error(
            "name",
            str(exc),
        )

        return templates.TemplateResponse(
            request=request,
            name="admin/companies/create.html",
            context={
                "current_user": administrator,
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

    except PermissionDeniedError:
        return _redirect_to_company_list(
            error="You do not have permission to create companies.",
        )

    return _redirect_to_company_detail(
        company_id=company.id,
        success=f"{company.name} was created.",
    )


@router.get(
    "/{company_id}",
    response_class=HTMLResponse,
    name="admin_company_detail",
)
def company_detail(
    company_id: int,
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
    success: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    """
    Display an administrator view of a company.
    """
    try:
        company = CompanyService.require_company(
            db,
            company_id=company_id,
        )

    except CompanyNotFoundError:
        return _redirect_to_company_list(
            error="The requested company could not be found.",
        )

    return templates.TemplateResponse(
        request=request,
        name="admin/companies/detail.html",
        context={
            "current_user": administrator,
            "company": company,
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
    "/{company_id}/edit",
    response_class=HTMLResponse,
    name="admin_company_edit",
)
def edit_company_page(
    company_id: int,
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
) -> HTMLResponse:
    """
    Display the company edit form.
    """
    try:
        company = CompanyService.require_company(
            db,
            company_id=company_id,
        )

    except CompanyNotFoundError:
        return _redirect_to_company_list(
            error="The requested company could not be found.",
        )

    return templates.TemplateResponse(
        request=request,
        name="admin/companies/edit.html",
        context={
            "current_user": administrator,
            "company": company,
            "form": CompanyForm.from_company(
                company,
            ),
            "csrf_token": _get_authenticated_csrf_token(
                request,
            ),
            "flash_messages": [],
        },
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/{company_id}/edit",
    response_class=HTMLResponse,
    name="admin_company_edit_submit",
)
async def edit_company_submit(
    company_id: int,
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
    auth_session: ValidatedCSRFSession,
) -> HTMLResponse:
    """
    Validate and update a company.
    """
    del auth_session

    try:
        company = CompanyService.require_company(
            db,
            company_id=company_id,
        )

    except CompanyNotFoundError:
        return _redirect_to_company_list(
            error="The requested company could not be found.",
        )

    form_data = await request.form()

    form = CompanyForm.from_form_data(
        form_data,
    )

    company_update = form.validate_update()

    if company_update is None:
        return templates.TemplateResponse(
            request=request,
            name="admin/companies/edit.html",
            context={
                "current_user": administrator,
                "company": company,
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
        updated_company = CompanyService.update_company(
            db,
            actor=administrator,
            company=company,
            company_update=company_update,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except CompanyNameAlreadyExistsError as exc:
        form.errors.add_field_error(
            "name",
            str(exc),
        )

        return templates.TemplateResponse(
            request=request,
            name="admin/companies/edit.html",
            context={
                "current_user": administrator,
                "company": company,
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

    except PermissionDeniedError:
        return _redirect_to_company_detail(
            company_id=company.id,
            error="You do not have permission to update this company.",
        )

    return _redirect_to_company_detail(
        company_id=updated_company.id,
        success=f"{updated_company.name} was updated.",
    )


@router.post(
    "/{company_id}/archive",
    name="admin_company_archive",
)
def archive_company(
    company_id: int,
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
    auth_session: ValidatedCSRFSession,
) -> RedirectResponse:
    """
    Archive a company.
    """
    del auth_session

    try:
        company = CompanyService.set_archived_status_by_id(
            db,
            actor=administrator,
            company_id=company_id,
            is_archived=True,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except CompanyNotFoundError:
        return _redirect_to_company_list(
            error="The requested company could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_company_detail(
            company_id=company_id,
            error="You do not have permission to archive this company.",
        )

    return _redirect_to_company_detail(
        company_id=company.id,
        success=f"{company.name} was archived.",
    )


@router.post(
    "/{company_id}/restore",
    name="admin_company_restore",
)
def restore_company(
    company_id: int,
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
    auth_session: ValidatedCSRFSession,
) -> RedirectResponse:
    """
    Restore an archived company.
    """
    del auth_session

    try:
        company = CompanyService.set_archived_status_by_id(
            db,
            actor=administrator,
            company_id=company_id,
            is_archived=False,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except CompanyNotFoundError:
        return _redirect_to_company_list(
            error="The requested company could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_company_detail(
            company_id=company_id,
            error="You do not have permission to restore this company.",
        )

    return _redirect_to_company_detail(
        company_id=company.id,
        success=f"{company.name} was restored.",
    )


@router.get(
    "/{company_id}/members",
    response_class=HTMLResponse,
    name="admin_company_members",
)
def company_members_page(
    company_id: int,
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
    success: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    """
    Display and manage company memberships.
    """
    try:
        company = CompanyService.require_company(
            db,
            company_id=company_id,
        )

        memberships = CompanyMembershipService.list_memberships(
            db,
            actor=administrator,
            company=company,
        )

    except CompanyNotFoundError:
        return _redirect_to_company_list(
            error="The requested company could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_company_detail(
            company_id=company_id,
            error=(
                "You do not have permission to manage this "
                "company's members."
            ),
        )

    available_users = _get_available_company_users(
        db,
        memberships=memberships,
    )

    return templates.TemplateResponse(
        request=request,
        name="admin/companies/members.html",
        context={
            "current_user": administrator,
            "company": company,
            "memberships": memberships,
            "available_users": available_users,
            "form": CompanyMembershipCreateForm(),
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


@router.post(
    "/{company_id}/members",
    response_class=HTMLResponse,
    name="admin_company_member_add",
)
async def add_company_member(
    company_id: int,
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
    auth_session: ValidatedCSRFSession,
) -> HTMLResponse:
    """
    Add an active user to a company.
    """
    del auth_session

    try:
        company = CompanyService.require_company(
            db,
            company_id=company_id,
        )

        memberships = CompanyMembershipService.list_memberships(
            db,
            actor=administrator,
            company=company,
        )

    except CompanyNotFoundError:
        return _redirect_to_company_list(
            error="The requested company could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_company_detail(
            company_id=company_id,
            error=(
                "You do not have permission to manage this "
                "company's members."
            ),
        )

    form_data = await request.form()

    form = CompanyMembershipCreateForm.from_form_data(
        form_data,
    )

    membership_create = form.validate()

    if membership_create is None:
        return _render_company_members_page(
            request=request,
            administrator=administrator,
            company=company,
            memberships=memberships,
            available_users=_get_available_company_users(
                db,
                memberships=memberships,
            ),
            form=form,
            csrf_token=(
                _get_form_value(
                    form_data,
                    "csrf_token",
                )
                or ""
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    try:
        membership = CompanyMembershipService.add_member(
            db,
            actor=administrator,
            company=company,
            membership_create=membership_create,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except (
        CompanyMembershipAlreadyExistsError,
        CompanyMembershipUserNotFoundError,
        CompanyMembershipUserUnavailableError,
        CompanyMembershipServiceError,
    ) as exc:
        form.errors.add_form_error(
            str(exc),
        )

        current_memberships = (
            CompanyMembershipService.list_memberships(
                db,
                actor=administrator,
                company=company,
            )
        )

        return _render_company_members_page(
            request=request,
            administrator=administrator,
            company=company,
            memberships=current_memberships,
            available_users=_get_available_company_users(
                db,
                memberships=current_memberships,
            ),
            form=form,
            csrf_token=(
                _get_form_value(
                    form_data,
                    "csrf_token",
                )
                or ""
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    except PermissionDeniedError:
        return _redirect_to_company_detail(
            company_id=company.id,
            error=(
                "You do not have permission to manage this "
                "company's members."
            ),
        )

    return _redirect_to_company_members(
        company_id=company.id,
        success=(
            f"{membership.user.display_name} was added to "
            f"{company.name}."
        ),
    )


@router.post(
    "/{company_id}/members/{user_id}/role",
    name="admin_company_member_role_update",
)
async def update_company_member_role(
    company_id: int,
    user_id: int,
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
    auth_session: ValidatedCSRFSession,
) -> RedirectResponse:
    """
    Change a company member's manager or employee role.
    """
    del auth_session

    form_data = await request.form()

    form = CompanyMembershipUpdateForm.from_form_data(
        form_data,
    )

    membership_update = form.validate()

    if membership_update is None:
        return _redirect_to_company_members(
            company_id=company_id,
            error="The selected company role is invalid.",
        )

    try:
        membership = (
            CompanyMembershipService.update_role_by_company_and_user(
                db,
                actor=administrator,
                company_id=company_id,
                user_id=user_id,
                membership_update=membership_update,
                ip_address=get_client_ip_address(
                    request,
                ),
                user_agent=get_user_agent(
                    request,
                ),
            )
        )

    except CompanyMembershipNotFoundError:
        return _redirect_to_company_members(
            company_id=company_id,
            error="The requested company membership could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_company_detail(
            company_id=company_id,
            error=(
                "You do not have permission to manage this "
                "company's members."
            ),
        )

    role_label = (
        "Manager"
        if membership.role == "manager"
        else "Employee"
    )

    return _redirect_to_company_members(
        company_id=company_id,
        success=(
            f"{membership.user.display_name}'s role was changed "
            f"to {role_label}."
        ),
    )


@router.post(
    "/{company_id}/members/{user_id}/remove",
    name="admin_company_member_remove",
)
def remove_company_member(
    company_id: int,
    user_id: int,
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
    auth_session: ValidatedCSRFSession,
) -> RedirectResponse:
    """
    Remove a user from a company.
    """
    del auth_session

    try:
        membership = CompanyMembershipService.require_membership(
            db,
            company_id=company_id,
            user_id=user_id,
        )

        display_name = membership.user.display_name

        CompanyMembershipService.remove_member(
            db,
            actor=administrator,
            membership=membership,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except CompanyMembershipNotFoundError:
        return _redirect_to_company_members(
            company_id=company_id,
            error="The requested company membership could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_company_detail(
            company_id=company_id,
            error=(
                "You do not have permission to manage this "
                "company's members."
            ),
        )

    return _redirect_to_company_members(
        company_id=company_id,
        success=f"{display_name} was removed from the company.",
    )


def _render_company_members_page(
    *,
    request: Request,
    administrator: object,
    company: object,
    memberships: list[object],
    available_users: list[object],
    form: CompanyMembershipCreateForm,
    csrf_token: str,
    status_code: int,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="admin/companies/members.html",
        context={
            "current_user": administrator,
            "company": company,
            "memberships": memberships,
            "available_users": available_users,
            "form": form,
            "csrf_token": csrf_token,
            "flash_messages": [],
        },
        status_code=status_code,
    )


def _get_available_company_users(
    db: DatabaseSession,
    *,
    memberships: list[object],
) -> list[object]:
    existing_user_ids = {
        membership.user_id
        for membership in memberships
    }

    users = UserRepository.list_all(
        db,
        include_inactive=False,
        include_anonymised=False,
    )

    return [
        user
        for user in users
        if user.id not in existing_user_ids
    ]


def _redirect_to_company_list(
    *,
    success: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    return _redirect_with_messages(
        url="/admin/companies",
        success=success,
        error=error,
    )


def _redirect_to_company_detail(
    *,
    company_id: int,
    success: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    return _redirect_with_messages(
        url=f"/admin/companies/{company_id}",
        success=success,
        error=error,
    )


def _redirect_to_company_members(
    *,
    company_id: int,
    success: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    return _redirect_with_messages(
        url=f"/admin/companies/{company_id}/members",
        success=success,
        error=error,
    )


def _redirect_with_messages(
    *,
    url: str,
    success: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    query_parameters: dict[str, str] = {}

    if success:
        query_parameters["success"] = success

    if error:
        query_parameters["error"] = error

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
    return f"{settings.session_cookie_name}_csrf"


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