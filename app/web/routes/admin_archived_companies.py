from math import ceil
from urllib.parse import urlencode

from fastapi import APIRouter, Request, status
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
)

from app.auth.permissions import PermissionDeniedError
from app.core.config import settings
from app.services.company_service import (
    CompanyNotFoundError,
    CompanyService,
)
from app.web.dependencies.auth import (
    AdministratorUser,
    DatabaseSession,
)
from app.web.dependencies.csrf import (
    ValidatedCSRFSession,
)
from app.web.forms.archive_filters import (
    ArchiveFilterForm,
)
from app.web.templating import templates


router = APIRouter(
    prefix="/admin/archived-companies",
    tags=[
        "admin archived companies",
    ],
)


@router.get(
    "",
    response_class=HTMLResponse,
    name="admin_archived_companies",
)
def archived_companies(
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
    success: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    filter_form = ArchiveFilterForm.from_query_params(
        request.query_params,
    )

    all_companies = CompanyService.list_companies_for_actor(
        db,
        actor=administrator,
        include_archived=True,
    )

    archived = [
        company
        for company in all_companies
        if company.is_archived
    ]

    if filter_form.search:
        search = filter_form.search.casefold()

        archived = [
            company
            for company in archived
            if (
                search
                in company.name.casefold()
                or (
                    company.description is not None
                    and search
                    in company.description.casefold()
                )
            )
        ]

    total_items = len(
        archived,
    )

    total_pages = max(
        1,
        ceil(
            total_items
            / filter_form.page_size,
        ),
    )

    if filter_form.page > total_pages:
        filter_form.page = total_pages

    start_index = (
        filter_form.page - 1
    ) * filter_form.page_size

    end_index = (
        start_index
        + filter_form.page_size
    )

    companies = archived[
        start_index:end_index
    ]

    return templates.TemplateResponse(
        request=request,
        name="admin/archives/companies.html",
        context={
            "current_user": administrator,
            "companies": companies,
            "filter_form": filter_form,
            "total_items": total_items,
            "total_pages": total_pages,
            "current_page": filter_form.page,
            "previous_page_url": (
                _build_page_url(
                    filter_form=filter_form,
                    page=filter_form.page - 1,
                )
                if filter_form.page > 1
                else None
            ),
            "next_page_url": (
                _build_page_url(
                    filter_form=filter_form,
                    page=filter_form.page + 1,
                )
                if filter_form.page < total_pages
                else None
            ),
            "csrf_token": (
                _get_authenticated_csrf_token(
                    request,
                )
            ),
            "flash_messages": _build_flash_messages(
                success=success,
                error=error,
            ),
        },
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/{company_id}/restore",
    name="admin_archived_company_restore",
)
def restore_archived_company(
    company_id: int,
    db: DatabaseSession,
    administrator: AdministratorUser,
    auth_session: ValidatedCSRFSession,
) -> RedirectResponse:
    del auth_session

    try:
        company = CompanyService.require_company(
            db,
            company_id=company_id,
        )

    except CompanyNotFoundError:
        return _redirect_to_archived_companies(
            error=(
                "The requested archived company "
                "could not be found."
            ),
        )

    if not company.is_archived:
        return _redirect_to_archived_companies(
            error=(
                f"{company.name} is not archived."
            ),
        )

    try:
        CompanyService.set_archived_status(
            db,
            actor=administrator,
            company=company,
            is_archived=False,
        )

    except PermissionDeniedError:
        return _redirect_to_archived_companies(
            error=(
                "You do not have permission to "
                "restore this company."
            ),
        )

    return _redirect_to_archived_companies(
        success=(
            f"{company.name} was restored."
        ),
    )


def _build_page_url(
    *,
    filter_form: ArchiveFilterForm,
    page: int,
) -> str:
    query_parameters = {
        "page": str(
            page,
        ),
        "page_size": str(
            filter_form.page_size,
        ),
    }

    if filter_form.search:
        query_parameters[
            "search"
        ] = filter_form.search

    return (
        "/admin/archived-companies?"
        + urlencode(
            query_parameters,
        )
    )


def _redirect_to_archived_companies(
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

    url = "/admin/archived-companies"

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


def _get_authenticated_csrf_token(
    request: Request,
) -> str:
    return request.cookies.get(
        (
            f"{settings.session_cookie_name}"
            "_csrf"
        ),
        "",
    )