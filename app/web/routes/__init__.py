from app.web.routes.admin_users import router as admin_users_router
from app.web.routes.auth import router as auth_router

__all__ = [
    "admin_users_router",
    "auth_router",
]