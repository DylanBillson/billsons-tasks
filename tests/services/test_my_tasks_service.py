from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.timezone import utc_now
from app.schemas.my_tasks import (
    MyTasksData,
    MyTasksFilterOptions,
)
from app.services.task_service import (
    MyTasksFilterError,
    TaskService,
)
from tests.factories import (
    create_company,
    create_section,
    create_section_list,
    create_task,
    create_task_assignee,
    create_user,
)


def _create_context(
    db: Session,
):
    user = create_user(
        db,
        display_name="Assigned User",
    )

    creator = create_user(
        db,
    )

    company = create_company(
        db,
        name="Service Company",
    )

    section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Service Section",
    )

    section_list = create_section_list(
        db,
        section=section,
        name="Service List",
    )

    return (
        user,
        creator,
        company,
        section,
        section_list,
    )


def test_get_my_tasks_returns_structured_data(
    db: Session,
) -> None:
    (
        user,
        creator,
        company,
        section,
        section_list,
    ) = _create_context(
        db,
    )

    task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Assigned Service Task",
        due_at=utc_now() + timedelta(
            days=1,
        ),
    )

    create_task_assignee(
        db,
        task=task,
        user=user,
    )

    result = TaskService.get_my_tasks(
        db,
        actor=user,
    )

    assert isinstance(
        result,
        MyTasksData,
    )

    assert result.metrics.all_count == 1
    assert result.metrics.open_count == 1

    assert len(
        result.tasks,
    ) == 1

    summary = result.tasks[0]

    assert summary.id == task.id
    assert summary.company_id == company.id
    assert summary.section_id == section.id
    assert summary.section_list_id == section_list.id
    assert summary.assignee_names == [
        "Assigned User",
    ]


def test_get_my_tasks_defaults_to_open_tasks(
    db: Session,
) -> None:
    (
        user,
        creator,
        _,
        _,
        section_list,
    ) = _create_context(
        db,
    )

    open_task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
    )

    completed_task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        completed_by=creator,
    )

    create_task_assignee(
        db,
        task=open_task,
        user=user,
    )

    create_task_assignee(
        db,
        task=completed_task,
        user=user,
    )

    result = TaskService.get_my_tasks(
        db,
        actor=user,
    )

    assert [
        task.id
        for task in result.tasks
    ] == [
        open_task.id,
    ]

    assert result.metrics.completed_count == 1


def test_get_my_tasks_applies_search_filter(
    db: Session,
) -> None:
    (
        user,
        creator,
        _,
        _,
        section_list,
    ) = _create_context(
        db,
    )

    matching = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Order coffee beans",
    )

    hidden = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Clean cellar",
    )

    create_task_assignee(
        db,
        task=matching,
        user=user,
    )

    create_task_assignee(
        db,
        task=hidden,
        user=user,
    )

    result = TaskService.get_my_tasks(
        db,
        actor=user,
        filters=MyTasksFilterOptions(
            state="all",
            search="coffee",
        ),
    )

    assert [
        task.id
        for task in result.tasks
    ] == [
        matching.id,
    ]


def test_get_my_tasks_rejects_unavailable_company_filter(
    db: Session,
) -> None:
    (
        user,
        _,
        _,
        _,
        _,
    ) = _create_context(
        db,
    )

    other_company = create_company(
        db,
    )

    with pytest.raises(
        MyTasksFilterError,
        match="company is not available",
    ):
        TaskService.get_my_tasks(
            db,
            actor=user,
            filters=MyTasksFilterOptions(
                company_id=other_company.id,
            ),
        )


def test_get_my_tasks_rejects_section_outside_selected_company(
    db: Session,
) -> None:
    (
        user,
        creator,
        company,
        _,
        section_list,
    ) = _create_context(
        db,
    )

    assigned_task = create_task(
        db,
        section_list=section_list,
        created_by=creator,
    )

    create_task_assignee(
        db,
        task=assigned_task,
        user=user,
    )

    other_company = create_company(
        db,
    )

    other_section = create_section(
        db,
        company=other_company,
        created_by=creator,
    )

    other_list = create_section_list(
        db,
        section=other_section,
    )

    other_task = create_task(
        db,
        section_list=other_list,
        created_by=creator,
    )

    create_task_assignee(
        db,
        task=other_task,
        user=user,
    )

    with pytest.raises(
        MyTasksFilterError,
        match="section is not available",
    ):
        TaskService.get_my_tasks(
            db,
            actor=user,
            filters=MyTasksFilterOptions(
                company_id=company.id,
                section_id=other_section.id,
            ),
        )


def test_get_my_tasks_rejects_inactive_user(
    db: Session,
) -> None:
    user = create_user(
        db,
        is_active=False,
    )

    with pytest.raises(
        MyTasksFilterError,
        match="active user account",
    ):
        TaskService.get_my_tasks(
            db,
            actor=user,
        )


def test_get_my_tasks_rejects_invalid_timezone(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    with pytest.raises(
        MyTasksFilterError,
        match="timezone is invalid",
    ):
        TaskService.get_my_tasks(
            db,
            actor=user,
            timezone_name="Invalid/Timezone",
        )


def test_get_my_tasks_rejects_invalid_due_soon_period(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    with pytest.raises(
        MyTasksFilterError,
        match="at least one day",
    ):
        TaskService.get_my_tasks(
            db,
            actor=user,
            due_soon_days=0,
        )