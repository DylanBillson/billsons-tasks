from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.auth.permissions import PermissionService
from app.core.constants import AuditAction
from app.core.timezone import utc_now
from app.models.company import Company
from app.models.user import User
from app.repositories.company_repository import (
    CompanyRepository,
)
from app.schemas.company import (
    CompanyCreateRequest,
    CompanyUpdateRequest,
)
from app.services.audit_service import AuditService
from app.services.dashboard_service import DashboardService


class CompanyServiceError(ValueError):
    """Base exception for company-service failures."""


class CompanyNotFoundError(CompanyServiceError):
    """Raised when a company cannot be found."""


class CompanyNameAlreadyExistsError(CompanyServiceError):
    """Raised when another company already uses the requested name."""


class CompanyDashboardError(CompanyServiceError):
    """Raised when company-dashboard arguments are invalid."""


class CompanyService:
    @staticmethod
    def get_company(
        db: Session,
        *,
        company_id: int,
    ) -> Company | None:
        return CompanyRepository.get_by_id(
            db,
            company_id,
        )

    @staticmethod
    def require_company(
        db: Session,
        *,
        company_id: int,
    ) -> Company:
        company = CompanyService.get_company(
            db,
            company_id=company_id,
        )

        if company is None:
            raise CompanyNotFoundError(
                "Company was not found.",
            )

        return company

    @staticmethod
    def get_accessible_company(
        db: Session,
        *,
        actor: User,
        company_id: int,
    ) -> Company:
        company = CompanyService.require_company(
            db,
            company_id=company_id,
        )

        PermissionService.require_company_access(
            db,
            actor=actor,
            company=company,
        )

        return company

    @staticmethod
    def list_companies_for_actor(
        db: Session,
        *,
        actor: User,
        include_archived: bool = False,
    ) -> list[Company]:
        if actor.is_administrator:
            return CompanyRepository.list_all(
                db,
                include_archived=include_archived,
            )

        return CompanyRepository.list_for_user(
            db,
            user_id=actor.id,
            include_archived=include_archived,
        )

    @staticmethod
    def get_company_dashboard(
        db: Session,
        *,
        actor: User,
        company_id: int,
        due_soon_days: int = 7,
        task_limit: int = 10,
    ) -> dict[str, Any]:
        if due_soon_days < 1:
            raise CompanyDashboardError(
                "The due-soon period must be at least one day.",
            )

        if task_limit < 1:
            raise CompanyDashboardError(
                "The task limit must be at least one.",
            )

        company = CompanyService.get_accessible_company(
            db,
            actor=actor,
            company_id=company_id,
        )

        generated_at = utc_now()

        metrics = CompanyRepository.get_dashboard_metrics(
            db,
            company_id=company.id,
            actor=actor,
            now=generated_at,
        )

        due_soon_tasks = (
            CompanyRepository.list_dashboard_due_soon_tasks(
                db,
                company_id=company.id,
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
        )

        recent_tasks = (
            CompanyRepository.list_dashboard_recent_tasks(
                db,
                company_id=company.id,
                actor=actor,
                limit=task_limit,
            )
        )

        return {
            "company": company,
            "generated_at": generated_at,
            "metrics": metrics,
            "due_soon_tasks": [
                DashboardService._build_task_summary(
                    task,
                )
                for task in due_soon_tasks
            ],
            "recent_tasks": [
                DashboardService._build_task_summary(
                    task,
                )
                for task in recent_tasks
            ],
        }

    @staticmethod
    def create_company(
        db: Session,
        *,
        actor: User,
        company_create: CompanyCreateRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> Company:
        PermissionService.require_company_creation(
            actor=actor,
        )

        existing_company = CompanyRepository.get_by_name(
            db,
            company_create.name,
        )

        if existing_company is not None:
            raise CompanyNameAlreadyExistsError(
                "A company with this name already exists.",
            )

        company = CompanyRepository.create(
            db,
            name=company_create.name,
            description=company_create.description,
        )

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.COMPANY_CREATED,
            summary=(
                f"{actor.display_name} created {company.name}."
            ),
            entity_type="company",
            entity_id=company.id,
            metadata_json={
                "name": company.name,
                "description": company.description,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()
            db.refresh(
                company,
            )

        return company

    @staticmethod
    def update_company(
        db: Session,
        *,
        actor: User,
        company: Company,
        company_update: CompanyUpdateRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> Company:
        PermissionService.require_company_management(
            actor=actor,
            company=company,
        )

        existing_company = CompanyRepository.get_by_name(
            db,
            company_update.name,
        )

        if (
            existing_company is not None
            and existing_company.id != company.id
        ):
            raise CompanyNameAlreadyExistsError(
                "A company with this name already exists.",
            )

        previous_name = company.name
        previous_description = company.description

        CompanyRepository.update(
            db,
            company=company,
            name=company_update.name,
            description=company_update.description,
        )

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.COMPANY_UPDATED,
            summary=(
                f"{actor.display_name} updated {company.name}."
            ),
            entity_type="company",
            entity_id=company.id,
            metadata_json={
                "previous_name": previous_name,
                "name": company.name,
                "previous_description": previous_description,
                "description": company.description,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()
            db.refresh(
                company,
            )

        return company

    @staticmethod
    def update_company_by_id(
        db: Session,
        *,
        actor: User,
        company_id: int,
        company_update: CompanyUpdateRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> Company:
        company = CompanyService.require_company(
            db,
            company_id=company_id,
        )

        return CompanyService.update_company(
            db,
            actor=actor,
            company=company,
            company_update=company_update,
            ip_address=ip_address,
            user_agent=user_agent,
            commit=commit,
        )

    @staticmethod
    def set_archived_status(
        db: Session,
        *,
        actor: User,
        company: Company,
        is_archived: bool,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> Company:
        PermissionService.require_company_management(
            actor=actor,
            company=company,
        )

        if company.is_archived == is_archived:
            return company

        CompanyRepository.set_archived(
            db,
            company=company,
            is_archived=is_archived,
        )

        action = (
            AuditAction.COMPANY_ARCHIVED
            if is_archived
            else AuditAction.COMPANY_RESTORED
        )

        verb = (
            "archived"
            if is_archived
            else "restored"
        )

        AuditService.record(
            db,
            user=actor,
            action=action,
            summary=(
                f"{actor.display_name} {verb} {company.name}."
            ),
            entity_type="company",
            entity_id=company.id,
            metadata_json={
                "name": company.name,
                "is_archived": is_archived,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            db.commit()
            db.refresh(
                company,
            )

        return company

    @staticmethod
    def set_archived_status_by_id(
        db: Session,
        *,
        actor: User,
        company_id: int,
        is_archived: bool,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> Company:
        company = CompanyService.require_company(
            db,
            company_id=company_id,
        )

        return CompanyService.set_archived_status(
            db,
            actor=actor,
            company=company,
            is_archived=is_archived,
            ip_address=ip_address,
            user_agent=user_agent,
            commit=commit,
        )

    @staticmethod
    def delete_company(
        db: Session,
        *,
        actor: User,
        company: Company,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> None:
        PermissionService.require_company_management(
            actor=actor,
            company=company,
        )

        company_id = company.id
        company_name = company.name

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.COMPANY_DELETED,
            summary=(
                f"{actor.display_name} deleted {company_name}."
            ),
            entity_type="company",
            entity_id=company_id,
            metadata_json={
                "name": company_name,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        CompanyRepository.delete(
            db,
            company=company,
        )

        if commit:
            db.commit()