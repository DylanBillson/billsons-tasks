from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.timezone import utc_now
from app.repositories.comment_repository import (
    CommentRepository,
)
from tests.factories import (
    create_company,
    create_section,
    create_section_list,
    create_task,
    create_task_comment,
    create_user,
)


def _create_task(
    db: Session,
):
    creator = create_user(
        db,
    )

    task = create_task(
        db,
        section_list=create_section_list(
            db,
            section=create_section(
                db,
                company=create_company(
                    db,
                ),
                created_by=creator,
            ),
        ),
        created_by=creator,
    )

    return creator, task


def test_get_by_id(
    db: Session,
) -> None:
    author, task = _create_task(
        db,
    )

    comment = create_task_comment(
        db,
        task=task,
        user=author,
    )

    result = CommentRepository.get_by_id(
        db,
        comment_id=comment.id,
    )

    assert result is comment
    assert result.task is task
    assert result.user is author


def test_get_by_id_returns_none(
    db: Session,
) -> None:
    assert CommentRepository.get_by_id(
        db,
        comment_id=999999,
    ) is None


def test_list_for_task_orders_newest_first(
    db: Session,
) -> None:
    author, task = _create_task(
        db,
    )

    first = create_task_comment(
        db,
        task=task,
        user=author,
        body="First.",
    )

    second = create_task_comment(
        db,
        task=task,
        user=author,
        body="Second.",
    )

    result = CommentRepository.list_for_task(
        db,
        task_id=task.id,
    )

    assert result == [
        second,
        first,
    ]


def test_list_for_task_excludes_deleted_by_default(
    db: Session,
) -> None:
    author, task = _create_task(
        db,
    )

    active = create_task_comment(
        db,
        task=task,
        user=author,
    )

    create_task_comment(
        db,
        task=task,
        user=author,
        deleted_by=author,
    )

    result = CommentRepository.list_for_task(
        db,
        task_id=task.id,
    )

    assert result == [
        active,
    ]


def test_list_for_task_can_include_deleted(
    db: Session,
) -> None:
    author, task = _create_task(
        db,
    )

    active = create_task_comment(
        db,
        task=task,
        user=author,
    )

    deleted = create_task_comment(
        db,
        task=task,
        user=author,
        deleted_by=author,
    )

    result = CommentRepository.list_for_task(
        db,
        task_id=task.id,
        include_deleted=True,
    )

    assert result == [
        deleted,
        active,
    ]


def test_create_comment(
    db: Session,
) -> None:
    author, task = _create_task(
        db,
    )

    comment = CommentRepository.create(
        db,
        task_id=task.id,
        user_id=author.id,
        body="A repository comment.",
    )

    assert comment.task_id == task.id
    assert comment.user_id == author.id
    assert comment.body == "A repository comment."


def test_soft_delete_comment(
    db: Session,
) -> None:
    author, task = _create_task(
        db,
    )

    comment = create_task_comment(
        db,
        task=task,
        user=author,
    )

    deleted_at = utc_now() - timedelta(
        minutes=1,
    )

    CommentRepository.soft_delete(
        db,
        comment=comment,
        deleted_by_user_id=author.id,
        deleted_at=deleted_at,
    )

    assert comment.deleted_at == deleted_at
    assert comment.deleted_by_user_id == author.id
    assert comment.is_deleted is True


def test_restore_comment(
    db: Session,
) -> None:
    author, task = _create_task(
        db,
    )

    comment = create_task_comment(
        db,
        task=task,
        user=author,
        deleted_by=author,
    )

    CommentRepository.restore(
        db,
        comment=comment,
    )

    assert comment.deleted_at is None
    assert comment.deleted_by_user_id is None
    assert comment.is_deleted is False


def test_permanently_delete_comment(
    db: Session,
) -> None:
    author, task = _create_task(
        db,
    )

    comment = create_task_comment(
        db,
        task=task,
        user=author,
    )

    comment_id = comment.id

    CommentRepository.permanently_delete(
        db,
        comment=comment,
    )

    assert CommentRepository.get_by_id(
        db,
        comment_id=comment_id,
    ) is None