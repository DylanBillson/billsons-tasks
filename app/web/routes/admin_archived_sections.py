from math import ceil
from urllib.parse import urlencode

from fastapi import APIRouter, Request, status
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
)

from app.auth.permissions import PermissionDeniedError
from app.core.config import settings
from app.services.company_service import CompanyService
from app.services.section_service import (
    SectionArchiveFilterError,
    SectionCompanyNotFoundError,
    SectionNotFoundError,
    SectionParentCompanyArchivedError,
    SectionService,
)
from app.web.dependencies.auth import (
    AdministratorUser,
    DatabaseSession,
)
from app.web.dependencies.csrf import (
    ValidatedCSRFSession,
)
from app.web.forms.archive_filters import ArchiveFilterForm
from app.web.templating import templates


router = APIRouter(
    prefix="/admin/archived-sections",
    tags=[
        "admin archived sections",
    ],
)


@router.get(
    "",
    response_class=HTMLResponse,
    name="admin_archived_sections",
)
def archived_sections(
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
    success: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    filter_form = ArchiveFilterForm.from_query_params(
        request.query_params,
    )

    company_id = _parse_optional_company_id(
        request.query_params.get(
            "company_id",
        ),
    )

    filter_form.company_id = (
        str(
            company_id,
        )
        if company_id is not None
        else ""
    )

    try:
        sections, total_items = (
            SectionService.list_archived_sections(
                db,
                actor=administrator,
                company_id=company_id,
                search=filter_form.search,
                page=filter_form.page,
                page_size=filter_form.page_size,
            )
        )

    except (
        SectionArchiveFilterError,
        SectionCompanyNotFoundError,
    ) as exc:
        return _redirect_to_archived_sections(
            error=str(
                exc,
            ),
        )

    total_pages = max(
        1,
        ceil(
            total_items
            / filter_form.page_size,
        ),
    )

    if (
        total_items > 0
        and filter_form.page > total_pages
    ):
        return RedirectResponse(
            url=_build_page_url(
                filter_form=filter_form,
                page=total_pages,
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    companies = CompanyService.list_companies_for_actor(
        db,
        actor=administrator,
        include_archived=True,
    )

    return templates.TemplateResponse(
        request=request,
        name="admin/archives/sections.html",
        context={
            "current_user": administrator,
            "sections": sections,
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
    "/{section_id}/restore",
    name="admin_archived_section_restore",
)
def restore_archived_section(
    section_id: int,
    db: DatabaseSession,
    administrator: AdministratorUser,
    auth_session: ValidatedCSRFSession,
) -> RedirectResponse:
    del auth_session

    try:
        section = SectionService.require_section(
            db,
            section_id=section_id,
        )

    except SectionNotFoundError:
        return _redirect_to_archived_sections(
            error=(
                "The requested archived section "
                "could not be found."
            ),
        )

    if not section.is_archived:
        return _redirect_to_archived_sections(
            error=(
                f"{section.name} is not archived."
            ),
        )

    try:
        SectionService.set_archived_status(
            db,
            actor=administrator,
            section=section,
            is_archived=False,
        )

    except SectionParentCompanyArchivedError as exc:
        return _redirect_to_archived_sections(
            error=str(
                exc,
            ),
        )

    except PermissionDeniedError:
        return _redirect_to_archived_sections(
            error=(
                "You do not have permission to "
                "restore this section."
            ),
        )

    return _redirect_to_archived_sections(
        success=(
            f"{section.name} was restored."
        ),
    )


def _parse_optional_company_id(
    value: object,
) -> int | None:
    if value is None:
        return None

    raw_value = str(
        value,
    ).strip()

    if not raw_value:
        return None

    try:
        company_id = int(
            raw_value,
        )

    except ValueError:
        return None

    if company_id < 1:
        return None

    return company_id


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

    company_id = getattr(
        filter_form,
        "company_id",
        "",
    )

    if company_id:
        query_parameters[
            "company_id"
        ] = company_id

    return (
        "/admin/archived-sections?"
        + urlencode(
            query_parameters,
        )
    )


def _redirect_to_archived_sections(
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

    url = "/admin/archived-sections"

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