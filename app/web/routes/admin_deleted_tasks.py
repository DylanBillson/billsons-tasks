from urllib.parse import urlencode

from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.config import settings
from app.repositories.task_repository import TaskRepository
from app.services.task_service import (
    TaskNotDeletedError,
    TaskNotFoundError,
    TaskService,
)
from app.auth.permissions import PermissionDeniedError
from app.web.dependencies.auth import (
    AdministratorUser,
    DatabaseSession,
    get_client_ip_address,
    get_user_agent,
)
from app.web.dependencies.csrf import ValidatedCSRFSession
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
    page: int = 1,
) -> HTMLResponse:
    resolved_page = max(
        page,
        1,
    )

    per_page = 100

    tasks = TaskRepository.list_all_deleted(
        db,
        limit=per_page + 1,
        offset=(
            resolved_page - 1
        )
        * per_page,
    )

    has_next_page = len(
        tasks,
    ) > per_page

    tasks = tasks[
        :per_page
    ]

    return templates.TemplateResponse(
        request=request,
        name="tasks/deleted.html",
        context={
            "current_user": administrator,
            "tasks": tasks,
            "page": resolved_page,
            "has_previous_page": resolved_page > 1,
            "has_next_page": has_next_page,
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
            error="The requested task could not be found.",
        )

    except TaskNotDeletedError as exc:
        return _redirect_to_deleted_tasks(
            error=str(exc),
        )

    except PermissionDeniedError:
        return _redirect_to_deleted_tasks(
            error=(
                "You do not have permission to restore "
                "this task."
            ),
        )

    return _redirect_to_deleted_tasks(
        success=f"{task.title} was restored.",
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
            error="The requested task could not be found.",
        )

    except TaskNotDeletedError as exc:
        return _redirect_to_deleted_tasks(
            error=str(exc),
        )

    except PermissionDeniedError:
        return _redirect_to_deleted_tasks(
            error=(
                "You do not have permission to permanently "
                "delete this task."
            ),
        )

    return _redirect_to_deleted_tasks(
        success=f"{task_title} was permanently deleted.",
    )


def _redirect_to_deleted_tasks(
    *,
    success: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    query: dict[str, str] = {}

    if success:
        query["success"] = success

    if error:
        query["error"] = error

    url = "/admin/deleted-tasks"

    if query:
        url = f"{url}?{urlencode(query)}"

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


def _get_authenticated_csrf_token(
    request: Request,
) -> str:
    return request.cookies.get(
        f"{settings.session_cookie_name}_csrf",
        "",
    )