from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from app.auth.permissions import PermissionDeniedError
from app.core.constants import (
    AuditAction,
    CompanyRole,
    TaskHistoryEventType,
)
from app.core.timezone import utc_now
from app.repositories.audit_repository import AuditRepository
from app.repositories.task_assignee_repository import (
    TaskAssigneeRepository,
)
from app.repositories.task_history_repository import (
    TaskHistoryRepository,
)
from app.schemas.task import (
    TaskCreateRequest,
    TaskFilterOptions,
    TaskMoveRequest,
    TaskPositionUpdate,
    TaskReorderRequest,
    TaskUpdateRequest,
)
from app.services.task_service import (
    TaskAlreadyCompletedError,
    TaskAlreadyDeletedError,
    TaskDestinationListNotFoundError,
    TaskNotCompletedError,
    TaskNotDeletedError,
    TaskNotFoundError,
    TaskReorderError,
    TaskService,
    TaskServiceError,
)
from app.services.live_update_service import (
    LiveUpdateService,
)
from app.services.task_service import (
    TaskAlreadyCompletedError,
    TaskAlreadyDeletedError,
    TaskDestinationListNotFoundError,
    TaskLiveUpdateConflictError,
    TaskNotCompletedError,
    TaskNotDeletedError,
    TaskNotFoundError,
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
        name="Operations",
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

    return (
        company,
        section_creator,
        section,
        first_list,
        second_list,
    )


def _create_section_member(
    db: Session,
    *,
    company,
    section,
    display_name: str | None = None,
):
    member = create_user(
        db,
        display_name=display_name,
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


def _history_events(
    db: Session,
    *,
    task_id: int,
):
    return TaskHistoryRepository.list_for_task(
        db,
        task_id=task_id,
    )


def _audit_logs_for_task(
    db: Session,
    *,
    task_id: int,
    action: AuditAction,
):
    logs = AuditRepository.list_logs(
        db,
        action=action.value,
    )

    return [
        log
        for log in logs
        if (
            log.entity_type == "task"
            and log.entity_id == task_id
        )
    ]


def test_get_task_returns_existing_task(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    result = TaskService.get_task(
        db,
        task_id=task.id,
    )

    assert result is task


def test_get_task_returns_none_for_unknown_task(
    db: Session,
) -> None:
    result = TaskService.get_task(
        db,
        task_id=999999,
    )

    assert result is None


def test_require_task_returns_existing_task(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    result = TaskService.require_task(
        db,
        task_id=task.id,
    )

    assert result is task


def test_require_task_raises_for_unknown_task(
    db: Session,
) -> None:
    with pytest.raises(
        TaskNotFoundError,
        match="Task was not found",
    ):
        TaskService.require_task(
            db,
            task_id=999999,
        )


def test_get_accessible_task_returns_task_for_section_member(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    result = TaskService.get_accessible_task(
        db,
        actor=member,
        task_id=task.id,
    )

    assert result is task


def test_get_accessible_task_denies_outsider(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    outsider = create_user(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="access to this task",
    ):
        TaskService.get_accessible_task(
            db,
            actor=outsider,
            task_id=task.id,
        )


def test_list_for_section_returns_accessible_tasks(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        first_list,
        second_list,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    first_task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        sort_position=1000,
    )

    second_task = create_task(
        db,
        section_list=second_list,
        created_by=creator,
        sort_position=1000,
    )

    result = TaskService.list_for_section(
        db,
        actor=member,
        section=section,
    )

    assert result == [
        first_task,
        second_task,
    ]


def test_list_for_section_denies_unassigned_company_manager(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
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

    with pytest.raises(
        PermissionDeniedError,
        match="access to this section",
    ):
        TaskService.list_for_section(
            db,
            actor=manager,
            section=section,
        )


def test_list_for_section_applies_filters(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        first_list,
        second_list,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    matching = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        title="Order coffee beans",
    )

    create_task(
        db,
        section_list=first_list,
        created_by=creator,
        title="Clean cellar",
    )

    create_task(
        db,
        section_list=second_list,
        created_by=creator,
        title="Order coffee filters",
    )

    result = TaskService.list_for_section(
        db,
        actor=member,
        section=section,
        filters=TaskFilterOptions(
            section_list_id=first_list.id,
            search="coffee",
        ),
    )

    assert result == [
        matching,
    ]


def test_list_for_section_rejects_foreign_list_filter(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        _,
        _,
    ) = _create_context(
        db,
    )

    other_section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Other Section",
    )

    foreign_list = create_section_list(
        db,
        section=other_section,
        name="Foreign List",
    )

    with pytest.raises(
        TaskServiceError,
        match="does not belong to this section",
    ):
        TaskService.list_for_section(
            db,
            actor=creator,
            section=section,
            filters=TaskFilterOptions(
                section_list_id=foreign_list.id,
            ),
        )


def test_section_member_creates_task(
    db: Session,
) -> None:
    (
        company,
        _,
        section,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
        display_name="Task Creator",
    )

    due_at = utc_now() + timedelta(
        days=2,
    )

    task = TaskService.create_task(
        db,
        actor=member,
        section_list=first_list,
        task_create=TaskCreateRequest(
            section_list_id=first_list.id,
            title="  Order supplies  ",
            description="  Order bar supplies.  ",
            due_at=due_at,
        ),
        commit=False,
    )

    assert task.id is not None
    assert task.section_list_id == first_list.id
    assert task.created_by_user_id == member.id
    assert task.title == "Order supplies"
    assert task.description == "Order bar supplies."
    assert task.due_at == due_at
    assert task.sort_position == 1000


def test_create_task_rejects_mismatched_list_id(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        second_list,
    ) = _create_context(
        db,
    )

    with pytest.raises(
        TaskServiceError,
        match="does not match the selected list",
    ):
        TaskService.create_task(
            db,
            actor=creator,
            section_list=first_list,
            task_create=TaskCreateRequest(
                section_list_id=second_list.id,
                title="Invalid task",
            ),
            commit=False,
        )


def test_user_without_section_access_cannot_create_task(
    db: Session,
) -> None:
    (
        company,
        _,
        _,
        first_list,
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

    with pytest.raises(
        PermissionDeniedError,
        match="create tasks",
    ):
        TaskService.create_task(
            db,
            actor=company_member,
            section_list=first_list,
            task_create=TaskCreateRequest(
                section_list_id=first_list.id,
                title="Unauthorised task",
            ),
            commit=False,
        )


def test_create_task_rejects_archived_list(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    first_list.is_archived = True
    db.flush()

    with pytest.raises(
        PermissionDeniedError,
        match="create tasks",
    ):
        TaskService.create_task(
            db,
            actor=creator,
            section_list=first_list,
            task_create=TaskCreateRequest(
                section_list_id=first_list.id,
                title="Task in archived list",
            ),
            commit=False,
        )


def test_create_task_uses_next_sort_position(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    create_task(
        db,
        section_list=first_list,
        created_by=creator,
        sort_position=3000,
    )

    task = TaskService.create_task(
        db,
        actor=creator,
        section_list=first_list,
        task_create=TaskCreateRequest(
            section_list_id=first_list.id,
            title="Next task",
        ),
        commit=False,
    )

    assert task.sort_position == 4000


def test_section_creator_creates_task_with_assignees(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    assignee = _create_section_member(
        db,
        company=company,
        section=section,
        display_name="Assigned User",
    )

    task = TaskService.create_task(
        db,
        actor=creator,
        section_list=first_list,
        task_create=TaskCreateRequest(
            section_list_id=first_list.id,
            title="Assigned task",
            assignee_user_ids=[
                assignee.id,
            ],
        ),
        commit=False,
    )

    assignments = TaskAssigneeRepository.list_for_task(
        db,
        task_id=task.id,
    )

    assert len(assignments) == 1
    assert assignments[0].user_id == assignee.id


def test_create_task_records_history_event(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    task = TaskService.create_task(
        db,
        actor=creator,
        section_list=first_list,
        task_create=TaskCreateRequest(
            section_list_id=first_list.id,
            title="History task",
        ),
        commit=False,
    )

    events = _history_events(
        db,
        task_id=task.id,
    )

    assert len(events) == 1
    assert events[0].event_type == (
        TaskHistoryEventType.CREATED.value
    )
    assert events[0].user_id == creator.id


def test_create_task_records_audit_log(
    db: Session,
) -> None:
    (
        _,
        creator,
        section,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    task = TaskService.create_task(
        db,
        actor=creator,
        section_list=first_list,
        task_create=TaskCreateRequest(
            section_list_id=first_list.id,
            title="Audited task",
        ),
        ip_address="192.0.2.40",
        user_agent="pytest task service",
        commit=False,
    )

    logs = _audit_logs_for_task(
        db,
        task_id=task.id,
        action=AuditAction.TASK_CREATED,
    )

    assert len(logs) == 1
    assert logs[0].user_id == creator.id
    assert logs[0].metadata_json["section_id"] == section.id
    assert logs[0].metadata_json["section_list_id"] == (
        first_list.id
    )
    assert logs[0].metadata_json["title"] == "Audited task"
    assert logs[0].ip_address == "192.0.2.40"


def test_create_task_by_list_id_rejects_unknown_list(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        _,
        _,
    ) = _create_context(
        db,
    )

    with pytest.raises(
        TaskDestinationListNotFoundError,
        match="List was not found",
    ):
        TaskService.create_task_by_list_id(
            db,
            actor=creator,
            section_list_id=999999,
            task_create=TaskCreateRequest(
                section_list_id=999999,
                title="Missing list",
            ),
            commit=False,
        )


def test_section_member_updates_task(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        title="Old title",
        description="Old description.",
    )

    due_at = utc_now() + timedelta(
        days=3,
    )

    result = TaskService.update_task(
        db,
        actor=member,
        task=task,
        task_update=TaskUpdateRequest(
            title="New title",
            description="New description.",
            due_at=due_at,
        ),
        commit=False,
    )

    assert result is task
    assert task.title == "New title"
    assert task.description == "New description."
    assert task.due_at == due_at


def test_outsider_cannot_update_task(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    outsider = create_user(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="update this task",
    ):
        TaskService.update_task(
            db,
            actor=outsider,
            task=task,
            task_update=TaskUpdateRequest(
                title="Unauthorised update",
            ),
            commit=False,
        )


def test_update_task_with_no_changes_is_noop(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        title="Unchanged",
        description="Unchanged description.",
    )

    result = TaskService.update_task(
        db,
        actor=creator,
        task=task,
        task_update=TaskUpdateRequest(
            title="Unchanged",
            description="Unchanged description.",
            due_at=None,
        ),
        commit=False,
    )

    assert result is task
    assert _history_events(
        db,
        task_id=task.id,
    ) == []

    assert _audit_logs_for_task(
        db,
        task_id=task.id,
        action=AuditAction.TASK_UPDATED,
    ) == []


def test_update_task_records_changes_in_history(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        title="Old title",
    )

    TaskService.update_task(
        db,
        actor=creator,
        task=task,
        task_update=TaskUpdateRequest(
            title="New title",
        ),
        commit=False,
    )

    events = _history_events(
        db,
        task_id=task.id,
    )

    assert len(events) == 1
    assert events[0].event_type == (
        TaskHistoryEventType.UPDATED.value
    )

    assert events[0].metadata_json["changes"]["title"] == {
        "previous": "Old title",
        "current": "New title",
    }


def test_section_member_moves_task_within_section(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        first_list,
        second_list,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    result = TaskService.move_task(
        db,
        actor=member,
        task=task,
        destination_list=second_list,
        move_request=TaskMoveRequest(
            destination_list_id=second_list.id,
            sort_position=500,
        ),
        commit=False,
    )

    assert result is task
    assert task.section_list_id == second_list.id
    assert task.sort_position == 500


def test_move_task_rejects_mismatched_destination_id(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        second_list,
    ) = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    with pytest.raises(
        TaskServiceError,
        match="does not match the selected list",
    ):
        TaskService.move_task(
            db,
            actor=creator,
            task=task,
            destination_list=second_list,
            move_request=TaskMoveRequest(
                destination_list_id=first_list.id,
                sort_position=1000,
            ),
            commit=False,
        )


def test_move_task_rejects_cross_section_destination(
    db: Session,
) -> None:
    (
        company,
        creator,
        _,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    other_section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Other Section",
    )

    foreign_list = create_section_list(
        db,
        section=other_section,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="same section",
    ):
        TaskService.move_task(
            db,
            actor=creator,
            task=task,
            destination_list=foreign_list,
            move_request=TaskMoveRequest(
                destination_list_id=foreign_list.id,
                sort_position=1000,
            ),
            commit=False,
        )


def test_move_task_rejects_archived_destination(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        second_list,
    ) = _create_context(
        db,
    )

    second_list.is_archived = True
    db.flush()

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="archived list",
    ):
        TaskService.move_task(
            db,
            actor=creator,
            task=task,
            destination_list=second_list,
            move_request=TaskMoveRequest(
                destination_list_id=second_list.id,
                sort_position=1000,
            ),
            commit=False,
        )


def test_move_task_records_history_and_audit(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        second_list,
    ) = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        sort_position=1000,
    )

    TaskService.move_task(
        db,
        actor=creator,
        task=task,
        destination_list=second_list,
        move_request=TaskMoveRequest(
            destination_list_id=second_list.id,
            sort_position=2000,
        ),
        commit=False,
    )

    events = _history_events(
        db,
        task_id=task.id,
    )

    assert len(events) == 1
    assert events[0].event_type == (
        TaskHistoryEventType.MOVED.value
    )

    assert events[0].metadata_json["previous_list_id"] == (
        first_list.id
    )

    assert events[0].metadata_json["section_list_id"] == (
        second_list.id
    )

    logs = _audit_logs_for_task(
        db,
        task_id=task.id,
        action=AuditAction.TASK_MOVED,
    )

    assert len(logs) == 1


def test_section_member_reorders_tasks(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        first_list,
        second_list,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    first_task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        sort_position=1000,
    )

    second_task = create_task(
        db,
        section_list=second_list,
        created_by=creator,
        sort_position=1000,
    )

    result = TaskService.reorder_tasks(
        db,
        actor=member,
        section=section,
        reorder_request=TaskReorderRequest(
            items=[
                TaskPositionUpdate(
                    task_id=first_task.id,
                    section_list_id=second_list.id,
                    sort_position=2000,
                ),
                TaskPositionUpdate(
                    task_id=second_task.id,
                    section_list_id=first_list.id,
                    sort_position=500,
                ),
            ],
        ),
        commit=False,
    )

    assert first_task.section_list_id == second_list.id
    assert first_task.sort_position == 2000

    assert second_task.section_list_id == first_list.id
    assert second_task.sort_position == 500

    assert result == [
        second_task,
        first_task,
    ]


def test_reorder_tasks_rejects_foreign_list(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    other_section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Other Section",
    )

    foreign_list = create_section_list(
        db,
        section=other_section,
    )

    with pytest.raises(
        TaskReorderError,
        match="archived or does not belong",
    ):
        TaskService.reorder_tasks(
            db,
            actor=creator,
            section=section,
            reorder_request=TaskReorderRequest(
                items=[
                    TaskPositionUpdate(
                        task_id=task.id,
                        section_list_id=foreign_list.id,
                        sort_position=1000,
                    ),
                ],
            ),
            commit=False,
        )


def test_reorder_tasks_rejects_foreign_task(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    other_section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Other Section",
    )

    foreign_list = create_section_list(
        db,
        section=other_section,
    )

    foreign_task = create_task(
        db,
        section_list=foreign_list,
        created_by=creator,
    )

    with pytest.raises(
        TaskReorderError,
        match="deleted or does not belong",
    ):
        TaskService.reorder_tasks(
            db,
            actor=creator,
            section=section,
            reorder_request=TaskReorderRequest(
                items=[
                    TaskPositionUpdate(
                        task_id=foreign_task.id,
                        section_list_id=first_list.id,
                        sort_position=1000,
                    ),
                ],
            ),
            commit=False,
        )


def test_reorder_tasks_rejects_deleted_task(
    db: Session,
) -> None:
    (
        _,
        creator,
        section,
        first_list,
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

    with pytest.raises(
        TaskReorderError,
        match="deleted or does not belong",
    ):
        TaskService.reorder_tasks(
            db,
            actor=creator,
            section=section,
            reorder_request=TaskReorderRequest(
                items=[
                    TaskPositionUpdate(
                        task_id=deleted_task.id,
                        section_list_id=first_list.id,
                        sort_position=2000,
                    ),
                ],
            ),
            commit=False,
        )


def test_section_member_completes_task(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    result = TaskService.complete_task(
        db,
        actor=member,
        task=task,
        commit=False,
    )

    assert result is task
    assert task.completed_at is not None
    assert task.completed_by_user_id == member.id
    assert task.state == "completed"


def test_complete_task_rejects_already_completed_task(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        completed_by=creator,
    )

    with pytest.raises(
        TaskAlreadyCompletedError,
        match="already completed",
    ):
        TaskService.complete_task(
            db,
            actor=creator,
            task=task,
            commit=False,
        )


def test_complete_task_records_history_and_audit(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    TaskService.complete_task(
        db,
        actor=creator,
        task=task,
        commit=False,
    )

    events = _history_events(
        db,
        task_id=task.id,
    )

    assert len(events) == 1
    assert events[0].event_type == (
        TaskHistoryEventType.COMPLETED.value
    )

    logs = _audit_logs_for_task(
        db,
        task_id=task.id,
        action=AuditAction.TASK_COMPLETED,
    )

    assert len(logs) == 1


def test_section_member_reopens_task(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        completed_by=creator,
    )

    result = TaskService.reopen_task(
        db,
        actor=member,
        task=task,
        commit=False,
    )

    assert result is task
    assert task.completed_at is None
    assert task.completed_by_user_id is None
    assert task.state == "open"


def test_reopen_task_rejects_open_task(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    with pytest.raises(
        TaskNotCompletedError,
        match="not completed",
    ):
        TaskService.reopen_task(
            db,
            actor=creator,
            task=task,
            commit=False,
        )


def test_section_creator_soft_deletes_task(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    result = TaskService.delete_task(
        db,
        actor=creator,
        task=task,
        commit=False,
    )

    assert result is task
    assert task.deleted_at is not None
    assert task.deleted_by_user_id == creator.id
    assert task.state == "deleted"


def test_section_member_cannot_delete_task(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="delete this task",
    ):
        TaskService.delete_task(
            db,
            actor=member,
            task=task,
            commit=False,
        )


def test_delete_task_rejects_already_deleted_task(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        deleted_by=creator,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="delete this task",
    ):
        TaskService.delete_task(
            db,
            actor=creator,
            task=task,
            commit=False,
        )


def test_delete_task_records_history_and_audit(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    TaskService.delete_task(
        db,
        actor=creator,
        task=task,
        commit=False,
    )

    events = _history_events(
        db,
        task_id=task.id,
    )

    assert len(events) == 1
    assert events[0].event_type == (
        TaskHistoryEventType.DELETED.value
    )

    logs = _audit_logs_for_task(
        db,
        task_id=task.id,
        action=AuditAction.TASK_DELETED,
    )

    assert len(logs) == 1


def test_section_creator_restores_deleted_task(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        deleted_by=creator,
    )

    result = TaskService.restore_task(
        db,
        actor=creator,
        task=task,
        commit=False,
    )

    assert result is task
    assert task.deleted_at is None
    assert task.deleted_by_user_id is None
    assert task.state == "open"


def test_restore_task_rejects_active_task(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    with pytest.raises(
        TaskNotDeletedError,
        match="not deleted",
    ):
        TaskService.restore_task(
            db,
            actor=creator,
            task=task,
            commit=False,
        )


def test_section_member_cannot_restore_task(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        deleted_by=creator,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="restore this task",
    ):
        TaskService.restore_task(
            db,
            actor=member,
            task=task,
            commit=False,
        )


def test_restore_task_records_history_and_audit(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        deleted_by=creator,
    )

    TaskService.restore_task(
        db,
        actor=creator,
        task=task,
        commit=False,
    )

    events = _history_events(
        db,
        task_id=task.id,
    )

    assert len(events) == 1
    assert events[0].event_type == (
        TaskHistoryEventType.RESTORED.value
    )

    logs = _audit_logs_for_task(
        db,
        task_id=task.id,
        action=AuditAction.TASK_RESTORED,
    )

    assert len(logs) == 1


def test_administrator_permanently_deletes_deleted_task(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    administrator = create_administrator(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        deleted_by=creator,
    )

    task_id = task.id

    TaskService.permanently_delete_task(
        db,
        actor=administrator,
        task=task,
        commit=False,
    )

    assert TaskService.get_task(
        db,
        task_id=task_id,
    ) is None

    logs = _audit_logs_for_task(
        db,
        task_id=task_id,
        action=AuditAction.TASK_PERMANENTLY_DELETED,
    )

    assert len(logs) == 1


def test_permanent_delete_rejects_active_task(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    administrator = create_administrator(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    with pytest.raises(
        TaskNotDeletedError,
        match="Only deleted tasks",
    ):
        TaskService.permanently_delete_task(
            db,
            actor=administrator,
            task=task,
            commit=False,
        )


def test_non_administrator_cannot_permanently_delete_task(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        deleted_by=creator,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="Only administrators",
    ):
        TaskService.permanently_delete_task(
            db,
            actor=creator,
            task=task,
            commit=False,
        )
def test_reorder_tasks_requires_every_active_board_task(
    db: Session,
) -> None:
    (
        _,
        creator,
        section,
        first_list,
        second_list,
    ) = _create_context(
        db,
    )

    first_task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        sort_position=1000,
    )

    second_task = create_task(
        db,
        section_list=second_list,
        created_by=creator,
        sort_position=1000,
    )

    with pytest.raises(
        TaskReorderError,
        match="include every active task",
    ):
        TaskService.reorder_tasks(
            db,
            actor=creator,
            section=section,
            reorder_request=TaskReorderRequest(
                items=[
                    TaskPositionUpdate(
                        task_id=first_task.id,
                        section_list_id=first_list.id,
                        sort_position=2000,
                    ),
                ],
            ),
            commit=False,
        )

    assert first_task.section_list_id == first_list.id
    assert first_task.sort_position == 1000

    assert second_task.section_list_id == second_list.id
    assert second_task.sort_position == 1000


def test_reorder_tasks_ignores_deleted_tasks_when_checking_completeness(
    db: Session,
) -> None:
    (
        _,
        creator,
        section,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    active_task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        sort_position=1000,
    )

    deleted_task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        sort_position=2000,
        deleted_by=creator,
    )

    TaskService.reorder_tasks(
        db,
        actor=creator,
        section=section,
        reorder_request=TaskReorderRequest(
            items=[
                TaskPositionUpdate(
                    task_id=active_task.id,
                    section_list_id=first_list.id,
                    sort_position=3000,
                ),
            ],
        ),
        commit=False,
    )

    assert active_task.sort_position == 3000
    assert deleted_task.sort_position == 2000


def test_reorder_tasks_ignores_tasks_in_archived_lists_for_completeness(
    db: Session,
) -> None:
    (
        _,
        creator,
        section,
        first_list,
        second_list,
    ) = _create_context(
        db,
    )

    second_list.is_archived = True

    active_task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        sort_position=1000,
    )

    archived_list_task = create_task(
        db,
        section_list=second_list,
        created_by=creator,
        sort_position=1000,
    )

    db.flush()

    TaskService.reorder_tasks(
        db,
        actor=creator,
        section=section,
        reorder_request=TaskReorderRequest(
            items=[
                TaskPositionUpdate(
                    task_id=active_task.id,
                    section_list_id=first_list.id,
                    sort_position=2000,
                ),
            ],
        ),
        commit=False,
    )

    assert active_task.sort_position == 2000
    assert archived_list_task.sort_position == 1000


def test_reorder_tasks_rejects_archived_destination_list(
    db: Session,
) -> None:
    (
        _,
        creator,
        section,
        first_list,
        second_list,
    ) = _create_context(
        db,
    )

    second_list.is_archived = True

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        sort_position=1000,
    )

    db.flush()

    with pytest.raises(
        TaskReorderError,
        match="archived or does not belong",
    ):
        TaskService.reorder_tasks(
            db,
            actor=creator,
            section=section,
            reorder_request=TaskReorderRequest(
                items=[
                    TaskPositionUpdate(
                        task_id=task.id,
                        section_list_id=second_list.id,
                        sort_position=1000,
                    ),
                ],
            ),
            commit=False,
        )

    assert task.section_list_id == first_list.id
    assert task.sort_position == 1000


def test_reorder_tasks_with_unchanged_positions_is_noop(
    db: Session,
) -> None:
    (
        _,
        creator,
        section,
        first_list,
        second_list,
    ) = _create_context(
        db,
    )

    first_task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        sort_position=1000,
    )

    second_task = create_task(
        db,
        section_list=second_list,
        created_by=creator,
        sort_position=1000,
    )

    result = TaskService.reorder_tasks(
        db,
        actor=creator,
        section=section,
        reorder_request=TaskReorderRequest(
            items=[
                TaskPositionUpdate(
                    task_id=first_task.id,
                    section_list_id=first_list.id,
                    sort_position=1000,
                ),
                TaskPositionUpdate(
                    task_id=second_task.id,
                    section_list_id=second_list.id,
                    sort_position=1000,
                ),
            ],
        ),
        commit=False,
    )

    assert result == [
        first_task,
        second_task,
    ]

    audit_logs = AuditRepository.list_logs(
        db,
        action=AuditAction.TASK_MOVED.value,
    )

    assert all(
        not (
            log.entity_type == "section"
            and log.entity_id == section.id
        )
        for log in audit_logs
    )


def test_reorder_tasks_audit_records_previous_and_current_positions(
    db: Session,
) -> None:
    (
        company,
        creator,
        section,
        first_list,
        second_list,
    ) = _create_context(
        db,
    )

    first_task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        sort_position=1000,
    )

    second_task = create_task(
        db,
        section_list=second_list,
        created_by=creator,
        sort_position=1000,
    )

    TaskService.reorder_tasks(
        db,
        actor=creator,
        section=section,
        reorder_request=TaskReorderRequest(
            items=[
                TaskPositionUpdate(
                    task_id=first_task.id,
                    section_list_id=second_list.id,
                    sort_position=2000,
                ),
                TaskPositionUpdate(
                    task_id=second_task.id,
                    section_list_id=second_list.id,
                    sort_position=1000,
                ),
            ],
        ),
        commit=False,
    )

    audit_logs = AuditRepository.list_logs(
        db,
        action=AuditAction.TASK_MOVED.value,
    )

    matching = [
        log
        for log in audit_logs
        if (
            log.entity_type == "section"
            and log.entity_id == section.id
        )
    ]

    assert len(matching) == 1

    metadata = matching[0].metadata_json

    assert metadata["company_id"] == company.id
    assert metadata["section_id"] == section.id

    assert metadata["task_positions"] == {
        str(first_task.id): {
            "previous_section_list_id": first_list.id,
            "section_list_id": second_list.id,
            "previous_sort_position": 1000,
            "sort_position": 2000,
        },
    }

def test_update_task_changes_live_update_revision(
    db: Session,
) -> None:
    (
        _,
        creator,
        section,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        title="Original title",
    )

    before = LiveUpdateService.get_section_revision(
        db,
        actor=creator,
        section_id=section.id,
    )

    TaskService.update_task(
        db,
        actor=creator,
        task=task,
        task_update=TaskUpdateRequest(
            title="Updated title",
        ),
        commit=False,
    )

    db.flush()

    after = LiveUpdateService.get_section_revision(
        db,
        actor=creator,
        section_id=section.id,
    )

    assert before.revision != after.revision


def test_move_task_accepts_current_revision(
    db: Session,
) -> None:
    (
        _,
        creator,
        section,
        first_list,
        second_list,
    ) = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        sort_position=1000,
    )

    revision = LiveUpdateService.get_section_revision(
        db,
        actor=creator,
        section_id=section.id,
    )

    result = TaskService.move_task(
        db,
        actor=creator,
        task=task,
        destination_list=second_list,
        move_request=TaskMoveRequest(
            destination_list_id=second_list.id,
            sort_position=2000,
            known_revision=revision.revision,
        ),
        commit=False,
    )

    assert result is task
    assert task.section_list_id == second_list.id
    assert task.sort_position == 2000


def test_move_task_rejects_stale_revision(
    db: Session,
) -> None:
    (
        _,
        creator,
        section,
        first_list,
        second_list,
    ) = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        sort_position=1000,
    )

    stale_revision = (
        LiveUpdateService.get_section_revision(
            db,
            actor=creator,
            section_id=section.id,
        )
    )

    task.title = "Changed by another user"
    task.updated_at = (
        utc_now()
        + timedelta(
            seconds=1,
        )
    )

    db.flush()

    with pytest.raises(
        TaskLiveUpdateConflictError,
        match="board changed",
    ) as exc_info:
        TaskService.move_task(
            db,
            actor=creator,
            task=task,
            destination_list=second_list,
            move_request=TaskMoveRequest(
                destination_list_id=second_list.id,
                sort_position=2000,
                known_revision=(
                    stale_revision.revision
                ),
            ),
            commit=False,
        )

    assert (
        exc_info.value.current_revision
        != stale_revision.revision
    )

    assert task.section_list_id == first_list.id
    assert task.sort_position == 1000


def test_reorder_tasks_rejects_stale_revision(
    db: Session,
) -> None:
    (
        _,
        creator,
        section,
        first_list,
        second_list,
    ) = _create_context(
        db,
    )

    first_task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
        sort_position=1000,
    )

    second_task = create_task(
        db,
        section_list=second_list,
        created_by=creator,
        sort_position=1000,
    )

    stale_revision = (
        LiveUpdateService.get_section_revision(
            db,
            actor=creator,
            section_id=section.id,
        )
    )

    second_task.title = "Concurrent update"
    second_task.updated_at = (
        utc_now()
        + timedelta(
            seconds=1,
        )
    )

    db.flush()

    with pytest.raises(
        TaskLiveUpdateConflictError,
        match="board changed",
    ):
        TaskService.reorder_tasks(
            db,
            actor=creator,
            section=section,
            reorder_request=TaskReorderRequest(
                known_revision=(
                    stale_revision.revision
                ),
                items=[
                    TaskPositionUpdate(
                        task_id=first_task.id,
                        section_list_id=second_list.id,
                        sort_position=2000,
                    ),
                    TaskPositionUpdate(
                        task_id=second_task.id,
                        section_list_id=first_list.id,
                        sort_position=500,
                    ),
                ],
            ),
            commit=False,
        )

    assert first_task.section_list_id == first_list.id
    assert first_task.sort_position == 1000

    assert second_task.section_list_id == second_list.id
    assert second_task.sort_position == 1000


def test_task_state_mutations_touch_updated_at(
    db: Session,
) -> None:
    (
        _,
        creator,
        _,
        first_list,
        _,
    ) = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=first_list,
        created_by=creator,
    )

    original_updated_at = task.updated_at

    TaskService.complete_task(
        db,
        actor=creator,
        task=task,
        commit=False,
    )

    assert task.updated_at >= original_updated_at

    completed_updated_at = task.updated_at

    TaskService.reopen_task(
        db,
        actor=creator,
        task=task,
        commit=False,
    )

    assert task.updated_at >= completed_updated_at

    reopened_updated_at = task.updated_at

    TaskService.delete_task(
        db,
        actor=creator,
        task=task,
        commit=False,
    )

    assert task.updated_at >= reopened_updated_at