import pytest
from sqlalchemy.orm import Session

from app.auth.permissions import (
    PermissionDeniedError,
    PermissionService,
)
from tests.factories import (
    create_administrator,
    create_user,
)


@pytest.mark.parametrize(
    "permission_method",
    [
        PermissionService.can_access_administration,
        PermissionService.can_view_archived_companies,
        PermissionService.can_view_archived_sections,
        PermissionService.can_view_deleted_tasks,
        PermissionService.can_manage_users,
        PermissionService.can_view_audit_log,
        PermissionService.can_view_audit_log_entry,
    ],
)
def test_administrator_has_administration_permissions(
    db: Session,
    permission_method,
) -> None:
    administrator = create_administrator(
        db,
    )

    assert permission_method(
        actor=administrator,
    ) is True


@pytest.mark.parametrize(
    "permission_method",
    [
        PermissionService.can_access_administration,
        PermissionService.can_view_archived_companies,
        PermissionService.can_view_archived_sections,
        PermissionService.can_view_deleted_tasks,
        PermissionService.can_manage_users,
        PermissionService.can_view_audit_log,
        PermissionService.can_view_audit_log_entry,
    ],
)
def test_standard_user_lacks_administration_permissions(
    db: Session,
    permission_method,
) -> None:
    user = create_user(
        db,
    )

    assert permission_method(
        actor=user,
    ) is False


def test_inactive_administrator_lacks_administration_access(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        is_active=False,
    )

    assert (
        PermissionService.can_access_administration(
            actor=administrator,
        )
        is False
    )


def test_anonymised_administrator_lacks_administration_access(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        is_active=False,
        is_anonymised=True,
    )

    assert (
        PermissionService.can_access_administration(
            actor=administrator,
        )
        is False
    )


def test_administrator_can_deactivate_other_active_user(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    user = create_user(
        db,
    )

    assert (
        PermissionService.can_deactivate_user(
            actor=administrator,
            target_user=user,
        )
        is True
    )


def test_administrator_cannot_deactivate_self(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    assert (
        PermissionService.can_deactivate_user(
            actor=administrator,
            target_user=administrator,
        )
        is False
    )


def test_administrator_can_reactivate_inactive_user(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    user = create_user(
        db,
        is_active=False,
    )

    assert (
        PermissionService.can_reactivate_user(
            actor=administrator,
            target_user=user,
        )
        is True
    )


def test_administrator_cannot_reactivate_anonymised_user(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    user = create_user(
        db,
        is_active=False,
        is_anonymised=True,
    )

    assert (
        PermissionService.can_reactivate_user(
            actor=administrator,
            target_user=user,
        )
        is False
    )


def test_administrator_can_anonymise_inactive_user(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    user = create_user(
        db,
        is_active=False,
    )

    assert (
        PermissionService.can_anonymise_user(
            actor=administrator,
            target_user=user,
        )
        is True
    )


def test_active_user_cannot_be_anonymised(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    user = create_user(
        db,
        is_active=True,
    )

    assert (
        PermissionService.can_anonymise_user(
            actor=administrator,
            target_user=user,
        )
        is False
    )


def test_standard_user_cannot_manage_another_user(
    db: Session,
) -> None:
    actor = create_user(
        db,
    )

    target = create_user(
        db,
        is_active=False,
    )

    assert (
        PermissionService.can_anonymise_user(
            actor=actor,
            target_user=target,
        )
        is False
    )

    assert (
        PermissionService.can_reactivate_user(
            actor=actor,
            target_user=target,
        )
        is False
    )


@pytest.mark.parametrize(
    "requirement_method",
    [
        PermissionService.require_administration_access,
        PermissionService.require_archived_company_access,
        PermissionService.require_archived_section_access,
        PermissionService.require_deleted_task_access,
        PermissionService.require_user_management,
        PermissionService.require_audit_log_access,
        PermissionService.require_audit_log_entry_access,
    ],
)
def test_administration_requirements_reject_standard_user(
    db: Session,
    requirement_method,
) -> None:
    user = create_user(
        db,
    )

    with pytest.raises(
        PermissionDeniedError,
    ):
        requirement_method(
            actor=user,
        )