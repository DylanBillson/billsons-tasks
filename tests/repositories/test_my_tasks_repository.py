from datetime import (
    datetime,
    timedelta,
    timezone,
)

from sqlalchemy.orm import Session

from app.core.timezone import utc_now
from app.repositories.task_repository import (
    TaskRepository,
)
from tests.factories import (
    create_company,
    create_section,
    create_section_list,
    create_task,
    create_task_assignee,
    create_user,
)


def _date_boundaries():
    now = utc_now()

    today_start = datetime.combine(
        now.date(),
        datetime.min.time(),
        tzinfo=timezone.utc,
    )

    tomorrow_start = today_start + timedelta(
        days=1,
    )

    due_soon_end = now + timedelta(
        days=7,
    )

    return (
        now,
        today_start,
        tomorrow_start,
        due_soon_end,
    )


def _create_context(
    db: Session,
):
    user = create_user(
        db,
    )

    creator = create_user(
        db,
    )

    company = create_company(
        db,
        name="My Tasks Company",
    )

    section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Operations",
    )

    section_list = create_section_list(
        db,
        section=section,
        name="To Do",
    )

    return (
        user,
        creator,
        company,
        section,
        section_list,
    )


def test_list_my_tasks_returns_only_assigned_tasks(
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

    assigned = create_task(
        db,
        section_list=section_list,
        created_by=creator,
    )

    create_task_assignee(
        db,
        task=assigned,
        user=user,
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
    )

    (
        now,
        today_start,
        tomorrow_start,
        due_soon_end,
    ) = _date_boundaries()

    result = TaskRepository.list_my_tasks(
        db,
        user_id=user.id,
        state="all",
        now=now,
        today_start=today_start,
        tomorrow_start=tomorrow_start,
        due_soon_end=due_soon_end,
    )

    assert result == [
        assigned,
    ]


def test_list_my_tasks_excludes_deleted_tasks(
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

    deleted = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        deleted_by=creator,
    )

    create_task_assignee(
        db,
        task=deleted,
        user=user,
    )

    (
        now,
        today_start,
        tomorrow_start,
        due_soon_end,
    ) = _date_boundaries()

    result = TaskRepository.list_my_tasks(
        db,
        user_id=user.id,
        state="all",
        now=now,
        today_start=today_start,
        tomorrow_start=tomorrow_start,
        due_soon_end=due_soon_end,
    )

    assert result == []


def test_list_my_tasks_filters_overdue_tasks(
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

    now = utc_now()

    overdue = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        due_at=now - timedelta(
            hours=1,
        ),
    )

    future = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        due_at=now + timedelta(
            days=1,
        ),
    )

    create_task_assignee(
        db,
        task=overdue,
        user=user,
    )

    create_task_assignee(
        db,
        task=future,
        user=user,
    )

    (
        _,
        today_start,
        tomorrow_start,
        due_soon_end,
    ) = _date_boundaries()

    result = TaskRepository.list_my_tasks(
        db,
        user_id=user.id,
        state="overdue",
        now=now,
        today_start=today_start,
        tomorrow_start=tomorrow_start,
        due_soon_end=due_soon_end,
    )

    assert result == [
        overdue,
    ]


def test_list_my_tasks_filters_due_today(
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

    (
        now,
        today_start,
        tomorrow_start,
        due_soon_end,
    ) = _date_boundaries()

    due_today = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        due_at=today_start + timedelta(
            hours=12,
        ),
    )

    due_later = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        due_at=tomorrow_start + timedelta(
            hours=1,
        ),
    )

    create_task_assignee(
        db,
        task=due_today,
        user=user,
    )

    create_task_assignee(
        db,
        task=due_later,
        user=user,
    )

    result = TaskRepository.list_my_tasks(
        db,
        user_id=user.id,
        state="due_today",
        now=now,
        today_start=today_start,
        tomorrow_start=tomorrow_start,
        due_soon_end=due_soon_end,
    )

    assert result == [
        due_today,
    ]


def test_list_my_tasks_filters_by_company_section_and_search(
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

    matching = create_task(
        db,
        section_list=section_list,
        created_by=creator,
        title="Order coffee",
    )

    create_task_assignee(
        db,
        task=matching,
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
        title="Order coffee elsewhere",
    )

    create_task_assignee(
        db,
        task=other_task,
        user=user,
    )

    (
        now,
        today_start,
        tomorrow_start,
        due_soon_end,
    ) = _date_boundaries()

    result = TaskRepository.list_my_tasks(
        db,
        user_id=user.id,
        state="all",
        now=now,
        today_start=today_start,
        tomorrow_start=tomorrow_start,
        due_soon_end=due_soon_end,
        company_id=company.id,
        section_id=section.id,
        search="coffee",
    )

    assert result == [
        matching,
    ]


def test_get_my_tasks_metrics_returns_state_counts(
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

    (
        now,
        today_start,
        tomorrow_start,
        due_soon_end,
    ) = _date_boundaries()

    tasks = [
        create_task(
            db,
            section_list=section_list,
            created_by=creator,
        ),
        create_task(
            db,
            section_list=section_list,
            created_by=creator,
            due_at=now - timedelta(
                hours=1,
            ),
        ),
        create_task(
            db,
            section_list=section_list,
            created_by=creator,
            due_at=now + timedelta(
                hours=1,
            ),
        ),
        create_task(
            db,
            section_list=section_list,
            created_by=creator,
            completed_by=creator,
        ),
    ]

    for task in tasks:
        create_task_assignee(
            db,
            task=task,
            user=user,
        )

    result = TaskRepository.get_my_tasks_metrics(
        db,
        user_id=user.id,
        now=now,
        today_start=today_start,
        tomorrow_start=tomorrow_start,
        due_soon_end=due_soon_end,
    )

    assert result["all_count"] == 4
    assert result["open_count"] == 3
    assert result["overdue_count"] == 1
    assert result["due_today_count"] >= 1
    assert result["due_soon_count"] == 1
    assert result["completed_count"] == 1


def test_my_tasks_filter_options_include_assigned_locations(
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
    )

    create_task_assignee(
        db,
        task=task,
        user=user,
    )

    companies = TaskRepository.list_my_tasks_companies(
        db,
        user_id=user.id,
    )

    sections = TaskRepository.list_my_tasks_sections(
        db,
        user_id=user.id,
    )

    assert companies == [
        company,
    ]

    assert sections == [
        section,
    ]