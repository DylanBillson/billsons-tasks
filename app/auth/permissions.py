from sqlalchemy.orm import Session

from app.core.constants import CompanyRole
from app.models.company import Company
from app.models.section import Section
from app.models.section_list import SectionList
from app.models.task import Task
from app.models.user import User
from app.repositories.company_membership_repository import (
    CompanyMembershipRepository,
)
from app.repositories.section_membership_repository import (
    SectionMembershipRepository,
)


class PermissionDeniedError(PermissionError):
    """Raised when an actor is not permitted to perform an operation."""


class PermissionService:
    @staticmethod
    def is_authenticated_user(
        actor: User,
    ) -> bool:
        return actor.can_authenticate

    @staticmethod
    def is_administrator(
        actor: User,
    ) -> bool:
        return (
            actor.can_authenticate
            and actor.is_administrator
        )

    @staticmethod
    def is_company_member(
        db: Session,
        *,
        actor: User,
        company: Company,
    ) -> bool:
        if not actor.can_authenticate:
            return False

        return CompanyMembershipRepository.exists(
            db,
            company_id=company.id,
            user_id=actor.id,
        )

    @staticmethod
    def is_company_manager(
        db: Session,
        *,
        actor: User,
        company: Company,
    ) -> bool:
        if not actor.can_authenticate:
            return False

        membership = (
            CompanyMembershipRepository.get_by_company_and_user(
                db,
                company_id=company.id,
                user_id=actor.id,
            )
        )

        return (
            membership is not None
            and membership.role
            == CompanyRole.MANAGER.value
        )

    @staticmethod
    def is_section_creator(
        *,
        actor: User,
        section: Section,
    ) -> bool:
        return (
            actor.can_authenticate
            and section.created_by_user_id
            == actor.id
        )

    @staticmethod
    def is_section_member(
        db: Session,
        *,
        actor: User,
        section: Section,
    ) -> bool:
        if not actor.can_authenticate:
            return False

        return SectionMembershipRepository.exists(
            db,
            section_id=section.id,
            user_id=actor.id,
        )

    # ------------------------------------------------------------------
    # Dashboard permissions
    # ------------------------------------------------------------------

    @staticmethod
    def can_view_global_dashboard(
        *,
        actor: User,
    ) -> bool:
        return PermissionService.is_authenticated_user(
            actor,
        )

    @staticmethod
    def can_view_company_dashboard(
        db: Session,
        *,
        actor: User,
        company: Company,
    ) -> bool:
        return PermissionService.can_view_company(
            db,
            actor=actor,
            company=company,
        )

    @staticmethod
    def can_view_my_tasks(
        *,
        actor: User,
    ) -> bool:
        return PermissionService.is_authenticated_user(
            actor,
        )

    # ------------------------------------------------------------------
    # Administration permissions
    # ------------------------------------------------------------------

    @staticmethod
    def can_access_administration(
        *,
        actor: User,
    ) -> bool:
        return PermissionService.is_administrator(
            actor,
        )

    @staticmethod
    def can_view_archived_companies(
        *,
        actor: User,
    ) -> bool:
        return PermissionService.can_access_administration(
            actor=actor,
        )

    @staticmethod
    def can_view_archived_sections(
        *,
        actor: User,
    ) -> bool:
        return PermissionService.can_access_administration(
            actor=actor,
        )

    @staticmethod
    def can_view_deleted_tasks(
        *,
        actor: User,
    ) -> bool:
        return PermissionService.can_access_administration(
            actor=actor,
        )

    @staticmethod
    def can_manage_users(
        *,
        actor: User,
    ) -> bool:
        return PermissionService.can_access_administration(
            actor=actor,
        )

    @staticmethod
    def can_deactivate_user(
        *,
        actor: User,
        target_user: User,
    ) -> bool:
        if not PermissionService.can_manage_users(
            actor=actor,
        ):
            return False

        if actor.id == target_user.id:
            return False

        if target_user.is_anonymised:
            return False

        return target_user.is_active

    @staticmethod
    def can_reactivate_user(
        *,
        actor: User,
        target_user: User,
    ) -> bool:
        if not PermissionService.can_manage_users(
            actor=actor,
        ):
            return False

        return (
            not target_user.is_active
            and not target_user.is_anonymised
        )

    @staticmethod
    def can_anonymise_user(
        *,
        actor: User,
        target_user: User,
    ) -> bool:
        if not PermissionService.can_manage_users(
            actor=actor,
        ):
            return False

        if actor.id == target_user.id:
            return False

        return (
            not target_user.is_active
            and not target_user.is_anonymised
        )

    @staticmethod
    def can_view_audit_log(
        *,
        actor: User,
    ) -> bool:
        return PermissionService.can_access_administration(
            actor=actor,
        )

    @staticmethod
    def can_view_audit_log_entry(
        *,
        actor: User,
    ) -> bool:
        return PermissionService.can_view_audit_log(
            actor=actor,
        )

    # ------------------------------------------------------------------
    # Company permissions
    # ------------------------------------------------------------------

    @staticmethod
    def can_view_company(
        db: Session,
        *,
        actor: User,
        company: Company,
    ) -> bool:
        if PermissionService.is_administrator(
            actor,
        ):
            return True

        return PermissionService.is_company_member(
            db,
            actor=actor,
            company=company,
        )

    @staticmethod
    def can_create_company(
        *,
        actor: User,
    ) -> bool:
        return PermissionService.is_administrator(
            actor,
        )

    @staticmethod
    def can_manage_company(
        *,
        actor: User,
        company: Company,
    ) -> bool:
        del company

        return PermissionService.is_administrator(
            actor,
        )

    @staticmethod
    def can_manage_company_memberships(
        db: Session,
        *,
        actor: User,
        company: Company,
    ) -> bool:
        if PermissionService.is_administrator(
            actor,
        ):
            return True

        return PermissionService.is_company_manager(
            db,
            actor=actor,
            company=company,
        )

    # ------------------------------------------------------------------
    # Section permissions
    # ------------------------------------------------------------------

    @staticmethod
    def can_create_section(
        db: Session,
        *,
        actor: User,
        company: Company,
    ) -> bool:
        if not actor.can_authenticate:
            return False

        if company.is_archived:
            return False

        if PermissionService.is_administrator(
            actor,
        ):
            return True

        return PermissionService.is_company_manager(
            db,
            actor=actor,
            company=company,
        )

    @staticmethod
    def can_view_section(
        db: Session,
        *,
        actor: User,
        section: Section,
    ) -> bool:
        if not actor.can_authenticate:
            return False

        if PermissionService.is_administrator(
            actor,
        ):
            return True

        if PermissionService.is_section_creator(
            actor=actor,
            section=section,
        ):
            return True

        return PermissionService.is_section_member(
            db,
            actor=actor,
            section=section,
        )

    @staticmethod
    def can_manage_section(
        db: Session,
        *,
        actor: User,
        section: Section,
    ) -> bool:
        del db

        if PermissionService.is_administrator(
            actor,
        ):
            return True

        return PermissionService.is_section_creator(
            actor=actor,
            section=section,
        )

    @staticmethod
    def can_manage_section_memberships(
        db: Session,
        *,
        actor: User,
        section: Section,
    ) -> bool:
        return PermissionService.can_manage_section(
            db,
            actor=actor,
            section=section,
        )

    # ------------------------------------------------------------------
    # Section-list permissions
    # ------------------------------------------------------------------

    @staticmethod
    def can_view_section_list(
        db: Session,
        *,
        actor: User,
        section_list: SectionList,
    ) -> bool:
        return PermissionService.can_view_section(
            db,
            actor=actor,
            section=section_list.section,
        )

    @staticmethod
    def can_manage_section_list(
        db: Session,
        *,
        actor: User,
        section_list: SectionList,
    ) -> bool:
        if (
            section_list.section.company.is_archived
            or section_list.section.is_archived
        ):
            return False

        return PermissionService.can_manage_section(
            db,
            actor=actor,
            section=section_list.section,
        )

    @staticmethod
    def can_create_section_list(
        db: Session,
        *,
        actor: User,
        section: Section,
    ) -> bool:
        if (
            section.company.is_archived
            or section.is_archived
        ):
            return False

        return PermissionService.can_manage_section(
            db,
            actor=actor,
            section=section,
        )

    @staticmethod
    def can_reorder_section_lists(
        db: Session,
        *,
        actor: User,
        section: Section,
    ) -> bool:
        return PermissionService.can_create_section_list(
            db,
            actor=actor,
            section=section,
        )

    # ------------------------------------------------------------------
    # Task permissions
    # ------------------------------------------------------------------

    @staticmethod
    def can_view_task(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> bool:
        if task.is_deleted:
            return PermissionService.can_restore_task(
                db,
                actor=actor,
                task=task,
            )

        return PermissionService.can_view_section_list(
            db,
            actor=actor,
            section_list=task.section_list,
        )

    @staticmethod
    def can_create_task(
        db: Session,
        *,
        actor: User,
        section_list: SectionList,
    ) -> bool:
        if (
            section_list.section.company.is_archived
            or section_list.section.is_archived
            or section_list.is_archived
        ):
            return False

        return PermissionService.can_view_section_list(
            db,
            actor=actor,
            section_list=section_list,
        )

    @staticmethod
    def can_update_task(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> bool:
        if (
            task.is_deleted
            or task.section_list.section.company.is_archived
            or task.section_list.section.is_archived
            or task.section_list.is_archived
        ):
            return False

        return PermissionService.can_view_section_list(
            db,
            actor=actor,
            section_list=task.section_list,
        )

    @staticmethod
    def can_move_task(
        db: Session,
        *,
        actor: User,
        task: Task,
        destination_list: SectionList,
    ) -> bool:
        if not PermissionService.can_update_task(
            db,
            actor=actor,
            task=task,
        ):
            return False

        if (
            destination_list.section_id
            != task.section_id
        ):
            return False

        return PermissionService.can_create_task(
            db,
            actor=actor,
            section_list=destination_list,
        )

    @staticmethod
    def can_reorder_tasks(
        db: Session,
        *,
        actor: User,
        section: Section,
    ) -> bool:
        if (
            section.company.is_archived
            or section.is_archived
        ):
            return False

        return PermissionService.can_view_section(
            db,
            actor=actor,
            section=section,
        )

    @staticmethod
    def can_complete_task(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> bool:
        return PermissionService.can_update_task(
            db,
            actor=actor,
            task=task,
        )

    @staticmethod
    def can_comment_on_task(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> bool:
        return PermissionService.can_update_task(
            db,
            actor=actor,
            task=task,
        )

    @staticmethod
    def can_manage_task_assignees(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> bool:
        if (
            task.is_deleted
            or task.section_list.section.company.is_archived
            or task.section_list.section.is_archived
            or task.section_list.is_archived
        ):
            return False

        return PermissionService.can_manage_section(
            db,
            actor=actor,
            section=task.section_list.section,
        )

    @staticmethod
    def can_delete_task(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> bool:
        if (
            task.is_deleted
            or task.section_list.section.company.is_archived
            or task.section_list.section.is_archived
        ):
            return False

        return PermissionService.can_manage_section(
            db,
            actor=actor,
            section=task.section_list.section,
        )

    @staticmethod
    def can_restore_task(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> bool:
        if not task.is_deleted:
            return False

        return PermissionService.can_manage_section(
            db,
            actor=actor,
            section=task.section_list.section,
        )

    @staticmethod
    def can_permanently_delete_task(
        *,
        actor: User,
        task: Task,
    ) -> bool:
        return (
            task.is_deleted
            and PermissionService.is_administrator(
                actor,
            )
        )

    # ------------------------------------------------------------------
    # Dashboard requirements
    # ------------------------------------------------------------------

    @staticmethod
    def require_global_dashboard_access(
        *,
        actor: User,
    ) -> None:
        if not PermissionService.can_view_global_dashboard(
            actor=actor,
        ):
            raise PermissionDeniedError(
                "You do not have access to the dashboard.",
            )

    @staticmethod
    def require_company_dashboard_access(
        db: Session,
        *,
        actor: User,
        company: Company,
    ) -> None:
        if not PermissionService.can_view_company_dashboard(
            db,
            actor=actor,
            company=company,
        ):
            raise PermissionDeniedError(
                "You do not have access to this company dashboard.",
            )

    @staticmethod
    def require_my_tasks_access(
        *,
        actor: User,
    ) -> None:
        if not PermissionService.can_view_my_tasks(
            actor=actor,
        ):
            raise PermissionDeniedError(
                "You do not have access to My Tasks.",
            )

    # ------------------------------------------------------------------
    # Administration requirements
    # ------------------------------------------------------------------

    @staticmethod
    def require_administration_access(
        *,
        actor: User,
    ) -> None:
        if not PermissionService.can_access_administration(
            actor=actor,
        ):
            raise PermissionDeniedError(
                "Administrator access is required.",
            )

    @staticmethod
    def require_archived_company_access(
        *,
        actor: User,
    ) -> None:
        if not PermissionService.can_view_archived_companies(
            actor=actor,
        ):
            raise PermissionDeniedError(
                "Administrator access is required to view archived companies.",
            )

    @staticmethod
    def require_archived_section_access(
        *,
        actor: User,
    ) -> None:
        if not PermissionService.can_view_archived_sections(
            actor=actor,
        ):
            raise PermissionDeniedError(
                "Administrator access is required to view archived sections.",
            )

    @staticmethod
    def require_deleted_task_access(
        *,
        actor: User,
    ) -> None:
        if not PermissionService.can_view_deleted_tasks(
            actor=actor,
        ):
            raise PermissionDeniedError(
                "Administrator access is required to view deleted tasks.",
            )

    @staticmethod
    def require_user_management(
        *,
        actor: User,
    ) -> None:
        if not PermissionService.can_manage_users(
            actor=actor,
        ):
            raise PermissionDeniedError(
                "Administrator access is required to manage users.",
            )

    @staticmethod
    def require_user_deactivation(
        *,
        actor: User,
        target_user: User,
    ) -> None:
        if not PermissionService.can_deactivate_user(
            actor=actor,
            target_user=target_user,
        ):
            raise PermissionDeniedError(
                "You do not have permission to deactivate this user.",
            )

    @staticmethod
    def require_user_reactivation(
        *,
        actor: User,
        target_user: User,
    ) -> None:
        if not PermissionService.can_reactivate_user(
            actor=actor,
            target_user=target_user,
        ):
            raise PermissionDeniedError(
                "You do not have permission to reactivate this user.",
            )

    @staticmethod
    def require_user_anonymisation(
        *,
        actor: User,
        target_user: User,
    ) -> None:
        if not PermissionService.can_anonymise_user(
            actor=actor,
            target_user=target_user,
        ):
            raise PermissionDeniedError(
                "You do not have permission to anonymise this user.",
            )

    @staticmethod
    def require_audit_log_access(
        *,
        actor: User,
    ) -> None:
        if not PermissionService.can_view_audit_log(
            actor=actor,
        ):
            raise PermissionDeniedError(
                "Administrator access is required to view the audit log.",
            )

    @staticmethod
    def require_audit_log_entry_access(
        *,
        actor: User,
    ) -> None:
        if not PermissionService.can_view_audit_log_entry(
            actor=actor,
        ):
            raise PermissionDeniedError(
                "Administrator access is required to view this audit entry.",
            )

    # ------------------------------------------------------------------
    # Company requirements
    # ------------------------------------------------------------------

    @staticmethod
    def require_company_access(
        db: Session,
        *,
        actor: User,
        company: Company,
    ) -> None:
        if not PermissionService.can_view_company(
            db,
            actor=actor,
            company=company,
        ):
            raise PermissionDeniedError(
                "You do not have access to this company.",
            )

    @staticmethod
    def require_company_creation(
        *,
        actor: User,
    ) -> None:
        if not PermissionService.can_create_company(
            actor=actor,
        ):
            raise PermissionDeniedError(
                "Only administrators can create companies.",
            )

    @staticmethod
    def require_company_management(
        *,
        actor: User,
        company: Company,
    ) -> None:
        if not PermissionService.can_manage_company(
            actor=actor,
            company=company,
        ):
            raise PermissionDeniedError(
                "Only administrators can manage companies.",
            )

    @staticmethod
    def require_company_membership_management(
        db: Session,
        *,
        actor: User,
        company: Company,
    ) -> None:
        if not PermissionService.can_manage_company_memberships(
            db,
            actor=actor,
            company=company,
        ):
            raise PermissionDeniedError(
                "You do not have permission to manage this company's members.",
            )

    # ------------------------------------------------------------------
    # Section requirements
    # ------------------------------------------------------------------

    @staticmethod
    def require_section_creation(
        db: Session,
        *,
        actor: User,
        company: Company,
    ) -> None:
        if not PermissionService.can_create_section(
            db,
            actor=actor,
            company=company,
        ):
            raise PermissionDeniedError(
                "You do not have permission to create sections in this company.",
            )

    @staticmethod
    def require_section_access(
        db: Session,
        *,
        actor: User,
        section: Section,
    ) -> None:
        if not PermissionService.can_view_section(
            db,
            actor=actor,
            section=section,
        ):
            raise PermissionDeniedError(
                "You do not have access to this section.",
            )

    @staticmethod
    def require_section_management(
        db: Session,
        *,
        actor: User,
        section: Section,
    ) -> None:
        if not PermissionService.can_manage_section(
            db,
            actor=actor,
            section=section,
        ):
            raise PermissionDeniedError(
                "You do not have permission to manage this section.",
            )

    @staticmethod
    def require_section_membership_management(
        db: Session,
        *,
        actor: User,
        section: Section,
    ) -> None:
        if not PermissionService.can_manage_section_memberships(
            db,
            actor=actor,
            section=section,
        ):
            raise PermissionDeniedError(
                "You do not have permission to manage this section's members.",
            )

    # ------------------------------------------------------------------
    # Section-list requirements
    # ------------------------------------------------------------------

    @staticmethod
    def require_section_list_access(
        db: Session,
        *,
        actor: User,
        section_list: SectionList,
    ) -> None:
        if not PermissionService.can_view_section_list(
            db,
            actor=actor,
            section_list=section_list,
        ):
            raise PermissionDeniedError(
                "You do not have access to this list.",
            )

    @staticmethod
    def require_section_list_creation(
        db: Session,
        *,
        actor: User,
        section: Section,
    ) -> None:
        if not PermissionService.can_create_section_list(
            db,
            actor=actor,
            section=section,
        ):
            raise PermissionDeniedError(
                "You do not have permission to create lists in this section.",
            )

    @staticmethod
    def require_section_list_management(
        db: Session,
        *,
        actor: User,
        section_list: SectionList,
    ) -> None:
        if not PermissionService.can_manage_section_list(
            db,
            actor=actor,
            section_list=section_list,
        ):
            raise PermissionDeniedError(
                "You do not have permission to manage this list.",
            )

    @staticmethod
    def require_section_list_reordering(
        db: Session,
        *,
        actor: User,
        section: Section,
    ) -> None:
        if not PermissionService.can_reorder_section_lists(
            db,
            actor=actor,
            section=section,
        ):
            raise PermissionDeniedError(
                "You do not have permission to reorder lists in this section.",
            )

    # ------------------------------------------------------------------
    # Task requirements
    # ------------------------------------------------------------------

    @staticmethod
    def require_task_access(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> None:
        if not PermissionService.can_view_task(
            db,
            actor=actor,
            task=task,
        ):
            raise PermissionDeniedError(
                "You do not have access to this task.",
            )

    @staticmethod
    def require_task_creation(
        db: Session,
        *,
        actor: User,
        section_list: SectionList,
    ) -> None:
        if not PermissionService.can_create_task(
            db,
            actor=actor,
            section_list=section_list,
        ):
            raise PermissionDeniedError(
                "You do not have permission to create tasks in this list.",
            )

    @staticmethod
    def require_task_update(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> None:
        if not PermissionService.can_update_task(
            db,
            actor=actor,
            task=task,
        ):
            raise PermissionDeniedError(
                "You do not have permission to update this task.",
            )

    @staticmethod
    def require_task_movement(
        db: Session,
        *,
        actor: User,
        task: Task,
        destination_list: SectionList,
    ) -> None:
        if not PermissionService.can_move_task(
            db,
            actor=actor,
            task=task,
            destination_list=destination_list,
        ):
            raise PermissionDeniedError(
                "You do not have permission to move this task.",
            )

    @staticmethod
    def require_task_reordering(
        db: Session,
        *,
        actor: User,
        section: Section,
    ) -> None:
        if not PermissionService.can_reorder_tasks(
            db,
            actor=actor,
            section=section,
        ):
            raise PermissionDeniedError(
                "You do not have permission to reorder tasks in this section.",
            )

    @staticmethod
    def require_task_completion(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> None:
        if not PermissionService.can_complete_task(
            db,
            actor=actor,
            task=task,
        ):
            raise PermissionDeniedError(
                "You do not have permission to change this task's completion state.",
            )

    @staticmethod
    def require_task_commenting(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> None:
        if not PermissionService.can_comment_on_task(
            db,
            actor=actor,
            task=task,
        ):
            raise PermissionDeniedError(
                "You do not have permission to comment on this task.",
            )

    @staticmethod
    def require_task_assignee_management(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> None:
        if not PermissionService.can_manage_task_assignees(
            db,
            actor=actor,
            task=task,
        ):
            raise PermissionDeniedError(
                "You do not have permission to manage this task's assignees.",
            )

    @staticmethod
    def require_task_deletion(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> None:
        if not PermissionService.can_delete_task(
            db,
            actor=actor,
            task=task,
        ):
            raise PermissionDeniedError(
                "You do not have permission to delete this task.",
            )

    @staticmethod
    def require_task_restoration(
        db: Session,
        *,
        actor: User,
        task: Task,
    ) -> None:
        if not PermissionService.can_restore_task(
            db,
            actor=actor,
            task=task,
        ):
            raise PermissionDeniedError(
                "You do not have permission to restore this task.",
            )

    @staticmethod
    def require_task_permanent_deletion(
        *,
        actor: User,
        task: Task,
    ) -> None:
        if not PermissionService.can_permanently_delete_task(
            actor=actor,
            task=task,
        ):
            raise PermissionDeniedError(
                "Only administrators can permanently delete a deleted task.",
            )