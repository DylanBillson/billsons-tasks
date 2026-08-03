import pytest
from sqlalchemy.orm import Session

from app.auth.permissions import (
    PermissionDeniedError,
    PermissionService,
)
from app.core.constants import CompanyRole
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

    creator = create_user(
        db,
        display_name="Section Creator",
    )

    create_company_membership(
        db,
        company=company,
        user=creator,
        role=CompanyRole.MANAGER,
    )

    section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Operations",
    )

    first_list = create_section_list(
        db,
        section=section,
        name="To Do",
    )

    second_list = create_section_list(
        db,
        section=section,
        name="In Progress",
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        title="Complete stock check",
    )

    return (
        company,
        creator,
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


def test_administrator_can_view_section_list(
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

    administrator = create_administrator(
        db,
    )

    assert PermissionService.can_view_section_list(
        db,
        actor=administrator,
        section_list=section_list,
    ) is True


def test_section_creator_can_view_section_list(
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

    assert PermissionService.can_view_section_list(
        db,
        actor=creator,
        section_list=section_list,
    ) is True


def test_explicit_section_member_can_view_section_list(
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

    assert PermissionService.can_view_section_list(
        db,
        actor=member,
        section_list=section_list,
    ) is True


def test_company_member_cannot_view_unassigned_section_list(
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

    assert PermissionService.can_view_section_list(
        db,
        actor=company_member,
        section_list=section_list,
    ) is False


def test_company_manager_cannot_view_unassigned_section_list(
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

    manager = create_user(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    assert PermissionService.can_view_section_list(
        db,
        actor=manager,
        section_list=section_list,
    ) is False


def test_section_creator_can_manage_section_list(
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

    assert PermissionService.can_manage_section_list(
        db,
        actor=creator,
        section_list=section_list,
    ) is True


def test_section_member_cannot_manage_section_list(
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

    assert PermissionService.can_manage_section_list(
        db,
        actor=member,
        section_list=section_list,
    ) is False


def test_archived_section_list_cannot_be_managed(
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

    section_list.is_archived = True
    db.flush()

    assert PermissionService.can_manage_section_list(
        db,
        actor=creator,
        section_list=section_list,
    ) is True

def test_list_in_archived_section_cannot_be_managed(
    db: Session,
) -> None:
    (
        _,
        creator,
        section,
        section_list,
        _,
        _,
    ) = _create_context(
        db,
    )

    section.is_archived = True
    db.flush()

    assert PermissionService.can_manage_section_list(
        db,
        actor=creator,
        section_list=section_list,
    ) is False


def test_list_in_archived_company_cannot_be_managed(
    db: Session,
) -> None:
    (
        company,
        creator,
        _,
        section_list,
        _,
        _,
    ) = _create_context(
        db,
    )

    company.is_archived = True
    db.flush()

    assert PermissionService.can_manage_section_list(
        db,
        actor=creator,
        section_list=section_list,
    ) is False


def test_section_creator_can_create_section_list(
    db: Session,
) -> None:
    (
        _,
        creator,
        section,
        _,
        _,
        _,
    ) = _create_context(
        db,
    )

    assert PermissionService.can_create_section_list(
        db,
        actor=creator,
        section=section,
    ) is True


def test_section_member_cannot_create_section_list(
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

    assert PermissionService.can_create_section_list(
        db,
        actor=member,
        section=section,
    ) is False


def test_administrator_can_view_active_task(
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

    assert PermissionService.can_view_task(
        db,
        actor=administrator,
        task=task,
    ) is True


def test_section_creator_can_view_active_task(
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

    assert PermissionService.can_view_task(
        db,
        actor=creator,
        task=task,
    ) is True


def test_section_member_can_view_active_task(
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

    assert PermissionService.can_view_task(
        db,
        actor=member,
        task=task,
    ) is True


def test_outsider_cannot_view_task(
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

    assert PermissionService.can_view_task(
        db,
        actor=outsider,
        task=task,
    ) is False


def test_company_manager_cannot_view_task_without_section_access(
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

    assert PermissionService.can_view_task(
        db,
        actor=manager,
        task=task,
    ) is False


def test_task_assignment_does_not_grant_section_access(
    db: Session,
) -> None:
    (
        company,
        creator,
        _,
        first_list,
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

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    from tests.factories import create_task_assignee

    create_task_assignee(
        db,
        task=task,
        user=company_member,
    )

    assert PermissionService.can_view_task(
        db,
        actor=company_member,
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

    assert PermissionService.can_create_task(
        db,
        actor=member,
        section_list=section_list,
    ) is True


def test_cannot_create_task_in_archived_list(
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

    section_list.is_archived = True
    db.flush()

    assert PermissionService.can_create_task(
        db,
        actor=creator,
        section_list=section_list,
    ) is False


def test_section_member_can_update_task(
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

    assert PermissionService.can_update_task(
        db,
        actor=member,
        task=task,
    ) is True


def test_deleted_task_cannot_be_updated(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        _,
        _,
    ) = _create_context(
        db,
    )

    deleted_task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        deleted_by=creator,
    )

    assert PermissionService.can_update_task(
        db,
        actor=creator,
        task=deleted_task,
    ) is False


def test_section_member_can_move_task_within_section(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        second_list,
        task,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    assert PermissionService.can_move_task(
        db,
        actor=member,
        task=task,
        destination_list=second_list,
    ) is True


def test_task_cannot_move_between_sections(
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

    assert PermissionService.can_move_task(
        db,
        actor=creator,
        task=task,
        destination_list=other_list,
    ) is False


def test_even_administrator_cannot_use_normal_cross_section_move(
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

    administrator = create_administrator(
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

    assert PermissionService.can_move_task(
        db,
        actor=administrator,
        task=task,
        destination_list=other_list,
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

    assert PermissionService.can_complete_task(
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

    assert PermissionService.can_comment_on_task(
        db,
        actor=member,
        task=task,
    ) is True


def test_section_creator_can_manage_task_assignees(
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

    assert PermissionService.can_manage_task_assignees(
        db,
        actor=creator,
        task=task,
    ) is True


def test_section_member_cannot_manage_task_assignees(
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

    assert PermissionService.can_manage_task_assignees(
        db,
        actor=member,
        task=task,
    ) is False


def test_section_creator_can_soft_delete_task(
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

    assert PermissionService.can_delete_task(
        db,
        actor=creator,
        task=task,
    ) is True


def test_section_member_cannot_soft_delete_task(
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

    assert PermissionService.can_delete_task(
        db,
        actor=member,
        task=task,
    ) is False


def test_deleted_task_visible_to_section_creator(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        _,
        _,
    ) = _create_context(
        db,
    )

    deleted_task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        deleted_by=creator,
    )

    assert PermissionService.can_view_task(
        db,
        actor=creator,
        task=deleted_task,
    ) is True


def test_deleted_task_hidden_from_ordinary_section_member(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        first_list,
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
        section_list=first_list,
        created_by=creator,
        deleted_by=creator,
    )

    assert PermissionService.can_view_task(
        db,
        actor=member,
        task=deleted_task,
    ) is False


def test_administrator_can_view_deleted_task(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
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
        section_list=first_list,
        created_by=creator,
        deleted_by=creator,
    )

    assert PermissionService.can_view_task(
        db,
        actor=administrator,
        task=deleted_task,
    ) is True


def test_section_creator_can_restore_deleted_task(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        _,
        _,
    ) = _create_context(
        db,
    )

    deleted_task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        deleted_by=creator,
    )

    assert PermissionService.can_restore_task(
        db,
        actor=creator,
        task=deleted_task,
    ) is True


def test_only_administrator_can_permanently_delete_task(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
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
        section_list=first_list,
        created_by=creator,
        deleted_by=creator,
    )

    assert PermissionService.can_permanently_delete_task(
        actor=administrator,
        task=deleted_task,
    ) is True

    assert PermissionService.can_permanently_delete_task(
        actor=creator,
        task=deleted_task,
    ) is False


def test_require_task_access_raises_for_outsider(
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
        PermissionService.require_task_access(
            db,
            actor=outsider,
            task=task,
        )


def test_require_task_movement_raises_for_cross_section_move(
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
        match="move this task",
    ):
        PermissionService.require_task_movement(
            db,
            actor=creator,
            task=task,
            destination_list=other_list,
        )