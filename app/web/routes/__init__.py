from app.web.routes.admin import (
    router as admin_router,
)
from app.web.routes.admin_audit import (
    router as admin_audit_router,
)
from app.web.routes.admin_archived_companies import (
    router as admin_archived_companies_router,
)
from app.web.routes.admin_archived_sections import (
    router as admin_archived_sections_router,
)
from app.web.routes.admin_companies import (
    router as admin_companies_router,
)
from app.web.routes.admin_deleted_tasks import (
    router as admin_deleted_tasks_router,
)
from app.web.routes.admin_users import (
    router as admin_users_router,
)
from app.web.routes.auth import (
    router as auth_router,
)
from app.web.routes.comments import (
    router as comments_router,
)
from app.web.routes.companies import (
    router as companies_router,
)
from app.web.routes.home import (
    router as home_router,
)
from app.web.routes.my_tasks import (
    router as my_tasks_router,
)
from app.web.routes.section_lists import (
    router as section_lists_router,
)
from app.web.routes.sections import (
    router as sections_router,
)
from app.web.routes.tasks import (
    router as tasks_router,
)


__all__ = [
    "admin_audit_router",
    "admin_archived_companies_router",
    "admin_archived_sections_router",
    "admin_companies_router",
    "admin_deleted_tasks_router",
    "admin_router",
    "admin_users_router",
    "auth_router",
    "comments_router",
    "companies_router",
    "home_router",
    "my_tasks_router",
    "section_lists_router",
    "sections_router",
    "tasks_router",
]