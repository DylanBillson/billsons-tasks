from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from app.core.config import settings
from app.core.constants import AuditAction
from app.models.audit_log import AuditLog
from app.models.company import Company
from app.models.section import Section
from app.models.task import Task
from app.models.user import User
from app.repositories.audit_repository import AuditRepository
from app.web.dependencies.auth import (
    AdministratorUser,
    DatabaseSession,
)
from app.web.templating import templates


router = APIRouter(
    prefix="/admin",
    tags=[
        "administration",
    ],
)


@router.get(
    "",
    response_class=HTMLResponse,
    name="admin_dashboard",
)
def admin_dashboard(
    request: Request,
    db: DatabaseSession,
    administrator: AdministratorUser,
) -> HTMLResponse:
    metrics = {
        "active_user_count": _count_active_users(
            db,
        ),
        "inactive_user_count": _count_inactive_users(
            db,
        ),
        "anonymised_user_count": (
            _count_anonymised_users(
                db,
            )
        ),
        "active_company_count": (
            _count_active_companies(
                db,
            )
        ),
        "archived_company_count": (
            _count_archived_companies(
                db,
            )
        ),
        "archived_section_count": (
            _count_archived_sections(
                db,
            )
        ),
        "deleted_task_count": (
            _count_deleted_tasks(
                db,
            )
        ),
        "notification_failure_count": (
            _count_notification_failures(
                db,
            )
        ),
    }

    recent_audit_logs = AuditRepository.list_logs(
        db,
        limit=10,
        offset=0,
    )

    return templates.TemplateResponse(
        request=request,
        name="admin/index.html",
        context={
            "current_user": administrator,
            "metrics": metrics,
            "recent_audit_logs": recent_audit_logs,
            "csrf_token": request.cookies.get(
                f"{settings.session_cookie_name}_csrf",
                "",
            ),
            "flash_messages": [],
        },
        status_code=status.HTTP_200_OK,
    )


def _count_active_users(
    db: DatabaseSession,
) -> int:
    query = select(
        func.count(
            User.id,
        ),
    ).where(
        User.is_active.is_(True),
        User.is_anonymised.is_(False),
    )

    return int(
        db.scalar(
            query,
        )
        or 0,
    )


def _count_inactive_users(
    db: DatabaseSession,
) -> int:
    query = select(
        func.count(
            User.id,
        ),
    ).where(
        User.is_active.is_(False),
        User.is_anonymised.is_(False),
    )

    return int(
        db.scalar(
            query,
        )
        or 0,
    )


def _count_anonymised_users(
    db: DatabaseSession,
) -> int:
    query = select(
        func.count(
            User.id,
        ),
    ).where(
        User.is_anonymised.is_(True),
    )

    return int(
        db.scalar(
            query,
        )
        or 0,
    )


def _count_active_companies(
    db: DatabaseSession,
) -> int:
    query = select(
        func.count(
            Company.id,
        ),
    ).where(
        Company.is_archived.is_(False),
    )

    return int(
        db.scalar(
            query,
        )
        or 0,
    )


def _count_archived_companies(
    db: DatabaseSession,
) -> int:
    query = select(
        func.count(
            Company.id,
        ),
    ).where(
        Company.is_archived.is_(True),
    )

    return int(
        db.scalar(
            query,
        )
        or 0,
    )


def _count_archived_sections(
    db: DatabaseSession,
) -> int:
    query = select(
        func.count(
            Section.id,
        ),
    ).where(
        Section.is_archived.is_(True),
    )

    return int(
        db.scalar(
            query,
        )
        or 0,
    )


def _count_deleted_tasks(
    db: DatabaseSession,
) -> int:
    query = select(
        func.count(
            Task.id,
        ),
    ).where(
        Task.deleted_at.is_not(None),
    )

    return int(
        db.scalar(
            query,
        )
        or 0,
    )


def _count_notification_failures(
    db: DatabaseSession,
) -> int:
    query = select(
        func.count(
            AuditLog.id,
        ),
    ).where(
        AuditLog.action
        == AuditAction.NOTIFICATION_FAILED.value,
    )

    return int(
        db.scalar(
            query,
        )
        or 0,
    )