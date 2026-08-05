from urllib.parse import urlencode

from fastapi import (
    APIRouter,
    Request,
    status,
)
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
    Response,
)

from app.auth.permissions import (
    PermissionDeniedError,
    PermissionService,
)
from app.core.config import settings
from app.models.company import Company
from app.models.company_membership import (
    CompanyMembership,
)
from app.models.user import User
from app.repositories.company_membership_repository import (
    CompanyMembershipRepository,
)
from app.services.company_membership_service import (
    CompanyMembershipAlreadyExistsError,
    CompanyMembershipNotFoundError,
    CompanyMembershipService,
    CompanyMembershipServiceError,
    CompanyMembershipUserNotFoundError,
    CompanyMembershipUserUnavailableError,
)
from app.services.company_service import (
    CompanyNotFoundError,
    CompanyService,
)
from app.services.section_service import (
    SectionService,
)
from app.services.user_service import UserService
from app.web.dependencies.auth import (
    CurrentUser,
    DatabaseSession,
    get_client_ip_address,
    get_user_agent,
)
from app.web.dependencies.csrf import (
    ValidatedCSRFSession,
)
from app.web.forms.company import (
    CompanyMembershipCreateForm,
    CompanyMembershipUpdateForm,
)
from app.web.templating import templates


router = APIRouter(
    prefix="/companies",
    tags=[
        "companies",
    ],
)


@router.get(
    "",
    response_class=HTMLResponse,
    name="companies",
)
def list_companies(
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    success: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    companies = (
        CompanyService.list_companies_for_actor(
            db,
            actor=current_user,
            include_archived=False,
        )
    )

    company_memberships: dict[
        int,
        CompanyMembership,
    ] = {}

    accessible_section_counts: dict[
        int,
        int,
    ] = {}

    for company in companies:
        membership = (
            CompanyMembershipRepository
            .get_by_company_and_user(
                db,
                company_id=company.id,
                user_id=current_user.id,
            )
        )

        if membership is not None:
            company_memberships[
                company.id
            ] = membership

        accessible_sections = (
            SectionService.list_accessible_sections(
                db,
                actor=current_user,
                company_id=company.id,
                include_archived=False,
            )
        )

        accessible_section_counts[
            company.id
        ] = len(
            accessible_sections,
        )

    return templates.TemplateResponse(
        request=request,
        name="companies/index.html",
        context={
            "current_user": current_user,
            "companies": companies,
            "company_memberships": (
                company_memberships
            ),
            "accessible_section_counts": (
                accessible_section_counts
            ),
            "csrf_token": (
                _get_authenticated_csrf_token(
                    request,
                )
            ),
            "flash_messages": (
                _build_flash_messages(
                    success=success,
                    error=error,
                )
            ),
        },
        status_code=status.HTTP_200_OK,
    )


@router.get(
    "/{company_id}/dashboard",
    response_class=HTMLResponse,
    name="company_dashboard",
)
def company_dashboard(
    company_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> Response:
    try:
        dashboard = (
            CompanyService.get_company_dashboard(
                db,
                actor=current_user,
                company_id=company_id,
            )
        )

    except CompanyNotFoundError:
        return _redirect_to_company_list(
            error=(
                "The requested company could not "
                "be found."
            ),
        )

    except PermissionDeniedError:
        return _redirect_to_company_list(
            error=(
                "You do not have access to the "
                "requested company."
            ),
        )

    company = dashboard[
        "company"
    ]

    sections = (
        SectionService.list_accessible_sections(
            db,
            actor=current_user,
            company_id=company.id,
            include_archived=False,
        )
    )

    return templates.TemplateResponse(
        request=request,
        name="companies/dashboard.html",
        context={
            "current_user": current_user,
            "company": company,
            "dashboard": dashboard,
            "metrics": dashboard[
                "metrics"
            ],
            "due_soon_tasks": dashboard[
                "due_soon_tasks"
            ],
            "recent_tasks": dashboard[
                "recent_tasks"
            ],
            "sections": sections,
            "csrf_token": (
                _get_authenticated_csrf_token(
                    request,
                )
            ),
            "flash_messages": [],
        },
        status_code=status.HTTP_200_OK,
    )


@router.get(
    "/{company_id}",
    response_class=HTMLResponse,
    name="company_detail",
)
def company_detail(
    company_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    success: str | None = None,
    error: str | None = None,
) -> Response:
    try:
        company = (
            CompanyService.get_accessible_company(
                db,
                actor=current_user,
                company_id=company_id,
            )
        )

    except CompanyNotFoundError:
        return _redirect_to_company_list(
            error=(
                "The requested company could not "
                "be found."
            ),
        )

    except PermissionDeniedError:
        return _redirect_to_company_list(
            error=(
                "You do not have access to the "
                "requested company."
            ),
        )

    membership = (
        CompanyMembershipRepository
        .get_by_company_and_user(
            db,
            company_id=company.id,
            user_id=current_user.id,
        )
    )

    sections = (
        SectionService.list_accessible_sections(
            db,
            actor=current_user,
            company_id=company.id,
            include_archived=False,
        )
    )

    can_create_section = (
        PermissionService.can_create_section(
            db,
            actor=current_user,
            company=company,
        )
    )

    can_manage_company_memberships = (
        PermissionService
        .can_manage_company_memberships(
            db,
            actor=current_user,
            company=company,
        )
    )

    return templates.TemplateResponse(
        request=request,
        name="companies/detail.html",
        context={
            "current_user": current_user,
            "company": company,
            "membership": membership,
            "sections": sections,
            "can_create_section": (
                can_create_section
            ),
            "can_manage_company_memberships": (
                can_manage_company_memberships
            ),
            "csrf_token": (
                _get_authenticated_csrf_token(
                    request,
                )
            ),
            "flash_messages": (
                _build_flash_messages(
                    success=success,
                    error=error,
                )
            ),
        },
        status_code=status.HTTP_200_OK,
    )


# -------------------------------------------------------------------------
# Company membership
# -------------------------------------------------------------------------


@router.get(
    "/{company_id}/members",
    response_class=HTMLResponse,
    name="company_members",
)
def company_members(
    company_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    success: str | None = None,
    error: str | None = None,
) -> Response:
    try:
        company = (
            CompanyService.require_company(
                db,
                company_id=company_id,
            )
        )

        PermissionService.require_company_membership_management(
            db,
            actor=current_user,
            company=company,
        )

    except CompanyNotFoundError:
        return _redirect_to_company_list(
            error=(
                "The requested company could not "
                "be found."
            ),
        )

    except PermissionDeniedError:
        return _redirect_to_company_detail(
            company_id=company_id,
            error=(
                "You do not have permission to manage "
                "this company's members."
            ),
        )

    return _render_company_members_page(
        request=request,
        db=db,
        current_user=current_user,
        company=company,
        form=CompanyMembershipCreateForm(),
        csrf_token=(
            _get_authenticated_csrf_token(
                request,
            )
        ),
        flash_messages=(
            _build_flash_messages(
                success=success,
                error=error,
            )
        ),
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/{company_id}/members",
    response_class=HTMLResponse,
    name="company_member_add",
)
async def add_company_member(
    company_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    auth_session: ValidatedCSRFSession,
) -> Response:
    del auth_session

    try:
        company = (
            CompanyService.require_company(
                db,
                company_id=company_id,
            )
        )

        PermissionService.require_company_membership_management(
            db,
            actor=current_user,
            company=company,
        )

    except CompanyNotFoundError:
        return _redirect_to_company_list(
            error=(
                "The requested company could not "
                "be found."
            ),
        )

    except PermissionDeniedError:
        return _redirect_to_company_detail(
            company_id=company_id,
            error=(
                "You do not have permission to manage "
                "this company's members."
            ),
        )

    form_data = await request.form()

    form = (
        CompanyMembershipCreateForm
        .from_form_data(
            form_data,
        )
    )

    membership_create = form.validate()

    csrf_token = (
        _get_form_value(
            form_data,
            "csrf_token",
        )
        or ""
    )

    if membership_create is None:
        return _render_company_members_page(
            request=request,
            db=db,
            current_user=current_user,
            company=company,
            form=form,
            csrf_token=csrf_token,
            flash_messages=[],
            status_code=(
                status.HTTP_422_UNPROCESSABLE_CONTENT
            ),
        )

    try:
        membership = (
            CompanyMembershipService.add_member(
                db,
                actor=current_user,
                company=company,
                membership_create=(
                    membership_create
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
        CompanyMembershipAlreadyExistsError,
        CompanyMembershipUserNotFoundError,
        CompanyMembershipUserUnavailableError,
        CompanyMembershipServiceError,
    ) as exc:
        form.errors.add_form_error(
            str(exc),
        )

        return _render_company_members_page(
            request=request,
            db=db,
            current_user=current_user,
            company=company,
            form=form,
            csrf_token=csrf_token,
            flash_messages=[],
            status_code=(
                status.HTTP_422_UNPROCESSABLE_CONTENT
            ),
        )

    except PermissionDeniedError:
        return _redirect_to_company_detail(
            company_id=company.id,
            error=(
                "You do not have permission to manage "
                "this company's members."
            ),
        )

    return _redirect_to_company_members(
        company_id=company.id,
        success=(
            f"{membership.user.display_name} "
            f"was added to {company.name}."
        ),
    )


@router.post(
    "/{company_id}/members/{user_id}/role",
    name="company_member_role_update",
)
async def update_company_member_role(
    company_id: int,
    user_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    auth_session: ValidatedCSRFSession,
) -> RedirectResponse:
    del auth_session

    form_data = await request.form()

    form = (
        CompanyMembershipUpdateForm
        .from_form_data(
            form_data,
        )
    )

    membership_update = form.validate()

    if membership_update is None:
        return _redirect_to_company_members(
            company_id=company_id,
            error=(
                "The selected company role "
                "was invalid."
            ),
        )

    try:
        membership = (
            CompanyMembershipService
            .update_role_by_company_and_user(
                db,
                actor=current_user,
                company_id=company_id,
                user_id=user_id,
                membership_update=(
                    membership_update
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

    except CompanyMembershipNotFoundError:
        return _redirect_to_company_members(
            company_id=company_id,
            error=(
                "The requested company membership "
                "could not be found."
            ),
        )

    except PermissionDeniedError:
        return _redirect_to_company_detail(
            company_id=company_id,
            error=(
                "You do not have permission to manage "
                "this company's members."
            ),
        )

    except CompanyMembershipServiceError as exc:
        return _redirect_to_company_members(
            company_id=company_id,
            error=str(exc),
        )

    return _redirect_to_company_members(
        company_id=company_id,
        success=(
            f"{membership.user.display_name}'s "
            f"company role was updated."
        ),
    )


@router.post(
    "/{company_id}/members/{user_id}/remove",
    name="company_member_remove",
)
def remove_company_member(
    company_id: int,
    user_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    auth_session: ValidatedCSRFSession,
) -> RedirectResponse:
    del auth_session

    try:
        membership = (
            CompanyMembershipService
            .require_membership(
                db,
                company_id=company_id,
                user_id=user_id,
            )
        )

        display_name = (
            membership.user.display_name
        )

        CompanyMembershipService.remove_member(
            db,
            actor=current_user,
            membership=membership,
            ip_address=(
                get_client_ip_address(
                    request,
                )
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except CompanyMembershipNotFoundError:
        return _redirect_to_company_members(
            company_id=company_id,
            error=(
                "The requested company membership "
                "could not be found."
            ),
        )

    except PermissionDeniedError:
        return _redirect_to_company_detail(
            company_id=company_id,
            error=(
                "You do not have permission to manage "
                "this company's members."
            ),
        )

    except CompanyMembershipServiceError as exc:
        return _redirect_to_company_members(
            company_id=company_id,
            error=str(exc),
        )

    return _redirect_to_company_members(
        company_id=company_id,
        success=(
            f"{display_name} was removed "
            "from the company."
        ),
    )


# -------------------------------------------------------------------------
# Membership rendering
# -------------------------------------------------------------------------


def _render_company_members_page(
    *,
    request: Request,
    db: DatabaseSession,
    current_user: User,
    company: Company,
    form: CompanyMembershipCreateForm,
    csrf_token: str,
    flash_messages: list[
        dict[
            str,
            str | None,
        ]
    ],
    status_code: int,
) -> HTMLResponse:
    memberships = (
        CompanyMembershipRepository.list_for_company(
            db,
            company_id=company.id,
        )
    )

    available_users = _get_available_company_users(
        db,
        memberships=memberships,
    )

    return templates.TemplateResponse(
        request=request,
        name="companies/members.html",
        context={
            "current_user": current_user,
            "company": company,
            "memberships": memberships,
            "available_users": available_users,
            "form": form,
            "csrf_token": csrf_token,
            "flash_messages": flash_messages,
        },
        status_code=status_code,
    )


def _get_available_company_users(
    db: DatabaseSession,
    *,
    memberships: list[
        CompanyMembership
    ],
) -> list[User]:
    assigned_user_ids = {
        membership.user_id
        for membership in memberships
    }

    users = UserService.list_users(
        db,
        include_inactive=False,
        include_anonymised=False,
    )

    return [
        user
        for user in users
        if (
            user.id
            not in assigned_user_ids
            and user.can_authenticate
        )
    ]


# -------------------------------------------------------------------------
# Redirects and shared helpers
# -------------------------------------------------------------------------


def _redirect_to_company_list(
    *,
    success: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    return _redirect_with_messages(
        url="/companies",
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
        url=f"/companies/{company_id}",
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
        url=f"/companies/{company_id}/members",
        success=success,
        error=error,
    )


def _redirect_with_messages(
    *,
    url: str,
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