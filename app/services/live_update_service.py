import hashlib
import json

from sqlalchemy.orm import Session

from app.auth.permissions import PermissionService
from app.models.user import User
from app.repositories.live_update_repository import (
    LiveUpdateRepository,
)
from app.repositories.section_repository import (
    SectionRepository,
)
from app.repositories.task_repository import (
    TaskRepository,
)
from app.schemas.live_updates import (
    LiveUpdateRevision,
    LiveUpdateScope,
    SectionLiveUpdateSnapshot,
    TaskLiveUpdateSnapshot,
)


class LiveUpdateServiceError(ValueError):
    """Base exception for live-update failures."""


class LiveUpdateResourceNotFoundError(
    LiveUpdateServiceError
):
    """Raised when the requested live-update resource does not exist."""


class LiveUpdateService:
    @staticmethod
    def get_section_revision(
        db: Session,
        *,
        actor: User,
        section_id: int,
    ) -> LiveUpdateRevision:
        section = SectionRepository.get_by_id(
            db,
            section_id,
        )

        if section is None:
            raise LiveUpdateResourceNotFoundError(
                "Section was not found.",
            )

        PermissionService.require_section_access(
            db,
            actor=actor,
            section=section,
        )

        snapshot = (
            LiveUpdateRepository.get_section_snapshot(
                db,
                section_id=section.id,
            )
        )

        if snapshot is None:
            raise LiveUpdateResourceNotFoundError(
                "Section was not found.",
            )

        return LiveUpdateRevision(
            scope=LiveUpdateScope.SECTION,
            resource_id=section.id,
            revision=LiveUpdateService._build_revision(
                snapshot,
            ),
        )

    @staticmethod
    def get_task_revision(
        db: Session,
        *,
        actor: User,
        task_id: int,
    ) -> LiveUpdateRevision:
        task = TaskRepository.get_by_id(
            db,
            task_id=task_id,
        )

        if task is None:
            raise LiveUpdateResourceNotFoundError(
                "Task was not found.",
            )

        PermissionService.require_task_access(
            db,
            actor=actor,
            task=task,
        )

        snapshot = LiveUpdateRepository.get_task_snapshot(
            db,
            task_id=task.id,
        )

        if snapshot is None:
            raise LiveUpdateResourceNotFoundError(
                "Task was not found.",
            )

        return LiveUpdateRevision(
            scope=LiveUpdateScope.TASK,
            resource_id=task.id,
            revision=LiveUpdateService._build_revision(
                snapshot,
            ),
        )

    @staticmethod
    def section_has_changed(
        db: Session,
        *,
        actor: User,
        section_id: int,
        known_revision: str,
    ) -> bool:
        current_revision = (
            LiveUpdateService.get_section_revision(
                db,
                actor=actor,
                section_id=section_id,
            )
        )

        return (
            current_revision.revision
            != known_revision
        )

    @staticmethod
    def task_has_changed(
        db: Session,
        *,
        actor: User,
        task_id: int,
        known_revision: str,
    ) -> bool:
        current_revision = (
            LiveUpdateService.get_task_revision(
                db,
                actor=actor,
                task_id=task_id,
            )
        )

        return (
            current_revision.revision
            != known_revision
        )

    @staticmethod
    def _build_revision(
        snapshot: (
            SectionLiveUpdateSnapshot
            | TaskLiveUpdateSnapshot
        ),
    ) -> str:
        payload = snapshot.model_dump(
            mode="json",
        )

        serialised = json.dumps(
            payload,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
        ).encode(
            "utf-8",
        )

        return hashlib.sha256(
            serialised,
        ).hexdigest()[:24]