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


ADMINISTRATION_PERMISSION_METHODS = [
    PermissionService.can_access_administration,
    PermissionService.can_view_archived_companies,
    PermissionService.can_view_archived_sections,
    PermissionService.can_view_deleted_tasks,
    PermissionService.can_manage_users,
    PermissionService.can_view_audit_log,
    PermissionService.can_view_audit_log_entry,
]


ADMINISTRATION_REQUIREMENT_METHODS = [
    PermissionService.require_administration_access,
    PermissionService.require_archived_company_access,
    PermissionService.require_archived_section_access,
    PermissionService.require_deleted_task_access,
    PermissionService.require_user_management,
    PermissionService.require_audit_log_access,
    PermissionService.require_audit_log_entry_access,
]


@pytest.mark.parametrize(
    "permission_method",
    ADMINISTRATION_PERMISSION_METHODS,
)
def test_active_administrator_has_administration_permissions(
    db: Session,
    permission_method,
) -> None:
    administrator = create_administrator(
        db,
        is_active=True,
        is_anonymised=False,
    )

    assert permission_method(
        actor=administrator,
    ) is True


@pytest.mark.parametrize(
    "requirement_method",
    ADMINISTRATION_REQUIREMENT_METHODS,
)
def test_active_administrator_satisfies_administration_requirements(
    db: Session,
    requirement_method,
) -> None:
    administrator = create_administrator(
        db,
        is_active=True,
        is_anonymised=False,
    )

    requirement_method(
        actor=administrator,
    )


@pytest.mark.parametrize(
    "permission_method",
    ADMINISTRATION_PERMISSION_METHODS,
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


@pytest.mark.parametrize(
    "requirement_method",
    ADMINISTRATION_REQUIREMENT_METHODS,
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


@pytest.mark.parametrize(
    "permission_method",
    ADMINISTRATION_PERMISSION_METHODS,
)
def test_inactive_administrator_lacks_administration_permissions(
    db: Session,
    permission_method,
) -> None:
    administrator = create_administrator(
        db,
        is_active=False,
        is_anonymised=False,
    )

    assert permission_method(
        actor=administrator,
    ) is False


@pytest.mark.parametrize(
    "requirement_method",
    ADMINISTRATION_REQUIREMENT_METHODS,
)
def test_administration_requirements_reject_inactive_administrator(
    db: Session,
    requirement_method,
) -> None:
    administrator = create_administrator(
        db,
        is_active=False,
        is_anonymised=False,
    )

    with pytest.raises(
        PermissionDeniedError,
    ):
        requirement_method(
            actor=administrator,
        )


@pytest.mark.parametrize(
    "permission_method",
    ADMINISTRATION_PERMISSION_METHODS,
)
def test_anonymised_administrator_lacks_administration_permissions(
    db: Session,
    permission_method,
) -> None:
    administrator = create_administrator(
        db,
        is_active=False,
        is_anonymised=True,
    )

    assert permission_method(
        actor=administrator,
    ) is False


@pytest.mark.parametrize(
    "requirement_method",
    ADMINISTRATION_REQUIREMENT_METHODS,
)
def test_administration_requirements_reject_anonymised_administrator(
    db: Session,
    requirement_method,
) -> None:
    administrator = create_administrator(
        db,
        is_active=False,
        is_anonymised=True,
    )

    with pytest.raises(
        PermissionDeniedError,
    ):
        requirement_method(
            actor=administrator,
        )


def test_administrator_has_user_management_permission(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    assert PermissionService.can_manage_users(
        actor=administrator,
    ) is True

    PermissionService.require_user_management(
        actor=administrator,
    )


def test_standard_user_lacks_user_management_permission(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    assert PermissionService.can_manage_users(
        actor=user,
    ) is False

    with pytest.raises(
        PermissionDeniedError,
    ):
        PermissionService.require_user_management(
            actor=user,
        )


def test_inactive_administrator_lacks_user_management_permission(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        is_active=False,
    )

    assert PermissionService.can_manage_users(
        actor=administrator,
    ) is False

    with pytest.raises(
        PermissionDeniedError,
    ):
        PermissionService.require_user_management(
            actor=administrator,
        )


def test_anonymised_administrator_lacks_user_management_permission(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        is_active=False,
        is_anonymised=True,
    )

    assert PermissionService.can_manage_users(
        actor=administrator,
    ) is False

    with pytest.raises(
        PermissionDeniedError,
    ):
        PermissionService.require_user_management(
            actor=administrator,
        )


def test_administrator_can_deactivate_other_active_user(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    user = create_user(
        db,
        is_active=True,
        is_anonymised=False,
    )

    assert PermissionService.can_deactivate_user(
        actor=administrator,
        target_user=user,
    ) is True


def test_administrator_cannot_deactivate_self(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    assert PermissionService.can_deactivate_user(
        actor=administrator,
        target_user=administrator,
    ) is False


def test_administrator_cannot_deactivate_inactive_user(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    user = create_user(
        db,
        is_active=False,
        is_anonymised=False,
    )

    assert PermissionService.can_deactivate_user(
        actor=administrator,
        target_user=user,
    ) is False


def test_administrator_cannot_deactivate_anonymised_user(
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

    assert PermissionService.can_deactivate_user(
        actor=administrator,
        target_user=user,
    ) is False


def test_standard_user_cannot_deactivate_another_user(
    db: Session,
) -> None:
    actor = create_user(
        db,
    )

    target = create_user(
        db,
        is_active=True,
    )

    assert PermissionService.can_deactivate_user(
        actor=actor,
        target_user=target,
    ) is False


def test_inactive_administrator_cannot_deactivate_user(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        is_active=False,
    )

    user = create_user(
        db,
        is_active=True,
    )

    assert PermissionService.can_deactivate_user(
        actor=administrator,
        target_user=user,
    ) is False


def test_administrator_can_reactivate_inactive_user(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    user = create_user(
        db,
        is_active=False,
        is_anonymised=False,
    )

    assert PermissionService.can_reactivate_user(
        actor=administrator,
        target_user=user,
    ) is True


def test_administrator_cannot_reactivate_active_user(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    user = create_user(
        db,
        is_active=True,
        is_anonymised=False,
    )

    assert PermissionService.can_reactivate_user(
        actor=administrator,
        target_user=user,
    ) is False


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

    assert PermissionService.can_reactivate_user(
        actor=administrator,
        target_user=user,
    ) is False


def test_standard_user_cannot_reactivate_another_user(
    db: Session,
) -> None:
    actor = create_user(
        db,
    )

    target = create_user(
        db,
        is_active=False,
    )

    assert PermissionService.can_reactivate_user(
        actor=actor,
        target_user=target,
    ) is False


def test_inactive_administrator_cannot_reactivate_user(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        is_active=False,
    )

    user = create_user(
        db,
        is_active=False,
    )

    assert PermissionService.can_reactivate_user(
        actor=administrator,
        target_user=user,
    ) is False


def test_administrator_can_anonymise_inactive_user(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    user = create_user(
        db,
        is_active=False,
        is_anonymised=False,
    )

    assert PermissionService.can_anonymise_user(
        actor=administrator,
        target_user=user,
    ) is True


def test_active_user_cannot_be_anonymised(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    user = create_user(
        db,
        is_active=True,
        is_anonymised=False,
    )

    assert PermissionService.can_anonymise_user(
        actor=administrator,
        target_user=user,
    ) is False


def test_anonymised_user_cannot_be_anonymised_again(
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

    assert PermissionService.can_anonymise_user(
        actor=administrator,
        target_user=user,
    ) is False


def test_administrator_cannot_anonymise_self(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        is_active=False,
    )

    assert PermissionService.can_anonymise_user(
        actor=administrator,
        target_user=administrator,
    ) is False


def test_standard_user_cannot_anonymise_another_user(
    db: Session,
) -> None:
    actor = create_user(
        db,
    )

    target = create_user(
        db,
        is_active=False,
    )

    assert PermissionService.can_anonymise_user(
        actor=actor,
        target_user=target,
    ) is False


def test_inactive_administrator_cannot_anonymise_user(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
        is_active=False,
    )

    user = create_user(
        db,
        is_active=False,
    )

    assert PermissionService.can_anonymise_user(
        actor=administrator,
        target_user=user,
    ) is False


def test_standard_user_cannot_perform_any_user_lifecycle_action(
    db: Session,
) -> None:
    actor = create_user(
        db,
    )

    active_target = create_user(
        db,
        is_active=True,
    )

    inactive_target = create_user(
        db,
        is_active=False,
    )

    assert PermissionService.can_deactivate_user(
        actor=actor,
        target_user=active_target,
    ) is False

    assert PermissionService.can_reactivate_user(
        actor=actor,
        target_user=inactive_target,
    ) is False

    assert PermissionService.can_anonymise_user(
        actor=actor,
        target_user=inactive_target,
    ) is False