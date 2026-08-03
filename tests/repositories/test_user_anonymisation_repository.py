from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.core.timezone import utc_now
from app.repositories.user_repository import (
    UserRepository,
)
from tests.factories import (
    create_auth_session,
    create_company,
    create_company_membership,
    create_section,
    create_section_list,
    create_section_membership,
    create_task,
    create_task_assignee,
    create_user,
)


def test_anonymise_replaces_user_identity(
    db: Session,
) -> None:
    user = create_user(
        db,
        username="personal-username",
        display_name="Personal Name",
        is_active=False,
    )

    anonymised_at = utc_now()

    result = UserRepository.anonymise(
        db,
        user=user,
        username="anonymised-user-0042",
        display_name="Anonymised User 0042",
        password_hash=hash_password(
            "Random-Unusable-Password-123!",
        ),
        anonymised_at=anonymised_at,
    )

    assert result is user
    assert user.username == "anonymised-user-0042"
    assert user.display_name == "Anonymised User 0042"
    assert user.global_role == "user"
    assert user.is_active is False
    assert user.is_anonymised is True
    assert user.anonymised_at == anonymised_at


def test_anonymised_identity_uses_stable_user_id(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    assert (
        UserRepository.build_anonymised_username(
            user_id=user.id,
        )
        == f"anonymised-user-{user.id:04d}"
    )

    assert (
        UserRepository.build_anonymised_display_name(
            user_id=user.id,
        )
        == f"Anonymised User {user.id:04d}"
    )


def test_remove_memberships_and_assignments(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    creator = create_user(
        db,
    )

    company = create_company(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=user,
    )

    section = create_section(
        db,
        company=company,
        created_by=creator,
    )

    create_section_membership(
        db,
        section=section,
        user=user,
    )

    section_list = create_section_list(
        db,
        section=section,
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

    assert (
        UserRepository.remove_task_assignments(
            db,
            user_id=user.id,
        )
        == 1
    )

    assert (
        UserRepository.remove_section_memberships(
            db,
            user_id=user.id,
        )
        == 1
    )

    assert (
        UserRepository.remove_company_memberships(
            db,
            user_id=user.id,
        )
        == 1
    )

    assert (
        UserRepository.count_task_assignments(
            db,
            user_id=user.id,
        )
        == 0
    )

    assert (
        UserRepository.count_section_memberships(
            db,
            user_id=user.id,
        )
        == 0
    )

    assert (
        UserRepository.count_company_memberships(
            db,
            user_id=user.id,
        )
        == 0
    )


def test_revoke_all_sessions_revokes_active_sessions(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    first_session, _, _ = create_auth_session(
        db,
        user=user,
    )

    second_session, _, _ = create_auth_session(
        db,
        user=user,
    )

    revoked_at = utc_now()

    count = UserRepository.revoke_all_sessions(
        db,
        user_id=user.id,
        revoked_at=revoked_at,
    )

    db.refresh(
        first_session,
    )

    db.refresh(
        second_session,
    )

    assert count == 2
    assert first_session.is_revoked is True
    assert second_session.is_revoked is True