"""
Application entry point for Billson's Tasks.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlencode

from fastapi import FastAPI, Request
from fastapi.responses import (
    JSONResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.web.dependencies.auth import (
    AuthenticationRequiredError,
)
from app.web.routes import (
    admin_audit_router,
    admin_archived_companies_router,
    admin_archived_sections_router,
    admin_companies_router,
    admin_deleted_tasks_router,
    admin_router,
    admin_users_router,
    auth_router,
    comments_router,
    companies_router,
    feedback_router,
    home_router,
    my_tasks_router,
    section_lists_router,
    sections_router,
    tasks_router,
)
from app.web.routes.health import router as health_router


logging.basicConfig(
    level=settings.log_level.upper(),
    format=(
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s"
    ),
)

logger = logging.getLogger(
    __name__,
)


@asynccontextmanager
async def lifespan(
    app: FastAPI,
) -> AsyncIterator[None]:
    logger.info(
        "Starting %s in %s mode",
        settings.app_name,
        settings.app_env,
    )

    yield

    logger.info(
        "Stopping %s",
        settings.app_name,
    )


app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    docs_url=(
        "/docs"
        if settings.app_debug
        else None
    ),
    redoc_url=(
        "/redoc"
        if settings.app_debug
        else None
    ),
    openapi_url=(
        "/openapi.json"
        if settings.app_debug
        else None
    ),
    lifespan=lifespan,
)


@app.exception_handler(
    AuthenticationRequiredError,
)
async def authentication_required_handler(
    request: Request,
    exc: AuthenticationRequiredError,
) -> Response:
    """
    Redirect browser page requests to the login page.

    Non-browser and API-style requests continue to receive a normal JSON
    401 response.
    """
    accept_header = request.headers.get(
        "accept",
        "",
    ).lower()

    is_api_request = (
        request.url.path == "/api"
        or request.url.path.startswith(
            "/api/",
        )
    )

    accepts_html = (
        "text/html"
        in accept_header
    )

    if accepts_html and not is_api_request:
        next_url = request.url.path

        if request.url.query:
            next_url = (
                f"{next_url}?"
                f"{request.url.query}"
            )

        login_url = (
            "/login?"
            + urlencode(
                {
                    "next_url": next_url,
                },
            )
        )

        return RedirectResponse(
            url=login_url,
            status_code=303,
        )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
        },
        headers=exc.headers,
    )


app.mount(
    "/static",
    StaticFiles(
        directory="app/web/static",
    ),
    name="static",
)


app.include_router(
    health_router,
)

app.include_router(
    auth_router,
)

app.include_router(
    home_router,
)

app.include_router(
    companies_router,
)

app.include_router(
    sections_router,
)

app.include_router(
    section_lists_router,
)

app.include_router(
    tasks_router,
)

app.include_router(
    comments_router,
)

app.include_router(
    my_tasks_router,
)

app.include_router(
    feedback_router,
)

app.include_router(
    admin_router,
)

app.include_router(
    admin_users_router,
)

app.include_router(
    admin_companies_router,
)

app.include_router(
    admin_archived_companies_router,
)

app.include_router(
    admin_archived_sections_router,
)

app.include_router(
    admin_deleted_tasks_router,
)

app.include_router(
    admin_audit_router,
)