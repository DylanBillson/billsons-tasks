from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.constants import (
    ANONYMISATION_CONFIRMATION_PHRASE,
    AuditAction,
)
from app.core.security import hash_password
from app.core.timezone import utc_now
from app.models.audit_log import AuditLog
from app.models.task_comment import TaskComment
from app.models.task_history_event import TaskHistoryEvent
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.anonymisation import (
    UserAnonymisationPreview,
    UserAnonymisationResult,
)
from app.services.audit_service import AuditService


class AnonymisationServiceError(ValueError):
    """Base exception for anonymisation failures."""


class AnonymisationPermissionError(
    AnonymisationServiceError,
):
    """Raised when the acting user cannot anonymise users."""


class AnonymisationUserNotFoundError(
    AnonymisationServiceError,
):
    """Raised when the target user does not exist."""


class UserMustBeInactiveError(
    AnonymisationServiceError,
):
    """Raised when an active user is selected."""


class UserAlreadyAnonymisedError(
    AnonymisationServiceError,
):
    """Raised when an anonymised user is selected again."""


class SelfAnonymisationError(
    AnonymisationServiceError,
):
    """Raised when an administrator selects their own account."""


class LastAdministratorAnonymisationError(
    AnonymisationServiceError,
):
    """Raised when anonymising the final active administrator."""


class AnonymisationConfirmationError(
    AnonymisationServiceError,
):
    """Raised when the confirmation phrase is incorrect."""


class AnonymisationService:
    @staticmethod
    def get_preview(
        db: Session,
        *,
        actor: User,
        user_id: int,
    ) -> UserAnonymisationPreview:
        target_user = (
            AnonymisationService._require_target_user(
                db,
                actor=actor,
                user_id=user_id,
            )
        )

        now = utc_now()

        return UserAnonymisationPreview(
            user_id=target_user.id,
            username=target_user.username,
            display_name=target_user.display_name,
            company_membership_count=(
                UserRepository.count_company_memberships(
                    db,
                    user_id=target_user.id,
                )
            ),
            section_membership_count=(
                UserRepository.count_section_memberships(
                    db,
                    user_id=target_user.id,
                )
            ),
            task_assignment_count=(
                UserRepository.count_task_assignments(
                    db,
                    user_id=target_user.id,
                )
            ),
            active_session_count=(
                UserRepository.count_active_sessions(
                    db,
                    user_id=target_user.id,
                    now=now,
                )
            ),
            comment_count=int(
                db.scalar(
                    select(
                        func.count(
                            TaskComment.id,
                        ),
                    ).where(
                        TaskComment.user_id
                        == target_user.id,
                    ),
                )
                or 0
            ),
            task_history_event_count=int(
                db.scalar(
                    select(
                        func.count(
                            TaskHistoryEvent.id,
                        ),
                    ).where(
                        TaskHistoryEvent.user_id
                        == target_user.id,
                    ),
                )
                or 0
            ),
        )

    @staticmethod
    def anonymise_user(
        db: Session,
        *,
        actor: User,
        user_id: int,
        confirmation_phrase: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> UserAnonymisationResult:
        target_user = (
            AnonymisationService._require_target_user(
                db,
                actor=actor,
                user_id=user_id,
            )
        )

        if (
            confirmation_phrase.strip()
            != ANONYMISATION_CONFIRMATION_PHRASE
        ):
            raise AnonymisationConfirmationError(
                "Enter ANONYMISE USER exactly to continue.",
            )

        original_username = target_user.username
        original_display_name = (
            target_user.display_name
        )

        anonymised_at = utc_now()

        anonymised_username = (
            UserRepository.build_anonymised_username(
                user_id=target_user.id,
            )
        )

        anonymised_display_name = (
            UserRepository.build_anonymised_display_name(
                user_id=target_user.id,
            )
        )

        removed_task_assignment_count = (
            UserRepository.remove_task_assignments(
                db,
                user_id=target_user.id,
            )
        )

        removed_section_membership_count = (
            UserRepository.remove_section_memberships(
                db,
                user_id=target_user.id,
            )
        )

        removed_company_membership_count = (
            UserRepository.remove_company_memberships(
                db,
                user_id=target_user.id,
            )
        )

        revoked_session_count = (
            UserRepository.revoke_all_sessions(
                db,
                user_id=target_user.id,
                revoked_at=anonymised_at,
            )
        )

        UserRepository.anonymise(
            db,
            user=target_user,
            username=anonymised_username,
            display_name=anonymised_display_name,
            password_hash=hash_password(
                secrets.token_urlsafe(
                    48,
                ),
            ),
            anonymised_at=anonymised_at,
        )

        scrubbed_audit_log_count = (
            AnonymisationService._scrub_audit_logs(
                db,
                target_user_id=target_user.id,
                original_username=original_username,
                original_display_name=(
                    original_display_name
                ),
                anonymised_username=(
                    anonymised_username
                ),
                anonymised_display_name=(
                    anonymised_display_name
                ),
            )
        )

        AuditService.record(
            db,
            user=actor,
            action=AuditAction.USER_ANONYMISED,
            summary=(
                f"{actor.display_name} anonymised "
                f"{anonymised_display_name}."
            ),
            entity_type="user",
            entity_id=target_user.id,
            metadata_json={
                "anonymised_username": (
                    anonymised_username
                ),
                "anonymised_display_name": (
                    anonymised_display_name
                ),
                "removed_company_membership_count": (
                    removed_company_membership_count
                ),
                "removed_section_membership_count": (
                    removed_section_membership_count
                ),
                "removed_task_assignment_count": (
                    removed_task_assignment_count
                ),
                "revoked_session_count": (
                    revoked_session_count
                ),
                "scrubbed_audit_log_count": (
                    scrubbed_audit_log_count
                ),
                "anonymised_at": (
                    anonymised_at.isoformat()
                ),
            },
            ip_address=ip_address,
            user_agent=user_agent,
            commit=False,
        )

        if commit:
            db.commit()
            db.refresh(
                target_user,
            )

        return UserAnonymisationResult(
            user_id=target_user.id,
            anonymised_username=(
                anonymised_username
            ),
            anonymised_display_name=(
                anonymised_display_name
            ),
            anonymised_at=anonymised_at,
            removed_company_membership_count=(
                removed_company_membership_count
            ),
            removed_section_membership_count=(
                removed_section_membership_count
            ),
            removed_task_assignment_count=(
                removed_task_assignment_count
            ),
            revoked_session_count=(
                revoked_session_count
            ),
            scrubbed_audit_log_count=(
                scrubbed_audit_log_count
            ),
        )

    @staticmethod
    def _require_target_user(
        db: Session,
        *,
        actor: User,
        user_id: int,
    ) -> User:
        if not actor.is_administrator:
            raise AnonymisationPermissionError(
                "Administrator access is required.",
            )

        if not actor.can_authenticate:
            raise AnonymisationPermissionError(
                "The administrator account is not available.",
            )

        target_user = UserRepository.get_by_id(
            db,
            user_id=user_id,
        )

        if target_user is None:
            raise AnonymisationUserNotFoundError(
                "The requested user could not be found.",
            )

        if target_user.id == actor.id:
            raise SelfAnonymisationError(
                "You cannot anonymise your own account.",
            )

        if target_user.is_anonymised:
            raise UserAlreadyAnonymisedError(
                "This user has already been anonymised.",
            )

        if target_user.is_active:
            raise UserMustBeInactiveError(
                "The user must be deactivated before anonymisation.",
            )

        return target_user

    @staticmethod
    def _scrub_audit_logs(
        db: Session,
        *,
        target_user_id: int,
        original_username: str,
        original_display_name: str,
        anonymised_username: str,
        anonymised_display_name: str,
    ) -> int:
        audit_logs = list(
            db.scalars(
                select(
                    AuditLog,
                ).where(
                    or_(
                        AuditLog.user_id
                        == target_user_id,
                        (
                            AuditLog.entity_type
                            == "user"
                        )
                        & (
                            AuditLog.entity_id
                            == target_user_id
                        ),
                    ),
                ),
            ).all(),
        )

        changed_count = 0

        replacements = {
            original_username: (
                anonymised_username
            ),
            original_display_name: (
                anonymised_display_name
            ),
        }

        for audit_log in audit_logs:
            original_summary = audit_log.summary
            original_metadata = (
                audit_log.metadata_json
            )

            audit_log.summary = (
                AnonymisationService._replace_identity(
                    original_summary,
                    replacements=replacements,
                )
            )

            audit_log.metadata_json = (
                AnonymisationService._scrub_value(
                    original_metadata,
                    replacements=replacements,
                )
            )

            if (
                audit_log.summary
                != original_summary
                or audit_log.metadata_json
                != original_metadata
            ):
                changed_count += 1

        db.flush()

        return changed_count

    @staticmethod
    def _scrub_value(
        value: Any,
        *,
        replacements: dict[str, str],
    ) -> Any:
        if isinstance(
            value,
            dict,
        ):
            return {
                str(key): (
                    AnonymisationService._scrub_value(
                        nested_value,
                        replacements=replacements,
                    )
                )
                for key, nested_value
                in value.items()
            }

        if isinstance(
            value,
            list,
        ):
            return [
                AnonymisationService._scrub_value(
                    item,
                    replacements=replacements,
                )
                for item in value
            ]

        if isinstance(
            value,
            tuple,
        ):
            return [
                AnonymisationService._scrub_value(
                    item,
                    replacements=replacements,
                )
                for item in value
            ]

        if isinstance(
            value,
            str,
        ):
            return (
                AnonymisationService._replace_identity(
                    value,
                    replacements=replacements,
                )
            )

        return value

    @staticmethod
    def _replace_identity(
        value: str,
        *,
        replacements: dict[str, str],
    ) -> str:
        result = value

        for original, replacement in (
            replacements.items()
        ):
            if original:
                result = result.replace(
                    original,
                    replacement,
                )

        return result