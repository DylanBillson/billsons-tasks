from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse

from app.core.config import settings
from app.services.dashboard_service import (
    DashboardService,
)
from app.web.dependencies.auth import (
    CurrentUser,
    DatabaseSession,
)
from app.web.templating import templates


router = APIRouter(
    tags=[
        "dashboard",
    ],
)


@router.get(
    "/",
    response_class=HTMLResponse,
    name="home",
)
def dashboard(
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
) -> HTMLResponse:
    """
    Display the authenticated user's global dashboard.

    Administrators receive system-wide totals. Standard users receive totals
    and task summaries limited to companies and sections they can access.
    """
    dashboard_data = DashboardService.get_dashboard(
        db,
        actor=current_user,
    )

    return templates.TemplateResponse(
        request=request,
        name="dashboard/index.html",
        context={
            "current_user": current_user,
            "dashboard": dashboard_data,
            "metrics": dashboard_data.metrics,
            "companies": dashboard_data.companies,
            "due_soon_tasks": dashboard_data.due_soon_tasks,
            "recent_tasks": dashboard_data.recent_tasks,
            "csrf_token": _get_authenticated_csrf_token(
                request,
            ),
            "flash_messages": [],
        },
        status_code=status.HTTP_200_OK,
    )


def _get_authenticated_csrf_token(
    request: Request,
) -> str:
    """
    Return the authenticated CSRF token stored alongside the session cookie.
    """
    return request.cookies.get(
        f"{settings.session_cookie_name}_csrf",
        "",
    )