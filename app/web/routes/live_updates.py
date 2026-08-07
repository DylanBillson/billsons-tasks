from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.auth.permissions import PermissionDeniedError
from app.core.config import settings
from app.services.live_update_service import (
    LiveUpdateResourceNotFoundError,
    LiveUpdateService,
)
from app.web.dependencies.auth import (
    CurrentUser,
    DatabaseSession,
)


router = APIRouter(
    prefix="/api/live-updates",
    tags=[
        "live updates",
    ],
)


@router.get(
    "/sections/{section_id}/revision",
    response_class=JSONResponse,
    name="section_live_update_revision",
)
def get_section_live_update_revision(
    section_id: int,
    db: DatabaseSession,
    current_user: CurrentUser,
    known_revision: str | None = None,
) -> JSONResponse:
    unavailable_response = _live_updates_unavailable_response()

    if unavailable_response is not None:
        return unavailable_response

    try:
        current = LiveUpdateService.get_section_revision(
            db,
            actor=current_user,
            section_id=section_id,
        )

    except (
        LiveUpdateResourceNotFoundError,
        PermissionDeniedError,
    ):
        return _resource_not_found_response()

    return _revision_response(
        scope=current.scope.value,
        resource_id=current.resource_id,
        revision=current.revision,
        known_revision=known_revision,
    )


@router.get(
    "/tasks/{task_id}/revision",
    response_class=JSONResponse,
    name="task_live_update_revision",
)
def get_task_live_update_revision(
    task_id: int,
    db: DatabaseSession,
    current_user: CurrentUser,
    known_revision: str | None = None,
) -> JSONResponse:
    unavailable_response = _live_updates_unavailable_response()

    if unavailable_response is not None:
        return unavailable_response

    try:
        current = LiveUpdateService.get_task_revision(
            db,
            actor=current_user,
            task_id=task_id,
        )

    except (
        LiveUpdateResourceNotFoundError,
        PermissionDeniedError,
    ):
        return _resource_not_found_response()

    return _revision_response(
        scope=current.scope.value,
        resource_id=current.resource_id,
        revision=current.revision,
        known_revision=known_revision,
    )


def _revision_response(
    *,
    scope: str,
    resource_id: int,
    revision: str,
    known_revision: str | None,
) -> JSONResponse:
    changed = (
        known_revision is not None
        and known_revision != revision
    )

    return JSONResponse(
        {
            "enabled": True,
            "scope": scope,
            "resource_id": resource_id,
            "revision": revision,
            "changed": changed,
            "poll_interval_seconds": (
                settings.live_updates_poll_interval_seconds
            ),
        },
        status_code=status.HTTP_200_OK,
        headers={
            "Cache-Control": (
                "no-store, no-cache, must-revalidate"
            ),
        },
    )


def _live_updates_unavailable_response(
) -> JSONResponse | None:
    if settings.live_updates_enabled:
        return None

    return JSONResponse(
        {
            "detail": "Live updates are disabled.",
            "code": "live_updates_disabled",
        },
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        headers={
            "Cache-Control": "no-store",
        },
    )


def _resource_not_found_response() -> JSONResponse:
    return JSONResponse(
        {
            "detail": (
                "The requested live-update resource "
                "could not be found."
            ),
        },
        status_code=status.HTTP_404_NOT_FOUND,
        headers={
            "Cache-Control": "no-store",
        },
    )