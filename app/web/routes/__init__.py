from app.web.routes.admin_companies import (
    router as admin_companies_router,
)
from app.web.routes.admin_users import (
    router as admin_users_router,
)
from app.web.routes.auth import (
    router as auth_router,
)
from app.web.routes.companies import (
    router as companies_router,
)
from app.web.routes.sections import (
    router as sections_router,
)


__all__ = [
    "admin_companies_router",
    "admin_users_router",
    "auth_router",
    "companies_router",
    "sections_router",
]