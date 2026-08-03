from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.timezone import utc_now
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

    return (
        creator,
        task,
    )


def test_task_comment_defaults(
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

    assert comment.id is not None
    assert comment.task_id == task.id
    assert comment.user_id == author.id
    assert comment.body.startswith(
        "Test comment ",
    )
    assert comment.deleted_at is None
    assert comment.deleted_by_user_id is None
    assert comment.is_deleted is False
    assert comment.created_at is not None
    assert comment.updated_at is not None


def test_task_comment_relationships(
    db: Session,
) -> None:
    author, task = _create_task(
        db,
    )

    deleter = create_user(
        db,
    )

    comment = create_task_comment(
        db,
        task=task,
        user=author,
        deleted_by=deleter,
    )

    assert comment.task is task
    assert comment in task.comments

    assert comment.user is author
    assert comment in author.task_comments

    assert comment.deleted_by is deleter
    assert comment in deleter.deleted_task_comments


def test_task_comment_can_retain_content_without_author(
    db: Session,
) -> None:
    _, task = _create_task(
        db,
    )

    comment = create_task_comment(
        db,
        task=task,
        user=None,
        body="Comment from a removed user.",
    )

    assert comment.user is None
    assert comment.user_id is None
    assert comment.body == "Comment from a removed user."


def test_deleted_comment_state(
    db: Session,
) -> None:
    author, task = _create_task(
        db,
    )

    deleted_at = (
        utc_now()
        - timedelta(
            minutes=1,
        )
    )

    comment = create_task_comment(
        db,
        task=task,
        user=author,
        deleted_at=deleted_at,
        deleted_by=author,
    )

    assert comment.deleted_at == deleted_at
    assert comment.deleted_by_user_id == author.id
    assert comment.is_deleted is True


def test_blank_comment_is_rejected(
    db: Session,
) -> None:
    author, task = _create_task(
        db,
    )

    with pytest.raises(
        IntegrityError,
    ):
        create_task_comment(
            db,
            task=task,
            user=author,
            body="   ",
        )


def test_comment_deletion_fields_must_be_consistent(
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

    comment.deleted_by = author
    comment.deleted_at = None

    with pytest.raises(
        IntegrityError,
    ):
        db.flush()


def test_task_comments_are_ordered_oldest_first(
    db: Session,
) -> None:
    author, task = _create_task(
        db,
    )

    first = create_task_comment(
        db,
        task=task,
        user=author,
        body="First comment.",
    )

    second = create_task_comment(
        db,
        task=task,
        user=author,
        body="Second comment.",
    )

    db.expire(
        task,
        [
            "comments",
        ],
    )

    assert task.comments == [
        first,
        second,
    ]


def test_task_comment_repr(
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

    representation = repr(
        comment,
    )

    assert "TaskComment" in representation
    assert f"id={comment.id!r}" in representation
    assert f"task_id={task.id!r}" in representation
    assert f"user_id={author.id!r}" in representation
    assert "is_deleted=False" in representation