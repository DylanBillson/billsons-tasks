"""
Application entry point for Billson's Tasks.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.web.routes import (
    admin_users_router,
    auth_router,
)
from app.web.routes.health import router as health_router


logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


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
    docs_url="/docs" if settings.app_debug else None,
    redoc_url="/redoc" if settings.app_debug else None,
    openapi_url=(
        "/openapi.json"
        if settings.app_debug
        else None
    ),
    lifespan=lifespan,
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
    admin_users_router,
)