from urllib.parse import urlencode

from fastapi import APIRouter, Request, status
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
    Response,
)

from app.core.config import settings
from app.schemas.audit_log import AuditLogFilterOptions
from app.services.audit_service import (
    AuditLogFilterError,
    AuditLogNotFoundError,
    AuditService,
)
from app.services.user_service import UserService
from app.web.dependencies.auth import (
    AdministratorUser,
    DatabaseSession,
)
from app.web.forms.audit_log import AuditLogFilterForm
from app.web.templating import templates


router = APIRouter(
    prefix="/admin/audit",
    tags=[
        "admin audit",
    ],
)


@router.get(
    "",
    response_class=HTMLResponse,
    name="admin_audit",
)
def audit_log_index(
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
) -> Response:
    filter_form = AuditLogFilterForm.from_query_params(
        request.query_params,
    )

    filters = filter_form.validate(
        timezone_name=settings.default_timezone,
    )

    filter_validation_failed = (
        filters is None
    )

    response_status = status.HTTP_200_OK

    if filters is None:
        filters = AuditLogFilterOptions()

        response_status = (
            status.HTTP_422_UNPROCESSABLE_CONTENT
        )

    try:
        audit_page = AuditService.get_log_page(
            db,
            actor=administrator,
            filters=filters,
        )

        filter_choices = (
            AuditService.get_filter_choices(
                db,
                actor=administrator,
            )
        )

    except AuditLogFilterError as exc:
        filter_form.errors.add_form_error(
            str(
                exc,
            ),
        )

        filter_validation_failed = True
        response_status = (
            status.HTTP_422_UNPROCESSABLE_CONTENT
        )

        fallback_filters = AuditLogFilterOptions()

        audit_page = AuditService.get_log_page(
            db,
            actor=administrator,
            filters=fallback_filters,
        )

        filter_choices = (
            AuditService.get_filter_choices(
                db,
                actor=administrator,
            )
        )

    users = UserService.list_users(
        db,
        include_inactive=True,
        include_anonymised=True,
    )

    previous_page_url = None
    next_page_url = None

    if audit_page.current_page > 1:
        previous_page_url = _build_audit_page_url(
            filter_form=filter_form,
            page=audit_page.current_page - 1,
        )

    if (
        audit_page.current_page
        < audit_page.total_pages
    ):
        next_page_url = _build_audit_page_url(
            filter_form=filter_form,
            page=audit_page.current_page + 1,
        )

    return templates.TemplateResponse(
        request=request,
        name="admin/audit/index.html",
        context={
            "current_user": administrator,
            "audit_page": audit_page,
            "audit_logs": audit_page.logs,
            "users": users,
            "actions": filter_choices.actions,
            "entity_types": (
                filter_choices.entity_types
            ),
            "filter_form": filter_form,
            "filter_validation_failed": (
                filter_validation_failed
            ),
            "previous_page_url": (
                previous_page_url
            ),
            "next_page_url": next_page_url,
            "flash_messages": [],
        },
        status_code=response_status,
    )


@router.get(
    "/{audit_log_id}",
    response_class=HTMLResponse,
    name="admin_audit_detail",
)
def audit_log_detail(
    audit_log_id: int,
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
) -> Response:
    try:
        audit_log = AuditService.get_log_detail(
            db,
            actor=administrator,
            audit_log_id=audit_log_id,
        )

    except AuditLogNotFoundError:
        return RedirectResponse(
            url=(
                "/admin/audit?"
                + urlencode(
                    {
                        "error": (
                            "The requested audit entry "
                            "could not be found."
                        ),
                    },
                )
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return templates.TemplateResponse(
        request=request,
        name="admin/audit/detail.html",
        context={
            "current_user": administrator,
            "audit_log": audit_log,
            "flash_messages": [],
        },
        status_code=status.HTTP_200_OK,
    )


def _build_audit_page_url(
    *,
    filter_form: AuditLogFilterForm,
    page: int,
) -> str:
    query_parameters: dict[str, str] = {
        "page": str(
            page,
        ),
        "page_size": filter_form.page_size,
    }

    for field_name in (
        "search",
        "user_id",
        "action",
        "entity_type",
        "entity_id",
        "created_from",
        "created_to",
    ):
        value = getattr(
            filter_form,
            field_name,
        )

        if value:
            query_parameters[
                field_name
            ] = value

    return (
        "/admin/audit?"
        + urlencode(
            query_parameters,
        )
    )