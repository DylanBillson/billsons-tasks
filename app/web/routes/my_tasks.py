from urllib.parse import urlencode

from fastapi import APIRouter, Request, status
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
    Response,
)

from app.core.config import settings
from app.schemas.my_tasks import MyTasksFilterOptions
from app.services.task_service import (
    MyTasksFilterError,
    TaskService,
)
from app.web.dependencies.auth import (
    CurrentUser,
    DatabaseSession,
)
from app.web.forms.my_tasks import MyTasksFilterForm
from app.web.templating import templates


router = APIRouter(
    prefix="/my-tasks",
    tags=[
        "my-tasks",
    ],
)


@router.get(
    "",
    response_class=HTMLResponse,
    name="my_tasks",
)
def my_tasks(
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    success: str | None = None,
    error: str | None = None,
) -> Response:
    """
    Display tasks explicitly assigned to the current user.

    Filtering is performed entirely on the server. Company and section
    options are limited to locations containing tasks assigned to the user.
    """
    filter_form = MyTasksFilterForm.from_query_params(
        request.query_params,
    )

    filters = filter_form.validate()

    filter_validation_failed = (
        filters is None
    )

    response_status = status.HTTP_200_OK

    if filter_validation_failed:
        filters = MyTasksFilterOptions()

        response_status = (
            status.HTTP_422_UNPROCESSABLE_CONTENT
        )

    try:
        my_tasks_data = TaskService.get_my_tasks(
            db,
            actor=current_user,
            filters=filters,
            timezone_name=settings.default_timezone,
        )

    except MyTasksFilterError as exc:
        return _redirect_to_my_tasks(
            error=str(
                exc,
            ),
        )

    return templates.TemplateResponse(
        request=request,
        name="tasks/my_tasks.html",
        context={
            "current_user": current_user,
            "my_tasks": my_tasks_data,
            "tasks": my_tasks_data.tasks,
            "metrics": my_tasks_data.metrics,
            "companies": my_tasks_data.companies,
            "sections": my_tasks_data.sections,
            "filter_form": filter_form,
            "filter_validation_failed": (
                filter_validation_failed
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


def _redirect_to_my_tasks(
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

    url = "/my-tasks"

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
                "title": "Unable to display My Tasks",
                "message": error,
            },
        )

    return messages


def _get_authenticated_csrf_token(
    request: Request,
) -> str:
    return request.cookies.get(
        f"{settings.session_cookie_name}_csrf",
        "",
    )