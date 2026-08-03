import pytest
from sqlalchemy.orm import Session

from app.auth.permissions import PermissionDeniedError
from app.core.constants import (
    AuditAction,
    CompanyRole,
    TaskHistoryEventType,
)
from app.repositories.audit_repository import AuditRepository
from app.repositories.task_history_repository import (
    TaskHistoryRepository,
)
from app.schemas.task_assignee import (
    TaskAssigneeCreateRequest,
    TaskAssigneeReplaceRequest,
)
from app.services.task_assignee_service import (
    TaskAssigneeAlreadyExistsError,
    TaskAssigneeCompanyMembershipRequiredError,
    TaskAssigneeNotFoundError,
    TaskAssigneeSectionAccessRequiredError,
    TaskAssigneeService,
    TaskAssigneeUserNotFoundError,
    TaskAssigneeUserUnavailableError,
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
        display_name="Section Creator",
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

    section_list = create_section_list(
        db,
        section=section,
        name="To Do",
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=section_creator,
        title="Prepare weekly report",
    )

    return (
        company,
        section_creator,
        section,
        section_list,
        task,
    )


def _create_eligible_assignee(
    db: Session,
    *,
    company,
    section,
    display_name: str | None = None,
):
    user = create_user(
        db,
        display_name=display_name,
    )

    create_company_membership(
        db,
        company=company,
        user=user,
        role=CompanyRole.EMPLOYEE,
    )

    create_section_membership(
        db,
        section=section,
        user=user,
    )

    return user


def test_get_assignment_returns_existing_assignment(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    user = _create_eligible_assignee(
        db,
        company=company,
        section=section,
    )

    assignment = create_task_assignee(
        db,
        task=task,
        user=user,
    )

    result = TaskAssigneeService.get_assignment(
        db,
        task_id=task.id,
        user_id=user.id,
    )

    assert result is assignment


def test_get_assignment_returns_none_for_missing_assignment(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    user = _create_eligible_assignee(
        db,
        company=company,
        section=section,
    )

    result = TaskAssigneeService.get_assignment(
        db,
        task_id=task.id,
        user_id=user.id,
    )

    assert result is None


def test_require_assignment_returns_existing_assignment(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    user = _create_eligible_assignee(
        db,
        company=company,
        section=section,
    )

    assignment = create_task_assignee(
        db,
        task=task,
        user=user,
    )

    result = TaskAssigneeService.require_assignment(
        db,
        task_id=task.id,
        user_id=user.id,
    )

    assert result is assignment


def test_require_assignment_raises_for_missing_assignment(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    user = _create_eligible_assignee(
        db,
        company=company,
        section=section,
    )

    with pytest.raises(
        TaskAssigneeNotFoundError,
        match="Task assignment was not found",
    ):
        TaskAssigneeService.require_assignment(
            db,
            task_id=task.id,
            user_id=user.id,
        )


def test_section_creator_lists_task_assignees(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    alice = _create_eligible_assignee(
        db,
        company=company,
        section=section,
        display_name="Alice",
    )

    bob = _create_eligible_assignee(
        db,
        company=company,
        section=section,
        display_name="Bob",
    )

    alice_assignment = create_task_assignee(
        db,
        task=task,
        user=alice,
    )

    bob_assignment = create_task_assignee(
        db,
        task=task,
        user=bob,
    )

    result = TaskAssigneeService.list_for_task(
        db,
        actor=creator,
        task=task,
    )

    assert result == [
        alice_assignment,
        bob_assignment,
    ]


def test_section_member_can_list_task_assignees(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    member = _create_eligible_assignee(
        db,
        company=company,
        section=section,
    )

    assignment = create_task_assignee(
        db,
        task=task,
        user=member,
    )

    result = TaskAssigneeService.list_for_task(
        db,
        actor=member,
        task=task,
    )

    assert result == [
        assignment,
    ]


def test_outsider_cannot_list_task_assignees(
    db: Session,
) -> None:
    (
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
        TaskAssigneeService.list_for_task(
            db,
            actor=outsider,
            task=task,
        )


def test_section_creator_adds_assignee(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    assignee = _create_eligible_assignee(
        db,
        company=company,
        section=section,
        display_name="Assigned User",
    )

    assignment = TaskAssigneeService.add_assignee(
        db,
        actor=creator,
        task=task,
        create_request=TaskAssigneeCreateRequest(
            user_id=assignee.id,
        ),
        commit=False,
    )

    assert assignment.id is not None
    assert assignment.task_id == task.id
    assert assignment.user_id == assignee.id
    assert assignment.user is assignee


def test_administrator_adds_assignee(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    administrator = create_administrator(
        db,
    )

    assignee = _create_eligible_assignee(
        db,
        company=company,
        section=section,
    )

    assignment = TaskAssigneeService.add_assignee(
        db,
        actor=administrator,
        task=task,
        create_request=TaskAssigneeCreateRequest(
            user_id=assignee.id,
        ),
        commit=False,
    )

    assert assignment.user_id == assignee.id


def test_section_member_cannot_add_assignee(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    member = _create_eligible_assignee(
        db,
        company=company,
        section=section,
    )

    another_user = _create_eligible_assignee(
        db,
        company=company,
        section=section,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="manage this task's assignees",
    ):
        TaskAssigneeService.add_assignee(
            db,
            actor=member,
            task=task,
            create_request=TaskAssigneeCreateRequest(
                user_id=another_user.id,
            ),
            commit=False,
        )


def test_add_assignee_rejects_unknown_user(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    with pytest.raises(
        TaskAssigneeUserNotFoundError,
        match="selected user was not found",
    ):
        TaskAssigneeService.add_assignee(
            db,
            actor=creator,
            task=task,
            create_request=TaskAssigneeCreateRequest(
                user_id=999999,
            ),
            commit=False,
        )


def test_add_assignee_rejects_inactive_user(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    inactive_user = create_user(
        db,
        is_active=False,
    )

    create_company_membership(
        db,
        company=company,
        user=inactive_user,
    )

    create_section_membership(
        db,
        section=section,
        user=inactive_user,
    )

    with pytest.raises(
        TaskAssigneeUserUnavailableError,
        match="selected user is not available",
    ):
        TaskAssigneeService.add_assignee(
            db,
            actor=creator,
            task=task,
            create_request=TaskAssigneeCreateRequest(
                user_id=inactive_user.id,
            ),
            commit=False,
        )


def test_add_assignee_rejects_anonymised_user(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    anonymised_user = create_user(
        db,
        is_anonymised=True,
    )

    create_company_membership(
        db,
        company=company,
        user=anonymised_user,
    )

    create_section_membership(
        db,
        section=section,
        user=anonymised_user,
    )

    with pytest.raises(
        TaskAssigneeUserUnavailableError,
        match="selected user is not available",
    ):
        TaskAssigneeService.add_assignee(
            db,
            actor=creator,
            task=task,
            create_request=TaskAssigneeCreateRequest(
                user_id=anonymised_user.id,
            ),
            commit=False,
        )


def test_add_assignee_requires_company_membership(
    db: Session,
) -> None:
    (
        _,
        creator,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    user = create_user(
        db,
    )

    create_section_membership(
        db,
        section=section,
        user=user,
    )

    with pytest.raises(
        TaskAssigneeCompanyMembershipRequiredError,
        match="not a member of the task's company",
    ):
        TaskAssigneeService.add_assignee(
            db,
            actor=creator,
            task=task,
            create_request=TaskAssigneeCreateRequest(
                user_id=user.id,
            ),
            commit=False,
        )


def test_add_assignee_requires_section_access(
    db: Session,
) -> None:
    (
        company,
        creator,
        _,
        _,
        task,
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

    with pytest.raises(
        TaskAssigneeSectionAccessRequiredError,
        match="does not have access",
    ):
        TaskAssigneeService.add_assignee(
            db,
            actor=creator,
            task=task,
            create_request=TaskAssigneeCreateRequest(
                user_id=company_member.id,
            ),
            commit=False,
        )


def test_administrator_can_be_assigned_without_company_membership(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    administrator = create_administrator(
        db,
    )

    assignment = TaskAssigneeService.add_assignee(
        db,
        actor=creator,
        task=task,
        create_request=TaskAssigneeCreateRequest(
            user_id=administrator.id,
        ),
        commit=False,
    )

    assert assignment.user_id == administrator.id


def test_add_assignee_rejects_duplicate_assignment(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    assignee = _create_eligible_assignee(
        db,
        company=company,
        section=section,
    )

    create_task_assignee(
        db,
        task=task,
        user=assignee,
    )

    with pytest.raises(
        TaskAssigneeAlreadyExistsError,
        match="already assigned",
    ):
        TaskAssigneeService.add_assignee(
            db,
            actor=creator,
            task=task,
            create_request=TaskAssigneeCreateRequest(
                user_id=assignee.id,
            ),
            commit=False,
        )


def test_add_assignee_records_history_event(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    assignee = _create_eligible_assignee(
        db,
        company=company,
        section=section,
        display_name="Assigned User",
    )

    TaskAssigneeService.add_assignee(
        db,
        actor=creator,
        task=task,
        create_request=TaskAssigneeCreateRequest(
            user_id=assignee.id,
        ),
        commit=False,
    )

    events = TaskHistoryRepository.list_for_task(
        db,
        task_id=task.id,
    )

    assert len(events) == 1

    event = events[0]

    assert (
        event.event_type
        == TaskHistoryEventType.ASSIGNEE_ADDED.value
    )
    assert event.user_id == creator.id
    assert event.metadata_json["assignee_user_id"] == assignee.id
    assert (
        event.metadata_json["assignee_display_name"]
        == "Assigned User"
    )


def test_add_assignee_records_audit_log(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    assignee = _create_eligible_assignee(
        db,
        company=company,
        section=section,
        display_name="Assigned User",
    )

    TaskAssigneeService.add_assignee(
        db,
        actor=creator,
        task=task,
        create_request=TaskAssigneeCreateRequest(
            user_id=assignee.id,
        ),
        ip_address="192.0.2.20",
        user_agent="pytest task-assignee service",
        commit=False,
    )

    audit_logs = AuditRepository.list_logs(
        db,
        action=AuditAction.TASK_ASSIGNEE_ADDED.value,
    )

    matching = [
        log
        for log in audit_logs
        if (
            log.entity_type == "task"
            and log.entity_id == task.id
        )
    ]

    assert len(matching) == 1

    audit_log = matching[0]

    assert audit_log.user_id == creator.id
    assert audit_log.metadata_json["section_id"] == section.id
    assert (
        audit_log.metadata_json["assignee_user_id"]
        == assignee.id
    )
    assert audit_log.ip_address == "192.0.2.20"


def test_section_creator_removes_assignee(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    assignee = _create_eligible_assignee(
        db,
        company=company,
        section=section,
    )

    assignment = create_task_assignee(
        db,
        task=task,
        user=assignee,
    )

    TaskAssigneeService.remove_assignee(
        db,
        actor=creator,
        assignment=assignment,
        commit=False,
    )

    assert TaskAssigneeService.get_assignment(
        db,
        task_id=task.id,
        user_id=assignee.id,
    ) is None


def test_section_member_cannot_remove_assignee(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    member = _create_eligible_assignee(
        db,
        company=company,
        section=section,
    )

    assignee = _create_eligible_assignee(
        db,
        company=company,
        section=section,
    )

    assignment = create_task_assignee(
        db,
        task=task,
        user=assignee,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="manage this task's assignees",
    ):
        TaskAssigneeService.remove_assignee(
            db,
            actor=member,
            assignment=assignment,
            commit=False,
        )


def test_remove_assignee_records_history_event(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    assignee = _create_eligible_assignee(
        db,
        company=company,
        section=section,
        display_name="Removed User",
    )

    assignment = create_task_assignee(
        db,
        task=task,
        user=assignee,
    )

    TaskAssigneeService.remove_assignee(
        db,
        actor=creator,
        assignment=assignment,
        commit=False,
    )

    events = TaskHistoryRepository.list_for_task(
        db,
        task_id=task.id,
    )

    assert len(events) == 1
    assert (
        events[0].event_type
        == TaskHistoryEventType.ASSIGNEE_REMOVED.value
    )
    assert events[0].metadata_json["assignee_user_id"] == (
        assignee.id
    )


def test_remove_assignee_records_audit_log(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    assignee = _create_eligible_assignee(
        db,
        company=company,
        section=section,
        display_name="Removed User",
    )

    assignment = create_task_assignee(
        db,
        task=task,
        user=assignee,
    )

    TaskAssigneeService.remove_assignee(
        db,
        actor=creator,
        assignment=assignment,
        commit=False,
    )

    audit_logs = AuditRepository.list_logs(
        db,
        action=AuditAction.TASK_ASSIGNEE_REMOVED.value,
    )

    matching = [
        log
        for log in audit_logs
        if (
            log.entity_type == "task"
            and log.entity_id == task.id
        )
    ]

    assert len(matching) == 1
    assert (
        matching[0].metadata_json["assignee_user_id"]
        == assignee.id
    )


def test_replace_assignees_adds_and_removes_assignments(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    retained_user = _create_eligible_assignee(
        db,
        company=company,
        section=section,
        display_name="Retained User",
    )

    removed_user = _create_eligible_assignee(
        db,
        company=company,
        section=section,
        display_name="Removed User",
    )

    added_user = _create_eligible_assignee(
        db,
        company=company,
        section=section,
        display_name="Added User",
    )

    create_task_assignee(
        db,
        task=task,
        user=retained_user,
    )

    create_task_assignee(
        db,
        task=task,
        user=removed_user,
    )

    result = TaskAssigneeService.replace_assignees(
        db,
        actor=creator,
        task=task,
        replace_request=TaskAssigneeReplaceRequest(
            user_ids=[
                retained_user.id,
                added_user.id,
            ],
        ),
        commit=False,
    )

    assert {
        assignment.user_id
        for assignment in result
    } == {
        retained_user.id,
        added_user.id,
    }

    assert TaskAssigneeService.get_assignment(
        db,
        task_id=task.id,
        user_id=removed_user.id,
    ) is None


def test_replace_assignees_can_remove_all_assignments(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    assignee = _create_eligible_assignee(
        db,
        company=company,
        section=section,
    )

    create_task_assignee(
        db,
        task=task,
        user=assignee,
    )

    result = TaskAssigneeService.replace_assignees(
        db,
        actor=creator,
        task=task,
        replace_request=TaskAssigneeReplaceRequest(
            user_ids=[],
        ),
        commit=False,
    )

    assert result == []


def test_replace_assignees_rejects_ineligible_user_before_mutation(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    existing_user = _create_eligible_assignee(
        db,
        company=company,
        section=section,
    )

    existing_assignment = create_task_assignee(
        db,
        task=task,
        user=existing_user,
    )

    ineligible_user = create_user(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=ineligible_user,
    )

    with pytest.raises(
        TaskAssigneeSectionAccessRequiredError,
        match="does not have access",
    ):
        TaskAssigneeService.replace_assignees(
            db,
            actor=creator,
            task=task,
            replace_request=TaskAssigneeReplaceRequest(
                user_ids=[
                    ineligible_user.id,
                ],
            ),
            commit=False,
        )

    stored_assignment = TaskAssigneeService.get_assignment(
        db,
        task_id=task.id,
        user_id=existing_user.id,
    )

    assert stored_assignment is existing_assignment


def test_replace_assignees_records_added_and_removed_history(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    removed_user = _create_eligible_assignee(
        db,
        company=company,
        section=section,
        display_name="Removed User",
    )

    added_user = _create_eligible_assignee(
        db,
        company=company,
        section=section,
        display_name="Added User",
    )

    create_task_assignee(
        db,
        task=task,
        user=removed_user,
    )

    TaskAssigneeService.replace_assignees(
        db,
        actor=creator,
        task=task,
        replace_request=TaskAssigneeReplaceRequest(
            user_ids=[
                added_user.id,
            ],
        ),
        commit=False,
    )

    events = TaskHistoryRepository.list_for_task(
        db,
        task_id=task.id,
    )

    assert {
        event.event_type
        for event in events
    } == {
        TaskHistoryEventType.ASSIGNEE_ADDED.value,
        TaskHistoryEventType.ASSIGNEE_REMOVED.value,
    }


def test_replace_assignees_records_single_update_audit_log(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    removed_user = _create_eligible_assignee(
        db,
        company=company,
        section=section,
    )

    added_user = _create_eligible_assignee(
        db,
        company=company,
        section=section,
    )

    create_task_assignee(
        db,
        task=task,
        user=removed_user,
    )

    TaskAssigneeService.replace_assignees(
        db,
        actor=creator,
        task=task,
        replace_request=TaskAssigneeReplaceRequest(
            user_ids=[
                added_user.id,
            ],
        ),
        commit=False,
    )

    audit_logs = AuditRepository.list_logs(
        db,
        action=AuditAction.TASK_UPDATED.value,
    )

    matching = [
        log
        for log in audit_logs
        if (
            log.entity_type == "task"
            and log.entity_id == task.id
        )
    ]

    assert len(matching) == 1

    assert matching[0].metadata_json["added_user_ids"] == [
        added_user.id,
    ]

    assert matching[0].metadata_json["removed_user_ids"] == [
        removed_user.id,
    ]


def test_replace_assignees_with_unchanged_users_is_noop(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        _,
        task,
    ) = _create_context(
        db,
    )

    assignee = _create_eligible_assignee(
        db,
        company=company,
        section=section,
    )

    assignment = create_task_assignee(
        db,
        task=task,
        user=assignee,
    )

    result = TaskAssigneeService.replace_assignees(
        db,
        actor=creator,
        task=task,
        replace_request=TaskAssigneeReplaceRequest(
            user_ids=[
                assignee.id,
            ],
        ),
        commit=False,
    )

    assert result == [
        assignment,
    ]

    events = TaskHistoryRepository.list_for_task(
        db,
        task_id=task.id,
    )

    assert events == []

    audit_logs = AuditRepository.list_logs(
        db,
        action=AuditAction.TASK_UPDATED.value,
    )

    assert all(
        log.entity_id != task.id
        for log in audit_logs
    )