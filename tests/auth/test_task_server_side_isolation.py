import pytest
from sqlalchemy.orm import Session

from app.auth.permissions import PermissionDeniedError
from app.core.constants import CompanyRole
from app.schemas.comment import TaskCommentCreateRequest
from app.schemas.section_list import (
    SectionListPositionUpdate,
    SectionListReorderRequest,
)
from app.schemas.task import (
    TaskCreateRequest,
    TaskFilterOptions,
    TaskMoveRequest,
    TaskPositionUpdate,
    TaskReorderRequest,
    TaskUpdateRequest,
)
from app.schemas.task_assignee import (
    TaskAssigneeCreateRequest,
)
from app.services.comment_service import CommentService
from app.services.section_list_service import (
    SectionListReorderError,
    SectionListService,
)
from app.services.task_assignee_service import (
    TaskAssigneeCompanyMembershipRequiredError,
    TaskAssigneeSectionAccessRequiredError,
    TaskAssigneeService,
)
from app.services.task_service import (
    TaskReorderError,
    TaskService,
    TaskServiceError,
)
from tests.factories import (
    create_administrator,
    create_company,
    create_company_membership,
    create_section,
    create_section_list,
    create_section_membership,
    create_task,
    create_task_assignee,
    create_task_comment,
    create_user,
)
from app.schemas.company import (
    CompanyMembershipCreateRequest,
    CompanyMembershipUpdateRequest,
)
from app.services.company_membership_service import (
    CompanyMembershipService,
)

def _create_isolated_context(
    db: Session,
) -> dict[str, object]:
    first_company = create_company(
        db,
        name="First Company",
    )

    second_company = create_company(
        db,
        name="Second Company",
    )

    first_creator = create_user(
        db,
        display_name="First Creator",
    )

    second_creator = create_user(
        db,
        display_name="Second Creator",
    )

    create_company_membership(
        db,
        company=first_company,
        user=first_creator,
        role=CompanyRole.MANAGER,
    )

    create_company_membership(
        db,
        company=second_company,
        user=second_creator,
        role=CompanyRole.MANAGER,
    )

    first_section = create_section(
        db,
        company=first_company,
        created_by=first_creator,
        name="First Section",
    )

    second_section = create_section(
        db,
        company=second_company,
        created_by=second_creator,
        name="Second Section",
    )

    first_list = create_section_list(
        db,
        section=first_section,
        name="First List",
    )

    second_list = create_section_list(
        db,
        section=second_section,
        name="Second List",
    )

    first_task = create_task(
        db,
        section_list=first_list,
        created_by=first_creator,
        title="First Task",
    )

    second_task = create_task(
        db,
        section_list=second_list,
        created_by=second_creator,
        title="Second Task",
    )

    return {
        "first_company": first_company,
        "second_company": second_company,
        "first_creator": first_creator,
        "second_creator": second_creator,
        "first_section": first_section,
        "second_section": second_section,
        "first_list": first_list,
        "second_list": second_list,
        "first_task": first_task,
        "second_task": second_task,
    }


def test_user_cannot_open_task_from_other_company_by_id(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="access to this task",
    ):
        TaskService.get_accessible_task(
            db,
            actor=context["first_creator"],
            task_id=context["second_task"].id,
        )


def test_user_cannot_list_tasks_from_other_company_section(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="access to this section",
    ):
        TaskService.list_for_section(
            db,
            actor=context["first_creator"],
            section=context["second_section"],
        )


def test_user_cannot_create_task_in_other_company_list(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="create tasks",
    ):
        TaskService.create_task(
            db,
            actor=context["first_creator"],
            section_list=context["second_list"],
            task_create=TaskCreateRequest(
                section_list_id=context["second_list"].id,
                title="Injected task",
            ),
            commit=False,
        )


def test_create_task_rejects_submitted_foreign_list_id(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    with pytest.raises(
        TaskServiceError,
        match="does not match the selected list",
    ):
        TaskService.create_task(
            db,
            actor=context["first_creator"],
            section_list=context["first_list"],
            task_create=TaskCreateRequest(
                section_list_id=context["second_list"].id,
                title="Mismatched task",
            ),
            commit=False,
        )


def test_user_cannot_update_task_from_other_company(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    original_title = context["second_task"].title

    with pytest.raises(
        PermissionDeniedError,
        match="update this task",
    ):
        TaskService.update_task(
            db,
            actor=context["first_creator"],
            task=context["second_task"],
            task_update=TaskUpdateRequest(
                title="Hijacked task",
            ),
            commit=False,
        )

    assert context["second_task"].title == original_title


def test_user_cannot_complete_task_from_other_company(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="completion state",
    ):
        TaskService.complete_task(
            db,
            actor=context["first_creator"],
            task=context["second_task"],
            commit=False,
        )

    assert context["second_task"].completed_at is None
    assert context["second_task"].completed_by_user_id is None


def test_user_cannot_reopen_task_from_other_company(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    context["second_task"].completed_at = (
        context["second_task"].created_at
    )
    context["second_task"].completed_by = (
        context["second_creator"]
    )

    db.flush()

    original_completed_at = (
        context["second_task"].completed_at
    )

    original_completed_by_user_id = (
        context["second_task"].completed_by_user_id
    )

    with pytest.raises(
        PermissionDeniedError,
        match="completion state",
    ):
        TaskService.reopen_task(
            db,
            actor=context["first_creator"],
            task=context["second_task"],
            commit=False,
        )

    assert (
        context["second_task"].completed_at
        == original_completed_at
    )

    assert (
        context["second_task"].completed_by_user_id
        == original_completed_by_user_id
    )


def test_user_cannot_delete_task_from_other_company(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="delete this task",
    ):
        TaskService.delete_task(
            db,
            actor=context["first_creator"],
            task=context["second_task"],
            commit=False,
        )

    assert context["second_task"].deleted_at is None
    assert context["second_task"].deleted_by_user_id is None


def test_user_cannot_restore_task_from_other_company(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    deleted_task = create_task(
        db,
        section_list=context["second_list"],
        created_by=context["second_creator"],
        title="Deleted Second Task",
        deleted_by=context["second_creator"],
    )

    original_deleted_at = deleted_task.deleted_at
    original_deleted_by_user_id = (
        deleted_task.deleted_by_user_id
    )

    with pytest.raises(
        PermissionDeniedError,
        match="restore this task",
    ):
        TaskService.restore_task(
            db,
            actor=context["first_creator"],
            task=deleted_task,
            commit=False,
        )

    assert deleted_task.deleted_at == original_deleted_at

    assert (
        deleted_task.deleted_by_user_id
        == original_deleted_by_user_id
    )


def test_user_cannot_comment_on_task_from_other_company(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="comment on this task",
    ):
        CommentService.add_comment(
            db,
            actor=context["first_creator"],
            task=context["second_task"],
            comment_create=TaskCommentCreateRequest(
                body="Injected comment.",
            ),
            commit=False,
        )


def test_user_cannot_delete_comment_from_other_company(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    comment = create_task_comment(
        db,
        task=context["second_task"],
        user=context["second_creator"],
    )

    with pytest.raises(
        PermissionDeniedError,
        match="access to this task",
    ):
        CommentService.delete_comment(
            db,
            actor=context["first_creator"],
            comment=comment,
            commit=False,
        )

    assert comment.deleted_at is None
    assert comment.deleted_by_user_id is None


def test_user_cannot_manage_assignees_on_other_company_task(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="manage this task's assignees",
    ):
        TaskAssigneeService.add_assignee(
            db,
            actor=context["first_creator"],
            task=context["second_task"],
            create_request=TaskAssigneeCreateRequest(
                user_id=context["second_creator"].id,
            ),
            commit=False,
        )


def test_user_cannot_remove_assignee_from_other_company_task(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    assignment = create_task_assignee(
        db,
        task=context["second_task"],
        user=context["second_creator"],
    )

    with pytest.raises(
        PermissionDeniedError,
        match="manage this task's assignees",
    ):
        TaskAssigneeService.remove_assignee(
            db,
            actor=context["first_creator"],
            assignment=assignment,
            commit=False,
        )

    stored_assignment = (
        TaskAssigneeService.get_assignment(
            db,
            task_id=context["second_task"].id,
            user_id=context["second_creator"].id,
        )
    )

    assert stored_assignment is assignment


def test_task_assignment_does_not_bypass_section_isolation(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    create_company_membership(
        db,
        company=context["second_company"],
        user=context["first_creator"],
        role=CompanyRole.EMPLOYEE,
    )

    create_task_assignee(
        db,
        task=context["second_task"],
        user=context["first_creator"],
    )

    with pytest.raises(
        PermissionDeniedError,
        match="access to this task",
    ):
        TaskService.get_accessible_task(
            db,
            actor=context["first_creator"],
            task_id=context["second_task"].id,
        )


def test_company_manager_role_does_not_bypass_section_isolation(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    create_company_membership(
        db,
        company=context["second_company"],
        user=context["first_creator"],
        role=CompanyRole.MANAGER,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="access to this task",
    ):
        TaskService.get_accessible_task(
            db,
            actor=context["first_creator"],
            task_id=context["second_task"].id,
        )


def test_explicit_section_membership_grants_access_only_to_that_section(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    create_company_membership(
        db,
        company=context["second_company"],
        user=context["first_creator"],
        role=CompanyRole.EMPLOYEE,
    )

    create_section_membership(
        db,
        section=context["second_section"],
        user=context["first_creator"],
    )

    result = TaskService.get_accessible_task(
        db,
        actor=context["first_creator"],
        task_id=context["second_task"].id,
    )

    assert result is context["second_task"]


def test_task_cannot_be_moved_to_list_in_other_company(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    original_list_id = (
        context["first_task"].section_list_id
    )

    original_position = (
        context["first_task"].sort_position
    )

    with pytest.raises(
        PermissionDeniedError,
        match="same section",
    ):
        TaskService.move_task(
            db,
            actor=context["first_creator"],
            task=context["first_task"],
            destination_list=context["second_list"],
            move_request=TaskMoveRequest(
                destination_list_id=context["second_list"].id,
                sort_position=2000,
            ),
            commit=False,
        )

    assert (
        context["first_task"].section_list_id
        == original_list_id
    )

    assert (
        context["first_task"].sort_position
        == original_position
    )


def test_administrator_cannot_use_drag_drop_for_cross_section_move(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    administrator = create_administrator(
        db,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="same section",
    ):
        TaskService.move_task(
            db,
            actor=administrator,
            task=context["first_task"],
            destination_list=context["second_list"],
            move_request=TaskMoveRequest(
                destination_list_id=context["second_list"].id,
                sort_position=1000,
            ),
            commit=False,
        )


def test_task_reorder_rejects_task_from_other_section(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    original_list_id = (
        context["second_task"].section_list_id
    )

    original_position = (
        context["second_task"].sort_position
    )

    with pytest.raises(
        TaskReorderError,
        match="deleted or does not belong",
    ):
        TaskService.reorder_tasks(
            db,
            actor=context["first_creator"],
            section=context["first_section"],
            reorder_request=TaskReorderRequest(
                items=[
                    TaskPositionUpdate(
                        task_id=context["second_task"].id,
                        section_list_id=context["first_list"].id,
                        sort_position=5000,
                    ),
                ],
            ),
            commit=False,
        )

    assert (
        context["second_task"].section_list_id
        == original_list_id
    )

    assert (
        context["second_task"].sort_position
        == original_position
    )


def test_task_reorder_rejects_destination_list_from_other_section(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    original_list_id = (
        context["first_task"].section_list_id
    )

    original_position = (
        context["first_task"].sort_position
    )

    with pytest.raises(
        TaskReorderError,
        match="archived or does not belong",
    ):
        TaskService.reorder_tasks(
            db,
            actor=context["first_creator"],
            section=context["first_section"],
            reorder_request=TaskReorderRequest(
                items=[
                    TaskPositionUpdate(
                        task_id=context["first_task"].id,
                        section_list_id=context["second_list"].id,
                        sort_position=5000,
                    ),
                ],
            ),
            commit=False,
        )

    assert (
        context["first_task"].section_list_id
        == original_list_id
    )

    assert (
        context["first_task"].sort_position
        == original_position
    )


def test_list_reorder_rejects_list_from_other_section(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    first_position = (
        context["first_list"].sort_position
    )

    second_position = (
        context["second_list"].sort_position
    )

    with pytest.raises(
        SectionListReorderError,
        match="archived or does not belong",
    ):
        SectionListService.reorder_lists(
            db,
            actor=context["first_creator"],
            section=context["first_section"],
            reorder_request=SectionListReorderRequest(
                items=[
                    SectionListPositionUpdate(
                        list_id=context["first_list"].id,
                        sort_position=3000,
                    ),
                    SectionListPositionUpdate(
                        list_id=context["second_list"].id,
                        sort_position=4000,
                    ),
                ],
            ),
            commit=False,
        )

    assert (
        context["first_list"].sort_position
        == first_position
    )

    assert (
        context["second_list"].sort_position
        == second_position
    )


def test_task_list_filter_rejects_list_from_other_section(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    with pytest.raises(
        TaskServiceError,
        match="does not belong to this section",
    ):
        TaskService.list_for_section(
            db,
            actor=context["first_creator"],
            section=context["first_section"],
            filters=TaskFilterOptions(
                section_list_id=context["second_list"].id,
            ),
        )


def test_cannot_assign_company_member_without_section_access(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    company_only_user = create_user(
        db,
    )

    create_company_membership(
        db,
        company=context["first_company"],
        user=company_only_user,
        role=CompanyRole.EMPLOYEE,
    )

    with pytest.raises(
        TaskAssigneeSectionAccessRequiredError,
        match="does not have access",
    ):
        TaskAssigneeService.add_assignee(
            db,
            actor=context["first_creator"],
            task=context["first_task"],
            create_request=TaskAssigneeCreateRequest(
                user_id=company_only_user.id,
            ),
            commit=False,
        )


def test_cannot_assign_member_of_different_company(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    with pytest.raises(
        TaskAssigneeCompanyMembershipRequiredError,
        match="not a member of the task's company",
    ):
        TaskAssigneeService.add_assignee(
            db,
            actor=context["first_creator"],
            task=context["first_task"],
            create_request=TaskAssigneeCreateRequest(
                user_id=context["second_creator"].id,
            ),
            commit=False,
        )


def test_failed_cross_company_update_leaves_task_unchanged(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    original_title = context["second_task"].title
    original_description = (
        context["second_task"].description
    )
    original_due_at = context["second_task"].due_at

    with pytest.raises(
        PermissionDeniedError,
    ):
        TaskService.update_task(
            db,
            actor=context["first_creator"],
            task=context["second_task"],
            task_update=TaskUpdateRequest(
                title="Changed externally",
                description="Injected description.",
            ),
            commit=False,
        )

    assert context["second_task"].title == original_title

    assert (
        context["second_task"].description
        == original_description
    )

    assert context["second_task"].due_at == original_due_at


def test_failed_cross_company_operations_leave_task_state_unchanged(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    original_list_id = (
        context["second_task"].section_list_id
    )

    original_position = (
        context["second_task"].sort_position
    )

    with pytest.raises(
        PermissionDeniedError,
    ):
        TaskService.complete_task(
            db,
            actor=context["first_creator"],
            task=context["second_task"],
            commit=False,
        )

    with pytest.raises(
        PermissionDeniedError,
    ):
        TaskService.delete_task(
            db,
            actor=context["first_creator"],
            task=context["second_task"],
            commit=False,
        )

    assert (
        context["second_task"].section_list_id
        == original_list_id
    )

    assert (
        context["second_task"].sort_position
        == original_position
    )

    assert context["second_task"].completed_at is None

    assert (
        context["second_task"].completed_by_user_id
        is None
    )

    assert context["second_task"].deleted_at is None

    assert (
        context["second_task"].deleted_by_user_id
        is None
    )

def test_task_reorder_cannot_hide_existing_task_by_omission(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    extra_task = create_task(
        db,
        section_list=context["first_list"],
        created_by=context["first_creator"],
        title="Extra First Task",
        sort_position=2000,
    )

    original_first_position = (
        context["first_task"].sort_position
    )

    original_extra_position = (
        extra_task.sort_position
    )

    with pytest.raises(
        TaskReorderError,
        match="include every active task",
    ):
        TaskService.reorder_tasks(
            db,
            actor=context["first_creator"],
            section=context["first_section"],
            reorder_request=TaskReorderRequest(
                items=[
                    TaskPositionUpdate(
                        task_id=context["first_task"].id,
                        section_list_id=context["first_list"].id,
                        sort_position=3000,
                    ),
                ],
            ),
            commit=False,
        )

    assert (
        context["first_task"].sort_position
        == original_first_position
    )

    assert (
        extra_task.sort_position
        == original_extra_position
    )


def test_list_reorder_cannot_hide_existing_list_by_omission(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    extra_list = create_section_list(
        db,
        section=context["first_section"],
        name="Extra First List",
        sort_position=2000,
    )

    original_first_position = (
        context["first_list"].sort_position
    )

    original_extra_position = (
        extra_list.sort_position
    )

    with pytest.raises(
        SectionListReorderError,
        match="include every active list",
    ):
        SectionListService.reorder_lists(
            db,
            actor=context["first_creator"],
            section=context["first_section"],
            reorder_request=SectionListReorderRequest(
                items=[
                    SectionListPositionUpdate(
                        list_id=context["first_list"].id,
                        sort_position=3000,
                    ),
                ],
            ),
            commit=False,
        )

    assert (
        context["first_list"].sort_position
        == original_first_position
    )

    assert (
        extra_list.sort_position
        == original_extra_position
    )


def test_task_reorder_rejects_archived_cross_board_destination(
    db: Session,
) -> None:
    context = _create_isolated_context(
        db,
    )

    archived_list = create_section_list(
        db,
        section=context["first_section"],
        name="Archived First List",
        sort_position=2000,
        is_archived=True,
    )

    original_list_id = (
        context["first_task"].section_list_id
    )

    original_position = (
        context["first_task"].sort_position
    )

    with pytest.raises(
        TaskReorderError,
        match="archived or does not belong",
    ):
        TaskService.reorder_tasks(
            db,
            actor=context["first_creator"],
            section=context["first_section"],
            reorder_request=TaskReorderRequest(
                items=[
                    TaskPositionUpdate(
                        task_id=context["first_task"].id,
                        section_list_id=archived_list.id,
                        sort_position=1000,
                    ),
                ],
            ),
            commit=False,
        )

    assert (
        context["first_task"].section_list_id
        == original_list_id
    )

    assert (
        context["first_task"].sort_position
        == original_position
    )

def test_manager_cannot_add_member_to_other_company(
    db: Session,
) -> None:
    own_company = create_company(
        db,
    )

    other_company = create_company(
        db,
    )

    manager = create_user(
        db,
    )

    target = create_user(
        db,
    )

    create_company_membership(
        db,
        company=own_company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    with pytest.raises(
        PermissionDeniedError,
    ):
        CompanyMembershipService.add_member(
            db,
            actor=manager,
            company=other_company,
            membership_create=(
                CompanyMembershipCreateRequest(
                    user_id=target.id,
                )
            ),
        )


def test_manager_cannot_change_role_in_other_company(
    db: Session,
) -> None:
    own_company = create_company(
        db,
    )

    other_company = create_company(
        db,
    )

    manager = create_user(
        db,
    )

    target = create_user(
        db,
    )

    create_company_membership(
        db,
        company=own_company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    target_membership = create_company_membership(
        db,
        company=other_company,
        user=target,
        role=CompanyRole.EMPLOYEE,
    )

    with pytest.raises(
        PermissionDeniedError,
    ):
        CompanyMembershipService.update_role(
            db,
            actor=manager,
            membership=target_membership,
            membership_update=(
                CompanyMembershipUpdateRequest(
                    role=CompanyRole.MANAGER,
                )
            ),
        )

    assert (
        target_membership.role
        == CompanyRole.EMPLOYEE.value
    )


def test_manager_cannot_remove_member_from_other_company(
    db: Session,
) -> None:
    own_company = create_company(
        db,
    )

    other_company = create_company(
        db,
    )

    manager = create_user(
        db,
    )

    target = create_user(
        db,
    )

    create_company_membership(
        db,
        company=own_company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    target_membership = create_company_membership(
        db,
        company=other_company,
        user=target,
    )

    with pytest.raises(
        PermissionDeniedError,
    ):
        CompanyMembershipService.remove_member(
            db,
            actor=manager,
            membership=target_membership,
        )

    assert (
        CompanyMembershipService.get_membership(
            db,
            company_id=other_company.id,
            user_id=target.id,
        )
        is target_membership
    )


def test_employee_cannot_mutate_own_company_memberships(
    db: Session,
) -> None:
    company = create_company(
        db,
    )

    employee = create_user(
        db,
    )

    target = create_user(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=employee,
        role=CompanyRole.EMPLOYEE,
    )

    with pytest.raises(
        PermissionDeniedError,
    ):
        CompanyMembershipService.add_member(
            db,
            actor=employee,
            company=company,
            membership_create=(
                CompanyMembershipCreateRequest(
                    user_id=target.id,
                )
            ),
        )