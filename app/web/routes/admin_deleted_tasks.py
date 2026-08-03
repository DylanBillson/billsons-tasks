from math import ceil
from urllib.parse import urlencode

from fastapi import APIRouter, Request, status
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
)

from app.auth.permissions import PermissionDeniedError
from app.core.config import settings
from app.repositories.company_repository import CompanyRepository
from app.repositories.section_repository import SectionRepository
from app.repositories.user_repository import UserRepository
from app.services.task_service import (
    DeletedTaskFilterError,
    TaskNotDeletedError,
    TaskNotFoundError,
    TaskService,
)
from app.web.dependencies.auth import (
    AdministratorUser,
    DatabaseSession,
    get_client_ip_address,
    get_user_agent,
)
from app.web.dependencies.csrf import ValidatedCSRFSession
from app.web.forms.deleted_task_filters import (
    DeletedTaskFilterForm,
    DeletedTaskFilters,
)
from app.web.templating import templates


router = APIRouter(
    prefix="/admin/deleted-tasks",
    tags=[
        "admin deleted tasks",
    ],
)


@router.get(
    "",
    response_class=HTMLResponse,
    name="admin_deleted_tasks",
)
def deleted_tasks_page(
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
    success: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    filter_form = DeletedTaskFilterForm.from_query_params(
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
        filters = DeletedTaskFilters()

        response_status = (
            status.HTTP_422_UNPROCESSABLE_CONTENT
        )

    try:
        tasks, total_items = (
            TaskService.list_deleted_tasks(
                db,
                actor=administrator,
                search=filters.search,
                company_id=filters.company_id,
                section_id=filters.section_id,
                deleted_by_user_id=(
                    filters.deleted_by_user_id
                ),
                deleted_from=filters.deleted_from,
                deleted_to=filters.deleted_to,
                page=filters.page,
                page_size=filters.page_size,
            )
        )

    except DeletedTaskFilterError as exc:
        return _redirect_to_deleted_tasks(
            error=str(
                exc,
            ),
        )

    total_pages = max(
        1,
        ceil(
            total_items
            / filters.page_size,
        ),
    )

    if (
        total_items > 0
        and filters.page > total_pages
    ):
        return RedirectResponse(
            url=_build_page_url(
                filter_form=filter_form,
                page=total_pages,
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    companies = CompanyRepository.list_all(
        db,
        include_archived=True,
    )

    sections = []

    for company in companies:
        sections.extend(
            SectionRepository.list_for_company(
                db,
                company_id=company.id,
                include_archived=True,
            ),
        )

    users = UserRepository.list_all(
        db,
        include_inactive=True,
        include_anonymised=True,
    )

    return templates.TemplateResponse(
        request=request,
        name="tasks/deleted.html",
        context={
            "current_user": administrator,
            "tasks": tasks,
            "companies": companies,
            "sections": sections,
            "users": users,
            "filter_form": filter_form,
            "filter_validation_failed": (
                filter_validation_failed
            ),
            "total_items": total_items,
            "total_pages": total_pages,
            "current_page": filters.page,
            "previous_page_url": (
                _build_page_url(
                    filter_form=filter_form,
                    page=filters.page - 1,
                )
                if filters.page > 1
                else None
            ),
            "next_page_url": (
                _build_page_url(
                    filter_form=filter_form,
                    page=filters.page + 1,
                )
                if filters.page < total_pages
                else None
            ),
            "csrf_token": _get_authenticated_csrf_token(
                request,
            ),
            "flash_messages": _build_flash_messages(
                success=success,
                error=error,
            ),
        },
        status_code=response_status,
    )


@router.post(
    "/{task_id}/restore",
    name="admin_deleted_task_restore",
)
def restore_deleted_task(
    task_id: int,
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
    auth_session: ValidatedCSRFSession,
) -> RedirectResponse:
    del auth_session

    try:
        task = TaskService.require_task(
            db,
            task_id=task_id,
        )

        task = TaskService.restore_task(
            db,
            actor=administrator,
            task=task,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except TaskNotFoundError:
        return _redirect_to_deleted_tasks(
            error=(
                "The requested task could not be found."
            ),
        )

    except TaskNotDeletedError as exc:
        return _redirect_to_deleted_tasks(
            error=str(
                exc,
            ),
        )

    except PermissionDeniedError:
        return _redirect_to_deleted_tasks(
            error=(
                "You do not have permission to restore "
                "this task."
            ),
        )

    return _redirect_to_deleted_tasks(
        success=(
            f"{task.title} was restored."
        ),
    )


@router.post(
    "/{task_id}/delete-permanently",
    name="admin_deleted_task_permanent_delete",
)
def permanently_delete_task(
    task_id: int,
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
    auth_session: ValidatedCSRFSession,
) -> RedirectResponse:
    del auth_session

    try:
        task = TaskService.require_task(
            db,
            task_id=task_id,
        )

        task_title = task.title

        TaskService.permanently_delete_task(
            db,
            actor=administrator,
            task=task,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except TaskNotFoundError:
        return _redirect_to_deleted_tasks(
            error=(
                "The requested task could not be found."
            ),
        )

    except TaskNotDeletedError as exc:
        return _redirect_to_deleted_tasks(
            error=str(
                exc,
            ),
        )

    except PermissionDeniedError:
        return _redirect_to_deleted_tasks(
            error=(
                "You do not have permission to permanently "
                "delete this task."
            ),
        )

    return _redirect_to_deleted_tasks(
        success=(
            f"{task_title} was permanently deleted."
        ),
    )


def _build_page_url(
    *,
    filter_form: DeletedTaskFilterForm,
    page: int,
) -> str:
    query: dict[str, str] = {
        "page": str(
            page,
        ),
        "page_size": filter_form.page_size,
    }

    for key in (
        "search",
        "company_id",
        "section_id",
        "deleted_by_user_id",
        "deleted_from",
        "deleted_to",
    ):
        value = getattr(
            filter_form,
            key,
        )

        if value:
            query[
                key
            ] = value

    return (
        "/admin/deleted-tasks?"
        + urlencode(
            query,
        )
    )


def _redirect_to_deleted_tasks(
    *,
    success: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    query: dict[str, str] = {}

    if success:
        query[
            "success"
        ] = success

    if error:
        query[
            "error"
        ] = error

    url = "/admin/deleted-tasks"

    if query:
        url = (
            f"{url}?"
            f"{urlencode(query)}"
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