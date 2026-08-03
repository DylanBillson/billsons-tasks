from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.timezone import utc_now
from app.models.task import Task
from app.models.user import User
from app.repositories.dashboard_repository import (
    DashboardRepository,
)
from app.schemas.dashboard import (
    DashboardCompanySummary,
    DashboardData,
    DashboardMetrics,
    DashboardTaskSummary,
)


class DashboardServiceError(ValueError):
    """Base exception for dashboard-service failures."""


class DashboardAccessError(DashboardServiceError):
    """Raised when an inactive user attempts to access a dashboard."""


class DashboardService:
    @staticmethod
    def get_dashboard(
        db: Session,
        *,
        actor: User,
        due_soon_days: int = 7,
        company_limit: int = 20,
        task_limit: int = 10,
    ) -> DashboardData:
        if not actor.can_authenticate:
            raise DashboardAccessError(
                "An active user account is required to view the dashboard.",
            )

        if due_soon_days < 1:
            raise DashboardServiceError(
                "The due-soon period must be at least one day.",
            )

        if company_limit < 1:
            raise DashboardServiceError(
                "The company limit must be at least one.",
            )

        if task_limit < 1:
            raise DashboardServiceError(
                "The task limit must be at least one.",
            )

        generated_at = utc_now()

        metrics_data = DashboardRepository.get_metrics(
            db,
            actor=actor,
            now=generated_at,
        )

        company_rows = DashboardRepository.list_company_summaries(
            db,
            actor=actor,
            now=generated_at,
            limit=company_limit,
        )

        due_soon_tasks = DashboardRepository.list_due_soon_tasks(
            db,
            actor=actor,
            due_from=generated_at,
            due_to=(
                generated_at
                + timedelta(
                    days=due_soon_days,
                )
            ),
            limit=task_limit,
        )

        recent_tasks = DashboardRepository.list_recent_tasks(
            db,
            actor=actor,
            limit=task_limit,
        )

        return DashboardData(
            generated_at=generated_at,
            is_administrator_view=actor.is_administrator,
            metrics=DashboardMetrics(
                company_count=int(
                    metrics_data["company_count"]
                    or 0,
                ),
                section_count=int(
                    metrics_data["section_count"]
                    or 0,
                ),
                active_user_count=(
                    int(
                        metrics_data["active_user_count"],
                    )
                    if metrics_data["active_user_count"]
                    is not None
                    else None
                ),
                open_task_count=int(
                    metrics_data["open_task_count"]
                    or 0,
                ),
                overdue_task_count=int(
                    metrics_data["overdue_task_count"]
                    or 0,
                ),
                completed_task_count=int(
                    metrics_data["completed_task_count"]
                    or 0,
                ),
                deleted_task_count=int(
                    metrics_data["deleted_task_count"]
                    or 0,
                ),
            ),
            companies=[
                DashboardCompanySummary(
                    **company_row,
                )
                for company_row in company_rows
            ],
            due_soon_tasks=[
                DashboardService._build_task_summary(
                    task,
                )
                for task in due_soon_tasks
            ],
            recent_tasks=[
                DashboardService._build_task_summary(
                    task,
                )
                for task in recent_tasks
            ],
        )

    @staticmethod
    def _build_task_summary(
        task: Task,
    ) -> DashboardTaskSummary:
        section_list = task.section_list
        section = section_list.section
        company = section.company

        return DashboardTaskSummary(
            id=task.id,
            title=task.title,
            company_id=company.id,
            company_name=company.name,
            section_id=section.id,
            section_name=section.name,
            section_list_id=section_list.id,
            section_list_name=section_list.name,
            due_at=task.due_at,
            updated_at=task.updated_at,
            state=task.state,
            assignee_names=[
                assignment.user.display_name
                for assignment in task.assignees
            ],
        )