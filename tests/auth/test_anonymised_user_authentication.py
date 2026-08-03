from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories.user_repository import (
    UserRepository,
)
from app.services.anonymisation_service import (
    AnonymisationService,
)
from tests.factories import (
    create_administrator,
    create_auth_session,
    create_user,
)


def test_anonymised_user_is_not_authenticatable_by_username(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    user = create_user(
        db,
        username="former-login-name",
        is_active=False,
    )

    AnonymisationService.anonymise_user(
        db,
        actor=administrator,
        user_id=user.id,
        confirmation_phrase="ANONYMISE USER",
        commit=False,
    )

    assert (
        UserRepository.get_authenticatable_by_username(
            db,
            username="former-login-name",
        )
        is None
    )

    assert (
        UserRepository.get_authenticatable_by_username(
            db,
            username=user.username,
        )
        is None
    )


def test_existing_session_cannot_authenticate_after_anonymisation(
    client: TestClient,
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    user = create_user(
        db,
        is_active=False,
    )

    _, session_token, _ = create_auth_session(
        db,
        user=user,
    )

    AnonymisationService.anonymise_user(
        db,
        actor=administrator,
        user_id=user.id,
        confirmation_phrase="ANONYMISE USER",
        commit=True,
    )

    client.cookies.set(
        settings.session_cookie_name,
        session_token,
    )

    response = client.get(
        "/companies",
        headers={
            "accept": "application/json",
        },
        follow_redirects=False,
    )

    assert response.status_code == 401


def test_anonymised_account_cannot_be_reactivated(
    db: Session,
) -> None:
    from app.services.user_service import (
        AnonymisedUserStatusError,
        UserService,
    )

    import pytest

    administrator = create_administrator(
        db,
    )

    user = create_user(
        db,
        is_active=False,
    )

    AnonymisationService.anonymise_user(
        db,
        actor=administrator,
        user_id=user.id,
        confirmation_phrase="ANONYMISE USER",
        commit=False,
    )

    with pytest.raises(
        AnonymisedUserStatusError,
    ):
        UserService.set_active_status(
            db,
            acting_user=administrator,
            target_user=user,
            is_active=True,
            commit=False,
        )