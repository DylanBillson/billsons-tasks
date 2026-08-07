from urllib.parse import urlencode
from app.services.live_update_service import (
    LiveUpdateService,
)
from fastapi import APIRouter, Request, status
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)
from pydantic import ValidationError

from app.auth.permissions import (
    PermissionDeniedError,
    PermissionService,
)
from app.core.config import settings
from app.repositories.section_membership_repository import (
    SectionMembershipRepository,
)
from app.schemas.task import (
    TaskMoveRequest,
    TaskReorderRequest,
)
from app.services.comment_service import CommentService
from app.services.section_list_service import (
    SectionListNotFoundError,
    SectionListService,
)
from app.services.section_service import (
    SectionNotFoundError,
    SectionService,
)
from app.services.task_assignee_service import (
    TaskAssigneeAlreadyExistsError,
    TaskAssigneeNotFoundError,
    TaskAssigneeService,
    TaskAssigneeServiceError,
)
from app.services.task_history_service import TaskHistoryService
from app.services.task_service import (
    TaskAlreadyCompletedError,
    TaskDestinationListNotFoundError,
    TaskLiveUpdateConflictError,
    TaskNotCompletedError,
    TaskNotFoundError,
    TaskReorderError,
    TaskService,
    TaskServiceError,
)
from app.web.dependencies.auth import (
    CurrentUser,
    DatabaseSession,
    get_client_ip_address,
    get_user_agent,
)
from app.web.dependencies.csrf import ValidatedCSRFSession
from app.web.forms.comment import TaskCommentForm
from app.web.forms.task import TaskForm
from app.web.forms.task_assignee import (
    TaskAssigneeCreateForm,
    TaskAssigneeReplaceForm,
)
from app.web.templating import templates


router = APIRouter(
    tags=[
        "tasks",
    ],
)


@router.get(
    "/section-lists/{section_list_id}/tasks/create",
    response_class=HTMLResponse,
    name="task_create",
)
def create_task_page(
    section_list_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> Response:
    try:
        section_list = SectionListService.require_list(
            db,
            section_list_id=section_list_id,
        )

        PermissionService.require_task_creation(
            db,
            actor=current_user,
            section_list=section_list,
        )

    except SectionListNotFoundError:
        return _redirect_to_companies(
            error="The requested list could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_section_list_parent(
            db=db,
            section_list_id=section_list_id,
            error=(
                "You do not have permission to create "
                "tasks in this list."
            ),
        )

    return templates.TemplateResponse(
        request=request,
        name="tasks/create.html",
        context=_task_form_context(
            request=request,
            db=db,
            current_user=current_user,
            section_list=section_list,
            form=TaskForm(
                section_list_id=str(
                    section_list.id,
                ),
            ),
        ),
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/section-lists/{section_list_id}/tasks/create",
    response_class=HTMLResponse,
    name="task_create_submit",
)
async def create_task_submit(
    section_list_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    auth_session: ValidatedCSRFSession,
) -> Response:
    del auth_session

    try:
        section_list = SectionListService.require_list(
            db,
            section_list_id=section_list_id,
        )

        PermissionService.require_task_creation(
            db,
            actor=current_user,
            section_list=section_list,
        )

    except SectionListNotFoundError:
        return _redirect_to_companies(
            error="The requested list could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_section_list_parent(
            db=db,
            section_list_id=section_list_id,
            error=(
                "You do not have permission to create "
                "tasks in this list."
            ),
        )

    form_data = await request.form()

    form = TaskForm.from_form_data(
        form_data,
    )

    task_create = form.validate_create(
        timezone_name=settings.default_timezone,
    )

    if task_create is None:
        return _render_task_create_form(
            request=request,
            db=db,
            current_user=current_user,
            section_list=section_list,
            form=form,
            csrf_token=_get_submitted_csrf_token(
                form_data,
            ),
        )

    try:
        task = TaskService.create_task(
            db,
            actor=current_user,
            section_list=section_list,
            task_create=task_create,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except (
        TaskAssigneeServiceError,
        TaskServiceError,
    ) as exc:
        form.errors.add_form_error(
            str(exc),
        )

        return _render_task_create_form(
            request=request,
            db=db,
            current_user=current_user,
            section_list=section_list,
            form=form,
            csrf_token=_get_submitted_csrf_token(
                form_data,
            ),
        )

    except PermissionDeniedError:
        return _redirect_to_section(
            section_id=section_list.section_id,
            error=(
                "You do not have permission to create "
                "this task."
            ),
        )

    return _redirect_to_task(
        task_id=task.id,
        success=f"{task.title} was created.",
    )


@router.get(
    "/tasks/{task_id}",
    response_class=HTMLResponse,
    name="task_detail",
)
def task_detail(
    task_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    success: str | None = None,
    error: str | None = None,
) -> Response:
    try:
        task = TaskService.get_accessible_task(
            db,
            actor=current_user,
            task_id=task_id,
        )

    except TaskNotFoundError:
        return _redirect_to_companies(
            error="The requested task could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_companies(
            error="You do not have access to the requested task.",
        )

    comments = CommentService.list_for_task(
        db,
        actor=current_user,
        task=task,
        include_deleted=True,
    )

    history_events = TaskHistoryService.list_for_task(
        db,
        task=task,
    )

    assignments = TaskAssigneeService.list_for_task(
        db,
        actor=current_user,
        task=task,
    )

    section_lists = SectionListService.list_for_section(
        db,
        actor=current_user,
        section=task.section_list.section,
        include_archived=True,
    )

    can_update = PermissionService.can_update_task(
        db,
        actor=current_user,
        task=task,
    )

    can_manage_assignees = (
        PermissionService.can_manage_task_assignees(
            db,
            actor=current_user,
            task=task,
        )
    )

    can_delete = PermissionService.can_delete_task(
        db,
        actor=current_user,
        task=task,
    )

    can_restore = PermissionService.can_restore_task(
        db,
        actor=current_user,
        task=task,
    )

    can_permanently_delete = (
        PermissionService.can_permanently_delete_task(
            actor=current_user,
            task=task,
        )
    )
    task_revision = (
        LiveUpdateService.get_task_revision(
            db,
            actor=current_user,
            task_id=task.id,
        )
    )

    section_revision = (
        LiveUpdateService.get_section_revision(
            db,
            actor=current_user,
            section_id=task.section_id,
        )
    )
    return templates.TemplateResponse(
        request=request,
        name="tasks/detail.html",
        context={
            "current_user": current_user,
            "task": task,
            "task_revision": task_revision,
            "section_revision": section_revision,
            "section": task.section_list.section,
            "section_list": task.section_list,
            "section_lists": section_lists,
            "assignments": assignments,
            "available_assignees": _available_assignees(
                db,
                task.section_list.section,
            ),
            "comments": comments,
            "history_events": history_events,
            "comment_form": TaskCommentForm(),
            "assignee_form": TaskAssigneeCreateForm(),
            "assignee_replace_form": (
                TaskAssigneeReplaceForm.from_task(
                    task,
                )
            ),
            "can_update": can_update,
            "can_complete": (
                PermissionService.can_complete_task(
                    db,
                    actor=current_user,
                    task=task,
                )
            ),
            "can_comment": (
                PermissionService.can_comment_on_task(
                    db,
                    actor=current_user,
                    task=task,
                )
            ),
            "can_manage_assignees": can_manage_assignees,
            "can_delete": can_delete,
            "can_restore": can_restore,
            "can_permanently_delete": can_permanently_delete,
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
    "/tasks/{task_id}/edit",
    response_class=HTMLResponse,
    name="task_edit",
)
def edit_task_page(
    task_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> Response:
    try:
        task = TaskService.require_task(
            db,
            task_id=task_id,
        )

        PermissionService.require_task_update(
            db,
            actor=current_user,
            task=task,
        )

    except TaskNotFoundError:
        return _redirect_to_companies(
            error="The requested task could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_task(
            task_id=task_id,
            error=(
                "You do not have permission to edit "
                "this task."
            ),
        )

    return templates.TemplateResponse(
        request=request,
        name="tasks/edit.html",
        context={
            "current_user": current_user,
            "task": task,
            "section": task.section_list.section,
            "section_list": task.section_list,
            "form": TaskForm.from_task(
                task,
                timezone_name=settings.default_timezone,
            ),
            "csrf_token": _get_authenticated_csrf_token(
                request,
            ),
            "flash_messages": [],
        },
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/tasks/{task_id}/edit",
    response_class=HTMLResponse,
    name="task_edit_submit",
)
async def edit_task_submit(
    task_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    auth_session: ValidatedCSRFSession,
) -> Response:
    del auth_session

    try:
        task = TaskService.require_task(
            db,
            task_id=task_id,
        )

        PermissionService.require_task_update(
            db,
            actor=current_user,
            task=task,
        )

    except TaskNotFoundError:
        return _redirect_to_companies(
            error="The requested task could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_task(
            task_id=task_id,
            error=(
                "You do not have permission to edit "
                "this task."
            ),
        )

    form_data = await request.form()

    form = TaskForm.from_form_data(
        form_data,
    )

    task_update = form.validate_update(
        timezone_name=settings.default_timezone,
    )

    if task_update is None:
        return _render_task_edit_form(
            request=request,
            current_user=current_user,
            task=task,
            form=form,
            csrf_token=_get_submitted_csrf_token(
                form_data,
            ),
        )

    try:
        updated_task = TaskService.update_task(
            db,
            actor=current_user,
            task=task,
            task_update=task_update,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except TaskServiceError as exc:
        form.errors.add_form_error(
            str(exc),
        )

        return _render_task_edit_form(
            request=request,
            current_user=current_user,
            task=task,
            form=form,
            csrf_token=_get_submitted_csrf_token(
                form_data,
            ),
        )

    except PermissionDeniedError:
        return _redirect_to_task(
            task_id=task.id,
            error=(
                "You do not have permission to edit "
                "this task."
            ),
        )

    return _redirect_to_task(
        task_id=updated_task.id,
        success=f"{updated_task.title} was updated.",
    )


@router.post(
    "/tasks/{task_id}/complete",
    name="task_complete",
)
def complete_task(
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

        task = TaskService.complete_task(
            db,
            actor=current_user,
            task=task,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except TaskNotFoundError:
        return _redirect_to_companies(
            error="The requested task could not be found.",
        )

    except TaskAlreadyCompletedError as exc:
        return _redirect_to_task(
            task_id=task_id,
            error=str(exc),
        )

    except PermissionDeniedError:
        return _redirect_to_task(
            task_id=task_id,
            error=(
                "You do not have permission to complete "
                "this task."
            ),
        )

    return _redirect_to_task(
        task_id=task.id,
        success=f"{task.title} was completed.",
    )


@router.post(
    "/tasks/{task_id}/reopen",
    name="task_reopen",
)
def reopen_task(
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

        task = TaskService.reopen_task(
            db,
            actor=current_user,
            task=task,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except TaskNotFoundError:
        return _redirect_to_companies(
            error="The requested task could not be found.",
        )

    except TaskNotCompletedError as exc:
        return _redirect_to_task(
            task_id=task_id,
            error=str(exc),
        )

    except PermissionDeniedError:
        return _redirect_to_task(
            task_id=task_id,
            error=(
                "You do not have permission to reopen "
                "this task."
            ),
        )

    return _redirect_to_task(
        task_id=task.id,
        success=f"{task.title} was reopened.",
    )


@router.post(
    "/tasks/{task_id}/delete",
    name="task_delete",
)
def delete_task(
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

        section_id = task.section_id
        task_title = task.title

        TaskService.delete_task(
            db,
            actor=current_user,
            task=task,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except TaskNotFoundError:
        return _redirect_to_companies(
            error="The requested task could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_task(
            task_id=task_id,
            error=(
                "You do not have permission to delete "
                "this task."
            ),
        )

    return _redirect_to_section(
        section_id=section_id,
        success=f"{task_title} was deleted.",
    )


@router.post(
    "/tasks/{task_id}/restore",
    name="task_restore",
)
def restore_task(
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

        task = TaskService.restore_task(
            db,
            actor=current_user,
            task=task,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except TaskNotFoundError:
        return _redirect_to_companies(
            error="The requested task could not be found.",
        )

    except TaskServiceError as exc:
        return _redirect_to_task(
            task_id=task_id,
            error=str(exc),
        )

    except PermissionDeniedError:
        return _redirect_to_task(
            task_id=task_id,
            error=(
                "You do not have permission to restore "
                "this task."
            ),
        )

    return _redirect_to_task(
        task_id=task.id,
        success=f"{task.title} was restored.",
    )


@router.post(
    "/tasks/{task_id}/move",
    response_class=JSONResponse,
    name="task_move",
)
async def move_task(
    task_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    auth_session: ValidatedCSRFSession,
) -> JSONResponse:
    del auth_session

    try:
        task = TaskService.require_task(
            db,
            task_id=task_id,
        )

        payload = await request.json()

        move_request = TaskMoveRequest.model_validate(
            payload,
        )

        destination_list = SectionListService.require_list(
            db,
            section_list_id=move_request.destination_list_id,
        )

        moved_task = TaskService.move_task(
            db,
            actor=current_user,
            task=task,
            destination_list=destination_list,
            move_request=move_request,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except TaskNotFoundError:
        return _json_error(
            "The requested task could not be found.",
            status.HTTP_404_NOT_FOUND,
        )

    except SectionListNotFoundError:
        return _json_error(
            "The destination list could not be found.",
            status.HTTP_404_NOT_FOUND,
        )

    except ValidationError as exc:
        return JSONResponse(
            {
                "detail": "The task move was invalid.",
                "errors": exc.errors(
                    include_url=False,
                ),
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    except TaskLiveUpdateConflictError as exc:
        return JSONResponse(
            {
                "detail": str(
                    exc,
                ),
                "code": "live_update_conflict",
                "current_revision": (
                    exc.current_revision
                ),
            },
            status_code=status.HTTP_409_CONFLICT,
        )

    except TaskDestinationListNotFoundError as exc:
        return _json_error(
            str(exc),
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    except TaskServiceError as exc:
        return _json_error(
            str(exc),
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    except PermissionDeniedError:
        return _json_error(
            "You do not have permission to move this task.",
            status.HTTP_403_FORBIDDEN,
        )

    return JSONResponse(
        {
            "task_id": moved_task.id,
            "section_list_id": moved_task.section_list_id,
            "sort_position": moved_task.sort_position,
        },
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/sections/{section_id}/tasks/reorder",
    response_class=JSONResponse,
    name="tasks_reorder",
)
async def reorder_tasks(
    section_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    auth_session: ValidatedCSRFSession,
) -> JSONResponse:
    del auth_session

    try:
        section = SectionService.require_section(
            db,
            section_id=section_id,
        )

        try:
            payload = await request.json()

        except ValueError:
            return _json_error(
                "The task order request was not valid JSON.",
                status.HTTP_422_UNPROCESSABLE_CONTENT,
            )

        reorder_request = (
            TaskReorderRequest.model_validate(
                payload,
            )
        )

        tasks = TaskService.reorder_tasks(
            db,
            actor=current_user,
            section=section,
            reorder_request=reorder_request,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except SectionNotFoundError:
        return _json_error(
            "The requested section could not be found.",
            status.HTTP_404_NOT_FOUND,
        )

    except ValidationError as exc:
        return JSONResponse(
            {
                "detail": "The task order was invalid.",
                "errors": exc.errors(
                    include_url=False,
                ),
            },
            status_code=(
                status.HTTP_422_UNPROCESSABLE_CONTENT
            ),
        )

    except TaskLiveUpdateConflictError as exc:
        return JSONResponse(
            {
                "detail": str(
                    exc,
                ),
                "code": "live_update_conflict",
                "current_revision": (
                    exc.current_revision
                ),
            },
            status_code=status.HTTP_409_CONFLICT,
        )

    except (
        TaskReorderError,
        TaskServiceError,
    ) as exc:
        return _json_error(
            str(exc),
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    except PermissionDeniedError:
        return _json_error(
            (
                "You do not have permission "
                "to reorder these tasks."
            ),
            status.HTTP_403_FORBIDDEN,
        )

    return JSONResponse(
        {
            "section_id": section.id,
            "items": [
                {
                    "task_id": task.id,
                    "section_list_id": (
                        task.section_list_id
                    ),
                    "sort_position": (
                        task.sort_position
                    ),
                }
                for task in tasks
                if not task.is_deleted
            ],
        },
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/tasks/{task_id}/assignees",
    response_class=HTMLResponse,
    name="task_assignee_add",
)
async def add_task_assignee(
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
        return _redirect_to_companies(
            error="The requested task could not be found.",
        )

    form_data = await request.form()

    form = TaskAssigneeCreateForm.from_form_data(
        form_data,
    )

    create_request = form.validate()

    if create_request is None:
        return _redirect_to_task(
            task_id=task.id,
            error=_first_form_error(
                form.errors,
                "Please select a valid assignee.",
            ),
        )

    try:
        assignment = TaskAssigneeService.add_assignee(
            db,
            actor=current_user,
            task=task,
            create_request=create_request,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except TaskAssigneeAlreadyExistsError as exc:
        return _redirect_to_task(
            task_id=task.id,
            error=str(exc),
        )

    except TaskAssigneeServiceError as exc:
        return _redirect_to_task(
            task_id=task.id,
            error=str(exc),
        )

    except PermissionDeniedError:
        return _redirect_to_task(
            task_id=task.id,
            error=(
                "You do not have permission to manage "
                "this task's assignees."
            ),
        )

    return _redirect_to_task(
        task_id=task.id,
        success=(
            f"{assignment.user.display_name} was assigned "
            f"to this task."
        ),
    )


@router.post(
    "/tasks/{task_id}/assignees/replace",
    response_class=HTMLResponse,
    name="task_assignees_replace",
)
async def replace_task_assignees(
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
        return _redirect_to_companies(
            error="The requested task could not be found.",
        )

    form_data = await request.form()

    form = TaskAssigneeReplaceForm.from_form_data(
        form_data,
    )

    replace_request = form.validate()

    if replace_request is None:
        return _redirect_to_task(
            task_id=task.id,
            error=_first_form_error(
                form.errors,
                "The selected assignees were invalid.",
            ),
        )

    try:
        TaskAssigneeService.replace_assignees(
            db,
            actor=current_user,
            task=task,
            replace_request=replace_request,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except TaskAssigneeServiceError as exc:
        return _redirect_to_task(
            task_id=task.id,
            error=str(exc),
        )

    except PermissionDeniedError:
        return _redirect_to_task(
            task_id=task.id,
            error=(
                "You do not have permission to manage "
                "this task's assignees."
            ),
        )

    return _redirect_to_task(
        task_id=task.id,
        success="The task assignees were updated.",
    )


@router.post(
    "/tasks/{task_id}/assignees/{user_id}/remove",
    name="task_assignee_remove",
)
def remove_task_assignee(
    task_id: int,
    user_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    auth_session: ValidatedCSRFSession,
) -> RedirectResponse:
    del auth_session

    try:
        assignment = TaskAssigneeService.require_assignment(
            db,
            task_id=task_id,
            user_id=user_id,
        )

        display_name = assignment.user.display_name

        TaskAssigneeService.remove_assignee(
            db,
            actor=current_user,
            assignment=assignment,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except TaskAssigneeNotFoundError:
        return _redirect_to_task(
            task_id=task_id,
            error="The requested task assignment could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_task(
            task_id=task_id,
            error=(
                "You do not have permission to manage "
                "this task's assignees."
            ),
        )

    return _redirect_to_task(
        task_id=task_id,
        success=f"{display_name} was removed from the task.",
    )


def _task_form_context(
    *,
    request: Request,
    db: DatabaseSession,
    current_user: object,
    section_list: object,
    form: TaskForm,
    csrf_token: str | None = None,
) -> dict[str, object]:
    can_manage_section = PermissionService.can_manage_section(
        db,
        actor=current_user,
        section=section_list.section,
    )

    return {
        "current_user": current_user,
        "section": section_list.section,
        "section_list": section_list,
        "form": form,
        "available_assignees": (
            _available_assignees(
                db,
                section_list.section,
            )
            if can_manage_section
            else []
        ),
        "can_manage_assignees": can_manage_section,
        "csrf_token": (
            csrf_token
            if csrf_token is not None
            else _get_authenticated_csrf_token(
                request,
            )
        ),
        "flash_messages": [],
    }


def _render_task_create_form(
    *,
    request: Request,
    db: DatabaseSession,
    current_user: object,
    section_list: object,
    form: TaskForm,
    csrf_token: str,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="tasks/create.html",
        context=_task_form_context(
            request=request,
            db=db,
            current_user=current_user,
            section_list=section_list,
            form=form,
            csrf_token=csrf_token,
        ),
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )


def _render_task_edit_form(
    *,
    request: Request,
    current_user: object,
    task: object,
    form: TaskForm,
    csrf_token: str,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="tasks/edit.html",
        context={
            "current_user": current_user,
            "task": task,
            "section": task.section_list.section,
            "section_list": task.section_list,
            "form": form,
            "csrf_token": csrf_token,
            "flash_messages": [],
        },
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )


def _available_assignees(
    db: DatabaseSession,
    section: object,
) -> list[object]:
    memberships = SectionMembershipRepository.list_for_section(
        db,
        section_id=section.id,
    )

    users_by_id = {
        membership.user.id: membership.user
        for membership in memberships
        if membership.user.can_authenticate
    }

    if section.created_by.can_authenticate:
        users_by_id[
            section.created_by.id
        ] = section.created_by

    return sorted(
        users_by_id.values(),
        key=lambda user: (
            user.display_name.casefold(),
            user.username.casefold(),
            user.id,
        ),
    )


def _redirect_to_section_list_parent(
    *,
    db: DatabaseSession,
    section_list_id: int,
    error: str,
) -> RedirectResponse:
    section_list = SectionListService.get_list(
        db,
        section_list_id=section_list_id,
    )

    if section_list is None:
        return _redirect_to_companies(
            error=error,
        )

    return _redirect_to_section(
        section_id=section_list.section_id,
        error=error,
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


def _redirect_to_section(
    *,
    section_id: int,
    success: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    return _redirect(
        path=f"/sections/{section_id}",
        success=success,
        error=error,
    )


def _redirect_to_companies(
    *,
    error: str,
) -> RedirectResponse:
    return _redirect(
        path="/companies",
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


def _first_form_error(
    errors: object,
    default: str,
) -> str:
    if errors.form_errors:
        return errors.form_errors[0]

    for messages in errors.field_errors.values():
        if messages:
            return messages[0]

    return default


def _get_authenticated_csrf_token(
    request: Request,
) -> str:
    return request.cookies.get(
        f"{settings.session_cookie_name}_csrf",
        "",
    )


def _get_submitted_csrf_token(
    form_data: object,
) -> str:
    getter = getattr(
        form_data,
        "get",
        None,
    )

    if getter is None:
        return ""

    return str(
        getter(
            "csrf_token",
            "",
        ),
    )


def _json_error(
    detail: str,
    status_code: int,
) -> JSONResponse:
    return JSONResponse(
        {
            "detail": detail,
        },
        status_code=status_code,
    )