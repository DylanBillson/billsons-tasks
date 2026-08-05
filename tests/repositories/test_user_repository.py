from sqlalchemy.orm import Session

from app.core.constants import GlobalRole
from app.core.security import (
    hash_password,
    verify_password,
)
from app.repositories.user_repository import (
    UserRepository,
)
from tests.factories import create_user


def test_get_by_id_returns_existing_user(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    result = UserRepository.get_by_id(
        db,
        user_id=user.id,
    )

    assert result is user


def test_get_by_id_returns_none_for_missing_user(
    db: Session,
) -> None:
    result = UserRepository.get_by_id(
        db,
        user_id=999_999,
    )

    assert result is None


def test_get_by_username_is_case_insensitive(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="repository-user",
    )

    result = UserRepository.get_by_username(
        db,
        username="  REPOSITORY-USER  ",
    )

    assert result is user


def test_get_by_username_returns_none_for_blank_username(
    db: Session,
) -> None:
    result = UserRepository.get_by_username(
        db,
        username="   ",
    )

    assert result is None


def test_username_exists_is_case_insensitive(
    db: Session,
) -> None:
    create_user(
        db,
        username="existing-user",
    )

    assert UserRepository.username_exists(
        db,
        username=" EXISTING-USER ",
    ) is True


def test_username_exists_returns_false_for_missing_username(
    db: Session,
) -> None:
    assert UserRepository.username_exists(
        db,
        username="missing-user",
    ) is False


def test_username_exists_can_exclude_existing_user(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="editable-user",
    )

    assert UserRepository.username_exists(
        db,
        username="EDITABLE-USER",
        exclude_user_id=user.id,
    ) is False


def test_username_exists_still_finds_other_user_when_excluding(
    db: Session,
) -> None:
    excluded_user = create_user(
        db,
        username="first-user",
    )

    create_user(
        db,
        username="second-user",
    )

    assert UserRepository.username_exists(
        db,
        username="SECOND-USER",
        exclude_user_id=excluded_user.id,
    ) is True


def test_create_normalises_and_persists_user(
    db: Session,
) -> None:
    password_hash = hash_password(
        "Repository-Password-123!",
    )

    user = UserRepository.create(
        db,
        username="  NEW-REPOSITORY-USER  ",
        display_name="  New Repository User  ",
        password_hash=password_hash,
        global_role=GlobalRole.USER.value,
        is_active=True,
    )

    assert user.id is not None
    assert user.username == "new-repository-user"
    assert user.display_name == "New Repository User"
    assert user.password_hash == password_hash
    assert user.global_role == GlobalRole.USER.value
    assert user.is_active is True
    assert user.is_anonymised is False

    stored_user = UserRepository.get_by_id(
        db,
        user_id=user.id,
    )

    assert stored_user is user


def test_create_can_create_inactive_administrator(
    db: Session,
) -> None:
    password_hash = hash_password(
        "Repository-Password-456!",
    )

    user = UserRepository.create(
        db,
        username="inactive-admin",
        display_name="Inactive Administrator",
        password_hash=password_hash,
        global_role=(
            GlobalRole.ADMINISTRATOR.value
        ),
        is_active=False,
    )

    assert user.global_role == (
        GlobalRole.ADMINISTRATOR.value
    )
    assert user.is_active is False
    assert user.is_anonymised is False


def test_update_profile_updates_identity_and_role(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="old-username",
        display_name="Old Name",
        global_role=GlobalRole.USER.value,
    )

    result = UserRepository.update_profile(
        db,
        user=user,
        username="  NEW-USERNAME  ",
        display_name="  New Name  ",
        global_role=(
            GlobalRole.ADMINISTRATOR.value
        ),
    )

    assert result is user
    assert user.username == "new-username"
    assert user.display_name == "New Name"
    assert user.global_role == (
        GlobalRole.ADMINISTRATOR.value
    )


def test_update_password_hash_updates_user(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    new_password = "Repository-New-Password-789!"
    new_hash = hash_password(
        new_password,
    )

    result = UserRepository.update_password_hash(
        db,
        user=user,
        password_hash=new_hash,
    )

    assert result is user
    assert user.password_hash == new_hash
    assert verify_password(
        new_password,
        user.password_hash,
    )


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


def test_authenticatable_lookup_returns_active_user(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="active-auth-user",
        is_active=True,
        is_anonymised=False,
    )

    result = (
        UserRepository.get_authenticatable_by_username(
            db,
            username="ACTIVE-AUTH-USER",
        )
    )

    assert result is user


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


def test_anonymised_user_is_not_authenticatable(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="anonymised-auth-user",
        is_active=True,
        is_anonymised=True,
    )

    result = (
        UserRepository.get_authenticatable_by_username(
            db,
            username=user.username,
        )
    )

    assert result is None


def test_list_all_returns_users_in_display_name_order(
    db: Session,
) -> None:
    charlie = create_user(
        db,
        username="charlie-repository",
        display_name="Charlie Repository",
    )

    alice = create_user(
        db,
        username="alice-repository",
        display_name="Alice Repository",
    )

    bob = create_user(
        db,
        username="bob-repository",
        display_name="Bob Repository",
    )

    users = UserRepository.list_all(
        db,
    )

    relevant_users = [
        user
        for user in users
        if user.id in {
            alice.id,
            bob.id,
            charlie.id,
        }
    ]

    assert relevant_users == [
        alice,
        bob,
        charlie,
    ]


def test_list_all_can_exclude_inactive_users(
    db: Session,
) -> None:
    active_user = create_user(
        db,
        display_name="Active User",
    )

    inactive_user = create_user(
        db,
        display_name="Inactive User",
        is_active=False,
    )

    result = UserRepository.list_all(
        db,
        include_inactive=False,
    )

    assert active_user in result
    assert inactive_user not in result

    assert all(
        user.is_active
        for user in result
    )


def test_list_all_can_exclude_anonymised_users(
    db: Session,
) -> None:
    normal_user = create_user(
        db,
        display_name="Normal Repository User",
    )

    anonymised_user = create_user(
        db,
        display_name="Anonymised Repository User",
        is_anonymised=True,
    )

    result = UserRepository.list_all(
        db,
        include_anonymised=False,
    )

    assert normal_user in result
    assert anonymised_user not in result

    assert all(
        not user.is_anonymised
        for user in result
    )