import pytest
from sqlalchemy.orm import Session

from app.auth.permissions import PermissionDeniedError
from app.core.constants import CompanyRole
from app.services.task_permission_service import (
    TaskPermissionService,
)
from tests.factories import (
    create_administrator,
    create_company,
    create_company_membership,
    create_section,
    create_section_list,
    create_section_membership,
    create_task,
    create_user,
)


def _create_context(
    db: Session,
):
    company = create_company(
        db,
    )

    section_creator = create_user(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=section_creator,
        role=CompanyRole.MANAGER,
    )

    section = create_section(
        db,
        company=company,
        created_by=section_creator,
    )

    first_list = create_section_list(
        db,
        section=section,
        name="To Do",
        sort_position=1000,
    )

    second_list = create_section_list(
        db,
        section=section,
        name="In Progress",
        sort_position=2000,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=section_creator,
    )

    return (
        company,
        section_creator,
        section,
        first_list,
        second_list,
        task,
    )


def _create_section_member(
    db: Session,
    *,
    company,
    section,
):
    member = create_user(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=member,
        role=CompanyRole.EMPLOYEE,
    )

    create_section_membership(
        db,
        section=section,
        user=member,
    )

    return member


def test_administrator_can_view_task(
    db: Session,
) -> None:
    (
        _,
        _,
        _,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    administrator = create_administrator(
        db,
    )

    assert TaskPermissionService.can_view(
        db,
        actor=administrator,
        task=task,
    ) is True


def test_section_creator_can_view_task(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    assert TaskPermissionService.can_view(
        db,
        actor=creator,
        task=task,
    ) is True


def test_explicit_section_member_can_view_task(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    assert TaskPermissionService.can_view(
        db,
        actor=member,
        task=task,
    ) is True


def test_company_manager_cannot_view_unassigned_section_task(
    db: Session,
) -> None:
    (
        company,
        _,
        _,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    manager = create_user(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    assert TaskPermissionService.can_view(
        db,
        actor=manager,
        task=task,
    ) is False


def test_inactive_user_cannot_view_task(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    inactive_member = create_user(
        db,
        is_active=False,
    )

    create_company_membership(
        db,
        company=company,
        user=inactive_member,
    )

    create_section_membership(
        db,
        section=section,
        user=inactive_member,
    )

    assert TaskPermissionService.can_view(
        db,
        actor=inactive_member,
        task=task,
    ) is False


def test_section_member_can_create_task(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        section_list,
        _,
        _,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    assert TaskPermissionService.can_create(
        db,
        actor=member,
        section_list=section_list,
    ) is True


def test_user_without_section_access_cannot_create_task(
    db: Session,
) -> None:
    (
        company,
        _,
        _,
        section_list,
        _,
        _,
    ) = _create_context(
        db,
    )

    company_member = create_user(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=company_member,
    )

    assert TaskPermissionService.can_create(
        db,
        actor=company_member,
        section_list=section_list,
    ) is False


def test_cannot_create_task_in_archived_list(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        section_list,
        _,
        _,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    section_list.is_archived = True
    db.flush()

    assert TaskPermissionService.can_create(
        db,
        actor=member,
        section_list=section_list,
    ) is False


def test_cannot_create_task_in_archived_section(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        section_list,
        _,
        _,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    section.is_archived = True
    db.flush()

    assert TaskPermissionService.can_create(
        db,
        actor=member,
        section_list=section_list,
    ) is False


def test_section_member_can_update_active_task(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    assert TaskPermissionService.can_update(
        db,
        actor=member,
        task=task,
    ) is True


def test_section_member_cannot_update_deleted_task(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    task.deleted_by = creator

    from app.core.timezone import utc_now

    task.deleted_at = utc_now()
    db.flush()

    assert TaskPermissionService.can_update(
        db,
        actor=member,
        task=task,
    ) is False


def test_section_member_can_move_task_within_same_section(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        destination_list,
        task,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    assert TaskPermissionService.can_move(
        db,
        actor=member,
        task=task,
        destination_list=destination_list,
    ) is True


def test_task_cannot_move_to_list_in_different_section(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    other_section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Other Section",
    )

    other_list = create_section_list(
        db,
        section=other_section,
    )

    assert TaskPermissionService.can_move(
        db,
        actor=member,
        task=task,
        destination_list=other_list,
    ) is False


def test_task_cannot_move_to_archived_destination_list(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        destination_list,
        task,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    destination_list.is_archived = True
    db.flush()

    assert TaskPermissionService.can_move(
        db,
        actor=member,
        task=task,
        destination_list=destination_list,
    ) is False


def test_section_member_can_reorder_tasks(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        _,
        _,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    assert TaskPermissionService.can_reorder(
        db,
        actor=member,
        section=section,
    ) is True


def test_cannot_reorder_tasks_in_archived_section(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        _,
        _,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    section.is_archived = True
    db.flush()

    assert TaskPermissionService.can_reorder(
        db,
        actor=member,
        section=section,
    ) is False


def test_section_member_can_complete_task(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    assert TaskPermissionService.can_complete(
        db,
        actor=member,
        task=task,
    ) is True


def test_section_member_can_comment_on_task(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    assert TaskPermissionService.can_comment(
        db,
        actor=member,
        task=task,
    ) is True


def test_section_creator_can_manage_assignees(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    assert TaskPermissionService.can_manage_assignees(
        db,
        actor=creator,
        task=task,
    ) is True


def test_section_member_cannot_manage_assignees(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    assert TaskPermissionService.can_manage_assignees(
        db,
        actor=member,
        task=task,
    ) is False


def test_section_creator_can_delete_task(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    assert TaskPermissionService.can_delete(
        db,
        actor=creator,
        task=task,
    ) is True


def test_section_member_cannot_delete_task(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    assert TaskPermissionService.can_delete(
        db,
        actor=member,
        task=task,
    ) is False


def test_section_creator_can_restore_deleted_task(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        section_list,
        _,
        _,
    ) = _create_context(
        db,
    )

    deleted_task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        deleted_by=creator,
    )

    assert TaskPermissionService.can_restore(
        db,
        actor=creator,
        task=deleted_task,
    ) is True


def test_section_member_cannot_restore_deleted_task(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        section_list,
        _,
        _,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    deleted_task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        deleted_by=creator,
    )

    assert TaskPermissionService.can_restore(
        db,
        actor=member,
        task=deleted_task,
    ) is False


def test_administrator_can_permanently_delete_deleted_task(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        section_list,
        _,
        _,
    ) = _create_context(
        db,
    )

    administrator = create_administrator(
        db,
    )

    deleted_task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        deleted_by=creator,
    )

    assert TaskPermissionService.can_permanently_delete(
        actor=administrator,
        task=deleted_task,
    ) is True


def test_administrator_cannot_permanently_delete_active_task(
    db: Session,
) -> None:
    (
        _,
        _,
        _,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    administrator = create_administrator(
        db,
    )

    assert TaskPermissionService.can_permanently_delete(
        actor=administrator,
        task=task,
    ) is False


def test_non_administrator_cannot_permanently_delete_task(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        section_list,
        _,
        _,
    ) = _create_context(
        db,
    )

    deleted_task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        deleted_by=creator,
    )

    assert TaskPermissionService.can_permanently_delete(
        actor=creator,
        task=deleted_task,
    ) is False


def test_require_view_raises_for_denied_actor(
    db: Session,
) -> None:
    (
        _,
        _,
        _,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    outsider = create_user(
        db,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="access to this task",
    ):
        TaskPermissionService.require_view(
            db,
            actor=outsider,
            task=task,
        )


def test_require_create_raises_for_denied_actor(
    db: Session,
) -> None:
    (
        _,
        _,
        _,
        section_list,
        _,
        _,
    ) = _create_context(
        db,
    )

    outsider = create_user(
        db,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="create tasks",
    ):
        TaskPermissionService.require_create(
            db,
            actor=outsider,
            section_list=section_list,
        )


def test_require_update_raises_for_denied_actor(
    db: Session,
) -> None:
    (
        _,
        _,
        _,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    outsider = create_user(
        db,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="update this task",
    ):
        TaskPermissionService.require_update(
            db,
            actor=outsider,
            task=task,
        )


def test_require_manage_assignees_raises_for_section_member(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="manage this task's assignees",
    ):
        TaskPermissionService.require_manage_assignees(
            db,
            actor=member,
            task=task,
        )


def test_require_delete_raises_for_section_member(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="delete this task",
    ):
        TaskPermissionService.require_delete(
            db,
            actor=member,
            task=task,
        )


def test_require_same_section_accepts_list_in_same_section(
    db: Session,
) -> None:
    (
        _,
        _,
        _,
        _,
        destination_list,
        task,
    ) = _create_context(
        db,
    )

    TaskPermissionService.require_same_section(
        task=task,
        section_list=destination_list,
    )


def test_require_same_section_rejects_cross_section_list(
    db: Session,
) -> None:
    (
        company,
        creator,
        _,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    other_section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Other Section",
    )

    other_list = create_section_list(
        db,
        section=other_section,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="same section",
    ):
        TaskPermissionService.require_same_section(
            task=task,
            section_list=other_list,
        )


def test_require_active_task_accepts_active_task(
    db: Session,
) -> None:
    (
        _,
        _,
        _,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    TaskPermissionService.require_active_task(
        task=task,
    )


def test_require_active_task_rejects_deleted_task(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        section_list,
        _,
        _,
    ) = _create_context(
        db,
    )

    deleted_task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        deleted_by=creator,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="Deleted tasks cannot be modified",
    ):
        TaskPermissionService.require_active_task(
            task=deleted_task,
        )


def test_require_active_destination_list_accepts_active_list(
    db: Session,
) -> None:
    (
        _,
        _,
        _,
        section_list,
        _,
        _,
    ) = _create_context(
        db,
    )

    TaskPermissionService.require_active_destination_list(
        section_list=section_list,
    )


def test_require_active_destination_list_rejects_archived_list(
    db: Session,
) -> None:
    (
        _,
        _,
        _,
        section_list,
        _,
        _,
    ) = _create_context(
        db,
    )

    section_list.is_archived = True
    db.flush()

    with pytest.raises(
        PermissionDeniedError,
        match="archived list",
    ):
        TaskPermissionService.require_active_destination_list(
            section_list=section_list,
        )


def test_require_active_destination_list_rejects_archived_section(
    db: Session,
) -> None:
    (
        _,
        _,
        section,
        section_list,
        _,
        _,
    ) = _create_context(
        db,
    )

    section.is_archived = True
    db.flush()

    with pytest.raises(
        PermissionDeniedError,
        match="archived section",
    ):
        TaskPermissionService.require_active_destination_list(
            section_list=section_list,
        )


def test_require_active_destination_list_rejects_archived_company(
    db: Session,
) -> None:
    (
        company,
        _,
        _,
        section_list,
        _,
        _,
    ) = _create_context(
        db,
    )

    company.is_archived = True
    db.flush()

    with pytest.raises(
        PermissionDeniedError,
        match="archived company",
    ):
        TaskPermissionService.require_active_destination_list(
            section_list=section_list,
        )