from urllib.parse import urlencode

from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth.permissions import PermissionDeniedError
from app.services.comment_service import (
    CommentAlreadyDeletedError,
    CommentNotFoundError,
    CommentPermissionError,
    CommentService,
    CommentServiceError,
)
from app.services.task_service import (
    TaskNotFoundError,
    TaskService,
)
from app.web.dependencies.auth import (
    CurrentUser,
    DatabaseSession,
    get_client_ip_address,
    get_user_agent,
)
from app.web.dependencies.csrf import ValidatedCSRFSession
from app.web.forms.comment import TaskCommentForm


router = APIRouter(
    tags=[
        "task comments",
    ],
)


@router.post(
    "/tasks/{task_id}/comments",
    response_class=HTMLResponse,
    name="task_comment_add",
)
async def add_task_comment(
    task_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    auth_session: ValidatedCSRFSession,
) -> RedirectResponse:
    del auth_session

    try:
        task = TaskService.require_task(
            db,
            task_id=task_id,
        )

    except TaskNotFoundError:
        return _redirect(
            path="/companies",
            error="The requested task could not be found.",
        )

    form_data = await request.form()

    form = TaskCommentForm.from_form_data(
        form_data,
    )

    comment_create = form.validate()

    if comment_create is None:
        return _redirect_to_task(
            task_id=task.id,
            error=_first_form_error(
                form,
                "Please enter a valid comment.",
            ),
        )

    try:
        CommentService.add_comment(
            db,
            actor=current_user,
            task=task,
            comment_create=comment_create,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except PermissionDeniedError:
        return _redirect_to_task(
            task_id=task.id,
            error=(
                "You do not have permission to comment "
                "on this task."
            ),
        )

    except CommentServiceError as exc:
        return _redirect_to_task(
            task_id=task.id,
            error=str(exc),
        )

    return _redirect_to_task(
        task_id=task.id,
        success="Your comment was added.",
    )


@router.post(
    "/tasks/{task_id}/comments/{comment_id}/delete",
    name="task_comment_delete",
)
def delete_task_comment(
    task_id: int,
    comment_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    auth_session: ValidatedCSRFSession,
) -> RedirectResponse:
    del auth_session

    try:
        comment = CommentService.require_comment(
            db,
            comment_id=comment_id,
        )

    except CommentNotFoundError:
        return _redirect_to_task(
            task_id=task_id,
            error="The requested comment could not be found.",
        )

    if comment.task_id != task_id:
        return _redirect_to_task(
            task_id=task_id,
            error="The requested comment could not be found.",
        )

    try:
        CommentService.delete_comment(
            db,
            actor=current_user,
            comment=comment,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except CommentAlreadyDeletedError as exc:
        return _redirect_to_task(
            task_id=task_id,
            error=str(exc),
        )

    except CommentPermissionError as exc:
        return _redirect_to_task(
            task_id=task_id,
            error=str(exc),
        )

    except PermissionDeniedError:
        return _redirect_to_task(
            task_id=task_id,
            error=(
                "You do not have permission to delete "
                "this comment."
            ),
        )

    return _redirect_to_task(
        task_id=task_id,
        success="The comment was deleted.",
    )


def _redirect_to_task(
    *,
    task_id: int,
    success: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    return _redirect(
        path=f"/tasks/{task_id}",
        success=success,
        error=error,
    )


def _redirect(
    *,
    path: str,
    success: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    query: dict[str, str] = {}

    if success:
        query["success"] = success

    if error:
        query["error"] = error

    url = path

    if query:
        url = f"{url}?{urlencode(query)}"

    return RedirectResponse(
        url=url,
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _first_form_error(
    form: TaskCommentForm,
    default: str,
) -> str:
    if form.errors.form_errors:
        return form.errors.form_errors[0]

    for messages in form.errors.field_errors.values():
        if messages:
            return messages[0]

    return default