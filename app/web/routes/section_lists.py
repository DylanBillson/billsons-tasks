from urllib.parse import urlencode

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
from app.schemas.section_list import SectionListReorderRequest
from app.services.section_list_service import (
    SectionListLiveUpdateConflictError,
    SectionListNameAlreadyExistsError,
    SectionListNotEmptyError,
    SectionListNotFoundError,
    SectionListReorderError,
    SectionListService,
    SectionListServiceError,
)
from app.services.section_service import (
    SectionNotFoundError,
    SectionService,
)
from app.web.dependencies.auth import (
    CurrentUser,
    DatabaseSession,
    get_client_ip_address,
    get_user_agent,
)
from app.web.dependencies.csrf import ValidatedCSRFSession
from app.web.forms.section_list import SectionListForm
from app.web.templating import templates


router = APIRouter(
    tags=[
        "section lists",
    ],
)


@router.get(
    "/sections/{section_id}/lists/create",
    response_class=HTMLResponse,
    name="section_list_create",
)
def create_section_list_page(
    section_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> Response:
    try:
        section = SectionService.require_section(
            db,
            section_id=section_id,
        )

        PermissionService.require_section_list_creation(
            db,
            actor=current_user,
            section=section,
        )

    except SectionNotFoundError:
        return _redirect_to_companies(
            error="The requested section could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_section(
            section_id=section_id,
            error=(
                "You do not have permission to create "
                "lists in this section."
            ),
        )

    return templates.TemplateResponse(
        request=request,
        name="section_lists/create.html",
        context={
            "current_user": current_user,
            "section": section,
            "form": SectionListForm(),
            "csrf_token": _get_authenticated_csrf_token(
                request,
            ),
            "flash_messages": [],
        },
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/sections/{section_id}/lists/create",
    response_class=HTMLResponse,
    name="section_list_create_submit",
)
async def create_section_list_submit(
    section_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    auth_session: ValidatedCSRFSession,
) -> Response:
    del auth_session

    try:
        section = SectionService.require_section(
            db,
            section_id=section_id,
        )

        PermissionService.require_section_list_creation(
            db,
            actor=current_user,
            section=section,
        )

    except SectionNotFoundError:
        return _redirect_to_companies(
            error="The requested section could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_section(
            section_id=section_id,
            error=(
                "You do not have permission to create "
                "lists in this section."
            ),
        )

    form_data = await request.form()

    form = SectionListForm.from_form_data(
        form_data,
    )

    section_list_create = form.validate_create()

    if section_list_create is None:
        return _render_create_page(
            request=request,
            current_user=current_user,
            section=section,
            form=form,
            csrf_token=_get_submitted_csrf_token(
                form_data,
            ),
        )

    try:
        section_list = SectionListService.create_list(
            db,
            actor=current_user,
            section=section,
            section_list_create=section_list_create,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except SectionListNameAlreadyExistsError as exc:
        form.errors.add_field_error(
            "name",
            str(exc),
        )

        return _render_create_page(
            request=request,
            current_user=current_user,
            section=section,
            form=form,
            csrf_token=_get_submitted_csrf_token(
                form_data,
            ),
        )

    except PermissionDeniedError:
        return _redirect_to_section(
            section_id=section.id,
            error=(
                "You do not have permission to create "
                "lists in this section."
            ),
        )

    except SectionListServiceError as exc:
        form.errors.add_form_error(
            str(exc),
        )

        return _render_create_page(
            request=request,
            current_user=current_user,
            section=section,
            form=form,
            csrf_token=_get_submitted_csrf_token(
                form_data,
            ),
        )

    return _redirect_to_section(
        section_id=section.id,
        success=f"{section_list.name} was created.",
    )


@router.get(
    "/section-lists/{section_list_id}/edit",
    response_class=HTMLResponse,
    name="section_list_edit",
)
def edit_section_list_page(
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

        PermissionService.require_section_list_management(
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
            section_list_id=section_list_id,
            db=db,
            error=(
                "You do not have permission to edit "
                "this list."
            ),
        )

    return templates.TemplateResponse(
        request=request,
        name="section_lists/edit.html",
        context={
            "current_user": current_user,
            "section": section_list.section,
            "section_list": section_list,
            "form": SectionListForm.from_section_list(
                section_list,
            ),
            "csrf_token": _get_authenticated_csrf_token(
                request,
            ),
            "flash_messages": [],
        },
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/section-lists/{section_list_id}/edit",
    response_class=HTMLResponse,
    name="section_list_edit_submit",
)
async def edit_section_list_submit(
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

        PermissionService.require_section_list_management(
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
            section_list_id=section_list_id,
            db=db,
            error=(
                "You do not have permission to edit "
                "this list."
            ),
        )

    form_data = await request.form()

    form = SectionListForm.from_form_data(
        form_data,
    )

    section_list_update = form.validate_update()

    if section_list_update is None:
        return _render_edit_page(
            request=request,
            current_user=current_user,
            section_list=section_list,
            form=form,
            csrf_token=_get_submitted_csrf_token(
                form_data,
            ),
        )

    try:
        updated_list = SectionListService.update_list(
            db,
            actor=current_user,
            section_list=section_list,
            section_list_update=section_list_update,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except SectionListNameAlreadyExistsError as exc:
        form.errors.add_field_error(
            "name",
            str(exc),
        )

        return _render_edit_page(
            request=request,
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
                "You do not have permission to edit "
                "this list."
            ),
        )

    except SectionListServiceError as exc:
        form.errors.add_form_error(
            str(exc),
        )

        return _render_edit_page(
            request=request,
            current_user=current_user,
            section_list=section_list,
            form=form,
            csrf_token=_get_submitted_csrf_token(
                form_data,
            ),
        )

    return _redirect_to_section(
        section_id=updated_list.section_id,
        success=f"{updated_list.name} was updated.",
    )


@router.post(
    "/section-lists/{section_list_id}/archive",
    name="section_list_archive",
)
def archive_section_list(
    section_list_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    auth_session: ValidatedCSRFSession,
) -> RedirectResponse:
    del auth_session

    try:
        section_list = SectionListService.require_list(
            db,
            section_list_id=section_list_id,
        )

        section_list = SectionListService.set_archived_status(
            db,
            actor=current_user,
            section_list=section_list,
            is_archived=True,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except SectionListNotFoundError:
        return _redirect_to_companies(
            error="The requested list could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_section_list_parent(
            section_list_id=section_list_id,
            db=db,
            error=(
                "You do not have permission to archive "
                "this list."
            ),
        )

    return _redirect_to_section(
        section_id=section_list.section_id,
        success=f"{section_list.name} was archived.",
    )


@router.post(
    "/section-lists/{section_list_id}/restore",
    name="section_list_restore",
)
def restore_section_list(
    section_list_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    auth_session: ValidatedCSRFSession,
) -> RedirectResponse:
    del auth_session

    try:
        section_list = SectionListService.require_list(
            db,
            section_list_id=section_list_id,
        )

        section_list = SectionListService.set_archived_status(
            db,
            actor=current_user,
            section_list=section_list,
            is_archived=False,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except SectionListNotFoundError:
        return _redirect_to_companies(
            error="The requested list could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_section_list_parent(
            section_list_id=section_list_id,
            db=db,
            error=(
                "You do not have permission to restore "
                "this list."
            ),
        )

    return _redirect_to_section(
        section_id=section_list.section_id,
        success=f"{section_list.name} was restored.",
    )


@router.post(
    "/section-lists/{section_list_id}/delete",
    name="section_list_delete",
)
def delete_section_list(
    section_list_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    auth_session: ValidatedCSRFSession,
) -> RedirectResponse:
    del auth_session

    try:
        section_list = SectionListService.require_list(
            db,
            section_list_id=section_list_id,
        )

        section_id = section_list.section_id
        list_name = section_list.name

        SectionListService.delete_list(
            db,
            actor=current_user,
            section_list=section_list,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except SectionListNotFoundError:
        return _redirect_to_companies(
            error="The requested list could not be found.",
        )

    except SectionListNotEmptyError as exc:
        return _redirect_to_section_list_parent(
            section_list_id=section_list_id,
            db=db,
            error=str(exc),
        )

    except PermissionDeniedError:
        return _redirect_to_section_list_parent(
            section_list_id=section_list_id,
            db=db,
            error=(
                "You do not have permission to delete "
                "this list."
            ),
        )

    return _redirect_to_section(
        section_id=section_id,
        success=f"{list_name} was deleted.",
    )


@router.post(
    "/sections/{section_id}/lists/reorder",
    response_class=JSONResponse,
    name="section_lists_reorder",
)
async def reorder_section_lists(
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
                "The list order request was not valid JSON.",
                status.HTTP_422_UNPROCESSABLE_CONTENT,
            )

        reorder_request = (
            SectionListReorderRequest.model_validate(
                payload,
            )
        )

        ordered_lists = SectionListService.reorder_lists(
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
                "detail": "The list order was invalid.",
                "errors": exc.errors(
                    include_url=False,
                ),
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    except SectionListLiveUpdateConflictError as exc:
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
        SectionListReorderError,
        SectionListServiceError,
    ) as exc:
        return _json_error(
            str(exc),
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    except PermissionDeniedError:
        return _json_error(
            "You do not have permission to reorder these lists.",
            status.HTTP_403_FORBIDDEN,
        )

    return JSONResponse(
        {
            "section_id": section.id,
            "items": [
                {
                    "list_id": section_list.id,
                    "sort_position": section_list.sort_position,
                }
                for section_list in ordered_lists
            ],
        },
        status_code=status.HTTP_200_OK,
    )


def _render_create_page(
    *,
    request: Request,
    current_user: object,
    section: object,
    form: SectionListForm,
    csrf_token: str,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="section_lists/create.html",
        context={
            "current_user": current_user,
            "section": section,
            "form": form,
            "csrf_token": csrf_token,
            "flash_messages": [],
        },
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )


def _render_edit_page(
    *,
    request: Request,
    current_user: object,
    section_list: object,
    form: SectionListForm,
    csrf_token: str,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="section_lists/edit.html",
        context={
            "current_user": current_user,
            "section": section_list.section,
            "section_list": section_list,
            "form": form,
            "csrf_token": csrf_token,
            "flash_messages": [],
        },
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )


def _redirect_to_section_list_parent(
    *,
    section_list_id: int,
    db: DatabaseSession,
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