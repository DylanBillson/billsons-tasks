from urllib.parse import urlencode

from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth.permissions import (
    PermissionDeniedError,
    PermissionService,
)
from app.core.config import settings
from app.models.company_membership import CompanyMembership
from app.repositories.company_membership_repository import (
    CompanyMembershipRepository,
)
from app.services.company_service import (
    CompanyNotFoundError,
    CompanyService,
)
from app.services.section_service import SectionService
from app.web.dependencies.auth import (
    CurrentUser,
    DatabaseSession,
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
    """
    Display companies available to the authenticated user.

    Administrators see every active company. Standard users see only
    companies where they have a company membership.
    """
    companies = CompanyService.list_companies_for_actor(
        db,
        actor=current_user,
        include_archived=False,
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
            CompanyMembershipRepository.get_by_company_and_user(
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
            "company_memberships": company_memberships,
            "accessible_section_counts": accessible_section_counts,
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
) -> HTMLResponse:
    """
    Display an accessible company and only those sections available to the
    authenticated user.

    Company managers do not automatically receive access to every section.
    Sections are included only when the user created them, was explicitly
    assigned to them, or is a global administrator.
    """
    try:
        company = CompanyService.get_accessible_company(
            db,
            actor=current_user,
            company_id=company_id,
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
        CompanyMembershipRepository.get_by_company_and_user(
            db,
            company_id=company.id,
            user_id=current_user.id,
        )
    )

    sections = SectionService.list_accessible_sections(
        db,
        actor=current_user,
        company_id=company.id,
        include_archived=False,
    )

    can_create_section = (
        PermissionService.can_create_section(
            db,
            actor=current_user,
            company=company,
        )
    )

    can_manage_company_memberships = (
        PermissionService.can_manage_company_memberships(
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
            "can_create_section": can_create_section,
            "can_manage_company_memberships": (
                can_manage_company_memberships
            ),
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
    "/{company_id}/members",
    name="company_members",
)
def company_members(
    company_id: int,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> RedirectResponse:
    """
    Reserve the company-members route used by the company detail template.

    The manager-facing membership page has not yet been created. Authorised
    users are returned to the company detail page with an explanatory message.
    """
    try:
        company = CompanyService.get_accessible_company(
            db,
            actor=current_user,
            company_id=company_id,
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

    if not PermissionService.can_manage_company_memberships(
        db,
        actor=current_user,
        company=company,
    ):
        return _redirect_to_company_detail(
            company_id=company.id,
            error=(
                "You do not have permission to manage "
                "this company's members."
            ),
        )

    return _redirect_to_company_detail(
        company_id=company.id,
        error=(
            "The manager-facing company membership "
            "page has not been created yet."
        ),
    )


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