from sqlalchemy.orm import Session

from app.repositories.user_repository import UserRepository
from tests.factories import create_user


def test_set_active_status_deactivates_user(
    db: Session,
) -> None:
    user = create_user(
        db,
        is_active=True,
    )

    result = UserRepository.set_active_status(
        db,
        user=user,
        is_active=False,
    )

    assert result is user
    assert user.is_active is False


def test_set_active_status_reactivates_user(
    db: Session,
) -> None:
    user = create_user(
        db,
        is_active=False,
    )

    result = UserRepository.set_active_status(
        db,
        user=user,
        is_active=True,
    )

    assert result is user
    assert user.is_active is True


def test_inactive_user_is_not_authenticatable(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="inactive-auth-user",
        is_active=False,
    )

    result = (
        UserRepository.get_authenticatable_by_username(
            db,
            username=user.username,
        )
    )

    assert result is None


def test_list_all_can_exclude_inactive_users(
    db: Session,
) -> None:
    active_user = create_user(
        db,
        display_name="Active User",
    )

    create_user(
        db,
        display_name="Inactive User",
        is_active=False,
    )

    result = UserRepository.list_all(
        db,
        include_inactive=False,
    )

    assert active_user in result

    assert all(
        user.is_active
        for user in result
    )