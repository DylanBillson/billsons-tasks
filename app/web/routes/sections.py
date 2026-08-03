from urllib.parse import urlencode

from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth.permissions import (
    PermissionDeniedError,
    PermissionService,
)
from app.core.config import settings
from app.models.company_membership import CompanyMembership
from app.models.section_membership import SectionMembership
from app.repositories.company_membership_repository import (
    CompanyMembershipRepository,
)
from app.repositories.section_membership_repository import (
    SectionMembershipRepository,
)
from app.schemas.task import TaskFilterOptions
from app.services.company_service import (
    CompanyNotFoundError,
    CompanyService,
)
from app.services.section_list_service import SectionListService
from app.services.section_membership_service import (
    SectionCompanyMembershipRequiredError,
    SectionMembershipAlreadyExistsError,
    SectionMembershipNotFoundError,
    SectionMembershipService,
    SectionMembershipServiceError,
    SectionMembershipUserNotFoundError,
    SectionMembershipUserUnavailableError,
)
from app.services.section_service import (
    SectionCompanyNotFoundError,
    SectionNameAlreadyExistsError,
    SectionNotFoundError,
    SectionService,
    SectionServiceError,
)
from app.services.task_service import (
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
from app.web.forms.section import (
    SectionForm,
    SectionMembershipCreateForm,
)
from app.web.forms.task import TaskFilterForm
from app.web.templating import templates


router = APIRouter(
    tags=[
        "sections",
    ],
)


@router.get(
    "/companies/{company_id}/sections/create",
    response_class=HTMLResponse,
    name="section_create",
)
def create_section_page(
    company_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> HTMLResponse:
    """
    Display the section creation form.

    Global administrators and managers of the selected company may create
    sections. Company employees and users from other companies are denied.
    """
    try:
        company = CompanyService.require_company(
            db,
            company_id=company_id,
        )

        PermissionService.require_section_creation(
            db,
            actor=current_user,
            company=company,
        )

    except CompanyNotFoundError:
        return _redirect_to_company_list(
            error="The requested company could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_company_detail(
            company_id=company_id,
            error=(
                "You do not have permission to create "
                "sections in this company."
            ),
        )

    return templates.TemplateResponse(
        request=request,
        name="sections/create.html",
        context={
            "current_user": current_user,
            "company": company,
            "form": SectionForm(),
            "csrf_token": _get_authenticated_csrf_token(
                request,
            ),
            "flash_messages": [],
        },
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/companies/{company_id}/sections/create",
    response_class=HTMLResponse,
    name="section_create_submit",
)
async def create_section_submit(
    company_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    auth_session: ValidatedCSRFSession,
) -> HTMLResponse:
    """
    Validate and create a section in a company.
    """
    del auth_session

    try:
        company = CompanyService.require_company(
            db,
            company_id=company_id,
        )

        PermissionService.require_section_creation(
            db,
            actor=current_user,
            company=company,
        )

    except CompanyNotFoundError:
        return _redirect_to_company_list(
            error="The requested company could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_company_detail(
            company_id=company_id,
            error=(
                "You do not have permission to create "
                "sections in this company."
            ),
        )

    form_data = await request.form()

    form = SectionForm.from_form_data(
        form_data,
    )

    section_create = form.validate_create()

    if section_create is None:
        return templates.TemplateResponse(
            request=request,
            name="sections/create.html",
            context={
                "current_user": current_user,
                "company": company,
                "form": form,
                "csrf_token": (
                    _get_form_value(
                        form_data,
                        "csrf_token",
                    )
                    or ""
                ),
                "flash_messages": [],
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    try:
        section = SectionService.create_section(
            db,
            actor=current_user,
            company=company,
            section_create=section_create,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except SectionNameAlreadyExistsError as exc:
        form.errors.add_field_error(
            "name",
            str(exc),
        )

        return templates.TemplateResponse(
            request=request,
            name="sections/create.html",
            context={
                "current_user": current_user,
                "company": company,
                "form": form,
                "csrf_token": (
                    _get_form_value(
                        form_data,
                        "csrf_token",
                    )
                    or ""
                ),
                "flash_messages": [],
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    except PermissionDeniedError:
        return _redirect_to_company_detail(
            company_id=company.id,
            error=(
                "You do not have permission to create "
                "sections in this company."
            ),
        )

    except SectionServiceError as exc:
        form.errors.add_form_error(
            str(exc),
        )

        return templates.TemplateResponse(
            request=request,
            name="sections/create.html",
            context={
                "current_user": current_user,
                "company": company,
                "form": form,
                "csrf_token": (
                    _get_form_value(
                        form_data,
                        "csrf_token",
                    )
                    or ""
                ),
                "flash_messages": [],
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    return _redirect_to_section_detail(
        section_id=section.id,
        success=f"{section.name} was created.",
    )


@router.get(
    "/sections/{section_id}",
    response_class=HTMLResponse,
    name="section_detail",
)
def section_detail(
    section_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    success: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    """
    Display a section and its task board after enforcing server-side access
    isolation.

    Task filters are parsed from the query string. Invalid filters are shown
    back to the user and ignored rather than allowing malformed or foreign
    identifiers to produce a server error.
    """
    try:
        section = SectionService.get_accessible_section(
            db,
            actor=current_user,
            section_id=section_id,
        )

    except SectionNotFoundError:
        return _redirect_to_company_list(
            error="The requested section could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_company_list(
            error="You do not have access to the requested section.",
        )

    memberships = SectionMembershipRepository.list_for_section(
        db,
        section_id=section.id,
    )

    company_memberships = _get_company_membership_map(
        db,
        company_id=section.company_id,
    )

    can_manage_section = PermissionService.can_manage_section(
        db,
        actor=current_user,
        section=section,
    )

    can_manage_section_memberships = (
        PermissionService.can_manage_section_memberships(
            db,
            actor=current_user,
            section=section,
        )
    )

    can_create_section_list = (
        PermissionService.can_create_section_list(
            db,
            actor=current_user,
            section=section,
        )
    )

    all_section_lists = SectionListService.list_for_section(
        db,
        actor=current_user,
        section=section,
        include_archived=True,
    )

    section_lists = [
        section_list
        for section_list in all_section_lists
        if not section_list.is_archived
    ]

    archived_section_lists = [
        section_list
        for section_list in all_section_lists
        if section_list.is_archived
    ]

    filter_form = TaskFilterForm.from_query_params(
        request.query_params,
    )

    task_filters = filter_form.validate(
        timezone_name=settings.default_timezone,
    )

    if task_filters is None:
        task_filters = TaskFilterOptions()

    try:
        tasks = TaskService.list_for_section(
            db,
            actor=current_user,
            section=section,
            filters=task_filters,
        )

    except TaskServiceError as exc:
        filter_form.errors.add_form_error(
            str(exc),
        )

        task_filters = TaskFilterOptions()

        tasks = TaskService.list_for_section(
            db,
            actor=current_user,
            section=section,
            filters=task_filters,
        )

    active_list_ids = {
        section_list.id
        for section_list in section_lists
    }

    tasks = [
        task
        for task in tasks
        if task.section_list_id in active_list_ids
    ]

    can_create_task = any(
        PermissionService.can_create_task(
            db,
            actor=current_user,
            section_list=section_list,
        )
        for section_list in section_lists
    )

    available_assignees = _get_available_task_assignees(
        section=section,
        section_memberships=memberships,
    )

    return templates.TemplateResponse(
        request=request,
        name="sections/detail.html",
        context={
            "current_user": current_user,
            "section": section,
            "memberships": memberships,
            "company_memberships": company_memberships,
            "section_lists": section_lists,
            "archived_section_lists": archived_section_lists,
            "tasks": tasks,
            "task_filters": task_filters,
            "task_filter_form": filter_form,
            "available_assignees": available_assignees,
            "can_manage_section": can_manage_section,
            "can_manage_section_memberships": (
                can_manage_section_memberships
            ),
            "can_create_section_list": can_create_section_list,
            "can_create_task": can_create_task,
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
    "/sections/{section_id}/edit",
    response_class=HTMLResponse,
    name="section_edit",
)
def edit_section_page(
    section_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> HTMLResponse:
    """
    Display the section edit form.

    Only global administrators and the section creator may edit a section.
    """
    try:
        section = SectionService.require_section(
            db,
            section_id=section_id,
        )

        PermissionService.require_section_management(
            db,
            actor=current_user,
            section=section,
        )

    except SectionNotFoundError:
        return _redirect_to_company_list(
            error="The requested section could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_section_detail(
            section_id=section_id,
            error=(
                "You do not have permission to edit "
                "this section."
            ),
        )

    return templates.TemplateResponse(
        request=request,
        name="sections/edit.html",
        context={
            "current_user": current_user,
            "section": section,
            "form": SectionForm.from_section(
                section,
            ),
            "csrf_token": _get_authenticated_csrf_token(
                request,
            ),
            "flash_messages": [],
        },
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/sections/{section_id}/edit",
    response_class=HTMLResponse,
    name="section_edit_submit",
)
async def edit_section_submit(
    section_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    auth_session: ValidatedCSRFSession,
) -> HTMLResponse:
    """
    Validate and update a section.
    """
    del auth_session

    try:
        section = SectionService.require_section(
            db,
            section_id=section_id,
        )

        PermissionService.require_section_management(
            db,
            actor=current_user,
            section=section,
        )

    except SectionNotFoundError:
        return _redirect_to_company_list(
            error="The requested section could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_section_detail(
            section_id=section_id,
            error=(
                "You do not have permission to edit "
                "this section."
            ),
        )

    form_data = await request.form()

    form = SectionForm.from_form_data(
        form_data,
    )

    section_update = form.validate_update()

    if section_update is None:
        return templates.TemplateResponse(
            request=request,
            name="sections/edit.html",
            context={
                "current_user": current_user,
                "section": section,
                "form": form,
                "csrf_token": (
                    _get_form_value(
                        form_data,
                        "csrf_token",
                    )
                    or ""
                ),
                "flash_messages": [],
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    try:
        updated_section = SectionService.update_section(
            db,
            actor=current_user,
            section=section,
            section_update=section_update,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except SectionNameAlreadyExistsError as exc:
        form.errors.add_field_error(
            "name",
            str(exc),
        )

        return templates.TemplateResponse(
            request=request,
            name="sections/edit.html",
            context={
                "current_user": current_user,
                "section": section,
                "form": form,
                "csrf_token": (
                    _get_form_value(
                        form_data,
                        "csrf_token",
                    )
                    or ""
                ),
                "flash_messages": [],
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    except PermissionDeniedError:
        return _redirect_to_section_detail(
            section_id=section.id,
            error=(
                "You do not have permission to edit "
                "this section."
            ),
        )

    return _redirect_to_section_detail(
        section_id=updated_section.id,
        success=f"{updated_section.name} was updated.",
    )


@router.post(
    "/sections/{section_id}/archive",
    name="section_archive",
)
def archive_section(
    section_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    auth_session: ValidatedCSRFSession,
) -> RedirectResponse:
    """
    Archive a section.
    """
    del auth_session

    try:
        section = SectionService.set_archived_status_by_id(
            db,
            actor=current_user,
            section_id=section_id,
            is_archived=True,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except SectionNotFoundError:
        return _redirect_to_company_list(
            error="The requested section could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_section_detail(
            section_id=section_id,
            error=(
                "You do not have permission to archive "
                "this section."
            ),
        )

    return _redirect_to_company_detail(
        company_id=section.company_id,
        success=f"{section.name} was archived.",
    )


@router.post(
    "/sections/{section_id}/restore",
    name="section_restore",
)
def restore_section(
    section_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    auth_session: ValidatedCSRFSession,
) -> RedirectResponse:
    """
    Restore an archived section.
    """
    del auth_session

    try:
        section = SectionService.set_archived_status_by_id(
            db,
            actor=current_user,
            section_id=section_id,
            is_archived=False,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except SectionNotFoundError:
        return _redirect_to_company_list(
            error="The requested section could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_section_detail(
            section_id=section_id,
            error=(
                "You do not have permission to restore "
                "this section."
            ),
        )

    return _redirect_to_section_detail(
        section_id=section.id,
        success=f"{section.name} was restored.",
    )


@router.get(
    "/sections/{section_id}/members",
    response_class=HTMLResponse,
    name="section_members",
)
def section_members_page(
    section_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    success: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    """
    Display explicit section assignments.

    Only global administrators and the section creator may manage section
    membership.
    """
    try:
        section = SectionService.require_section(
            db,
            section_id=section_id,
        )

        PermissionService.require_section_membership_management(
            db,
            actor=current_user,
            section=section,
        )

    except SectionNotFoundError:
        return _redirect_to_company_list(
            error="The requested section could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_section_detail(
            section_id=section_id,
            error=(
                "You do not have permission to manage "
                "this section's members."
            ),
        )

    memberships = SectionMembershipRepository.list_for_section(
        db,
        section_id=section.id,
    )

    company_memberships = (
        CompanyMembershipRepository.list_for_company(
            db,
            company_id=section.company_id,
        )
    )

    company_membership_map = {
        membership.user_id: membership
        for membership in company_memberships
    }

    available_users = _get_available_section_users(
        company_memberships=company_memberships,
        section_memberships=memberships,
    )

    return templates.TemplateResponse(
        request=request,
        name="sections/members.html",
        context={
            "current_user": current_user,
            "section": section,
            "memberships": memberships,
            "company_memberships": company_membership_map,
            "available_users": available_users,
            "form": SectionMembershipCreateForm(),
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
    "/sections/{section_id}/members",
    response_class=HTMLResponse,
    name="section_member_add",
)
async def add_section_member(
    section_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    auth_session: ValidatedCSRFSession,
) -> HTMLResponse:
    """
    Assign an active member of the parent company to a section.
    """
    del auth_session

    try:
        section = SectionService.require_section(
            db,
            section_id=section_id,
        )

        PermissionService.require_section_membership_management(
            db,
            actor=current_user,
            section=section,
        )

    except SectionNotFoundError:
        return _redirect_to_company_list(
            error="The requested section could not be found.",
        )

    except PermissionDeniedError:
        return _redirect_to_section_detail(
            section_id=section_id,
            error=(
                "You do not have permission to manage "
                "this section's members."
            ),
        )

    form_data = await request.form()

    form = SectionMembershipCreateForm.from_form_data(
        form_data,
    )

    membership_create = form.validate()

    if membership_create is None:
        return _render_section_members_page(
            request=request,
            db=db,
            current_user=current_user,
            section=section,
            form=form,
            csrf_token=(
                _get_form_value(
                    form_data,
                    "csrf_token",
                )
                or ""
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    try:
        membership = SectionMembershipService.assign_user(
            db,
            actor=current_user,
            section=section,
            membership_create=membership_create,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except (
        SectionCompanyMembershipRequiredError,
        SectionMembershipAlreadyExistsError,
        SectionMembershipUserNotFoundError,
        SectionMembershipUserUnavailableError,
        SectionMembershipServiceError,
    ) as exc:
        form.errors.add_form_error(
            str(exc),
        )

        return _render_section_members_page(
            request=request,
            db=db,
            current_user=current_user,
            section=section,
            form=form,
            csrf_token=(
                _get_form_value(
                    form_data,
                    "csrf_token",
                )
                or ""
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    except PermissionDeniedError:
        return _redirect_to_section_detail(
            section_id=section.id,
            error=(
                "You do not have permission to manage "
                "this section's members."
            ),
        )

    return _redirect_to_section_members(
        section_id=section.id,
        success=(
            f"{membership.user.display_name} was assigned "
            f"to {section.name}."
        ),
    )


@router.post(
    "/sections/{section_id}/members/{user_id}/remove",
    name="section_member_remove",
)
def remove_section_member(
    section_id: int,
    user_id: int,
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    auth_session: ValidatedCSRFSession,
) -> RedirectResponse:
    """
    Remove an explicit section assignment.
    """
    del auth_session

    try:
        membership = SectionMembershipService.require_membership(
            db,
            section_id=section_id,
            user_id=user_id,
        )

        display_name = membership.user.display_name

        SectionMembershipService.remove_user(
            db,
            actor=current_user,
            membership=membership,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except SectionMembershipNotFoundError:
        return _redirect_to_section_members(
            section_id=section_id,
            error=(
                "The requested section membership "
                "could not be found."
            ),
        )

    except PermissionDeniedError:
        return _redirect_to_section_detail(
            section_id=section_id,
            error=(
                "You do not have permission to manage "
                "this section's members."
            ),
        )

    return _redirect_to_section_members(
        section_id=section_id,
        success=(
            f"{display_name} was removed from the section."
        ),
    )


def _render_section_members_page(
    *,
    request: Request,
    db: DatabaseSession,
    current_user: object,
    section: object,
    form: SectionMembershipCreateForm,
    csrf_token: str,
    status_code: int,
) -> HTMLResponse:
    memberships = SectionMembershipRepository.list_for_section(
        db,
        section_id=section.id,
    )

    company_memberships = (
        CompanyMembershipRepository.list_for_company(
            db,
            company_id=section.company_id,
        )
    )

    company_membership_map = {
        membership.user_id: membership
        for membership in company_memberships
    }

    available_users = _get_available_section_users(
        company_memberships=company_memberships,
        section_memberships=memberships,
    )

    return templates.TemplateResponse(
        request=request,
        name="sections/members.html",
        context={
            "current_user": current_user,
            "section": section,
            "memberships": memberships,
            "company_memberships": company_membership_map,
            "available_users": available_users,
            "form": form,
            "csrf_token": csrf_token,
            "flash_messages": [],
        },
        status_code=status_code,
    )


def _get_company_membership_map(
    db: DatabaseSession,
    *,
    company_id: int,
) -> dict[int, CompanyMembership]:
    memberships = CompanyMembershipRepository.list_for_company(
        db,
        company_id=company_id,
    )

    return {
        membership.user_id: membership
        for membership in memberships
    }


def _get_available_section_users(
    *,
    company_memberships: list[CompanyMembership],
    section_memberships: list[SectionMembership],
) -> list[object]:
    assigned_user_ids = {
        membership.user_id
        for membership in section_memberships
    }

    available_users = [
        membership.user
        for membership in company_memberships
        if (
            membership.user_id not in assigned_user_ids
            and membership.user.can_authenticate
        )
    ]

    return sorted(
        available_users,
        key=lambda user: (
            user.display_name.casefold(),
            user.username.casefold(),
            user.id,
        ),
    )



def _get_available_task_assignees(
    *,
    section: object,
    section_memberships: list[SectionMembership],
) -> list[object]:
    """
    Return active users who may be selected as task assignees in the section.

    The section creator has implicit section access and therefore remains
    eligible even when they do not have an explicit SectionMembership row.
    """
    users_by_id = {
        membership.user.id: membership.user
        for membership in section_memberships
        if membership.user.can_authenticate
    }

    if section.created_by.can_authenticate:
        users_by_id[section.created_by.id] = section.created_by

    return sorted(
        users_by_id.values(),
        key=lambda user: (
            user.display_name.casefold(),
            user.username.casefold(),
            user.id,
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


def _redirect_to_section_detail(
    *,
    section_id: int,
    success: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    return _redirect_with_messages(
        url=f"/sections/{section_id}",
        success=success,
        error=error,
    )


def _redirect_to_section_members(
    *,
    section_id: int,
    success: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    return _redirect_with_messages(
        url=f"/sections/{section_id}/members",
        success=success,
        error=error,
    )


def _redirect_with_messages(
    *,
    url: str,
    success: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    query_parameters: dict[str, str] = {}

    if success:
        query_parameters["success"] = success

    if error:
        query_parameters["error"] = error

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


def _get_authenticated_csrf_cookie_name() -> str:
    return f"{settings.session_cookie_name}_csrf"


def _get_authenticated_csrf_token(
    request: Request,
) -> str:
    return request.cookies.get(
        _get_authenticated_csrf_cookie_name(),
        "",
    )


def _get_form_value(
    form_data: object,
    field_name: str,
) -> str | None:
    getter = getattr(
        form_data,
        "get",
        None,
    )

    if getter is None:
        return None

    raw_value = getter(
        field_name,
    )

    if raw_value is None:
        return None

    value = str(
        raw_value,
    ).strip()

    return value or None