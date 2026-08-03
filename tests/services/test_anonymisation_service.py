import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import AuditAction
from app.models.audit_log import AuditLog
from app.services.anonymisation_service import (
    AnonymisationConfirmationError,
    AnonymisationPermissionError,
    AnonymisationService,
    SelfAnonymisationError,
    UserAlreadyAnonymisedError,
    UserMustBeInactiveError,
)
from tests.factories import (
    create_administrator,
    create_audit_log,
    create_auth_session,
    create_company,
    create_company_membership,
    create_section,
    create_section_list,
    create_section_membership,
    create_task,
    create_task_assignee,
    create_task_comment,
    create_user,
)


def _create_context(
    db: Session,
):
    administrator = create_administrator(
        db,
    )

    user = create_user(
        db,
        username="dylan-personal",
        display_name="Dylan Personal",
        is_active=False,
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
        created_by=administrator,
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
        created_by=administrator,
    )

    create_task_assignee(
        db,
        task=task,
        user=user,
    )

    create_task_comment(
        db,
        task=task,
        user=user,
        body="Historical comment remains.",
    )

    return (
        administrator,
        user,
        company,
        section,
        task,
    )


def test_preview_returns_removal_counts(
    db: Session,
) -> None:
    (
        administrator,
        user,
        _,
        _,
        _,
    ) = _create_context(
        db,
    )

    preview = AnonymisationService.get_preview(
        db,
        actor=administrator,
        user_id=user.id,
    )

    assert preview.company_membership_count == 1
    assert preview.section_membership_count == 1
    assert preview.task_assignment_count == 1
    assert preview.comment_count == 1


def test_anonymise_user_replaces_identity(
    db: Session,
) -> None:
    (
        administrator,
        user,
        _,
        _,
        _,
    ) = _create_context(
        db,
    )

    result = AnonymisationService.anonymise_user(
        db,
        actor=administrator,
        user_id=user.id,
        confirmation_phrase="ANONYMISE USER",
        commit=False,
    )

    assert user.username == (
        f"anonymised-user-{user.id:04d}"
    )

    assert user.display_name == (
        f"Anonymised User {user.id:04d}"
    )

    assert user.is_active is False
    assert user.is_anonymised is True
    assert user.anonymised_at is not None

    assert result.user_id == user.id
    assert result.removed_company_membership_count == 1
    assert result.removed_section_membership_count == 1
    assert result.removed_task_assignment_count == 1


def test_anonymisation_preserves_historical_comment(
    db: Session,
) -> None:
    (
        administrator,
        user,
        _,
        _,
        task,
    ) = _create_context(
        db,
    )

    comment = task.comments[0]
    comment_id = comment.id

    AnonymisationService.anonymise_user(
        db,
        actor=administrator,
        user_id=user.id,
        confirmation_phrase="ANONYMISE USER",
        commit=False,
    )

    db.refresh(
        comment,
    )

    assert comment.id == comment_id
    assert comment.user_id == user.id
    assert comment.body == (
        "Historical comment remains."
    )

    assert comment.user.display_name == (
        f"Anonymised User {user.id:04d}"
    )


def test_anonymisation_revokes_sessions(
    db: Session,
) -> None:
    (
        administrator,
        user,
        _,
        _,
        _,
    ) = _create_context(
        db,
    )

    auth_session, _, _ = create_auth_session(
        db,
        user=user,
    )

    result = AnonymisationService.anonymise_user(
        db,
        actor=administrator,
        user_id=user.id,
        confirmation_phrase="ANONYMISE USER",
        commit=False,
    )

    db.refresh(
        auth_session,
    )

    assert result.revoked_session_count == 1
    assert auth_session.is_revoked is True


def test_anonymisation_scrubs_existing_audit_identity(
    db: Session,
) -> None:
    (
        administrator,
        user,
        _,
        _,
        _,
    ) = _create_context(
        db,
    )

    audit_log = create_audit_log(
        db,
        action=AuditAction.USER_UPDATED,
        user=administrator,
        entity_type="user",
        entity_id=user.id,
        summary=(
            "Dylan Personal updated dylan-personal."
        ),
        metadata_json={
            "username": "dylan-personal",
            "display_name": "Dylan Personal",
        },
    )

    AnonymisationService.anonymise_user(
        db,
        actor=administrator,
        user_id=user.id,
        confirmation_phrase="ANONYMISE USER",
        commit=False,
    )

    db.refresh(
        audit_log,
    )

    assert "Dylan Personal" not in audit_log.summary
    assert "dylan-personal" not in audit_log.summary

    assert (
        audit_log.metadata_json["username"]
        == f"anonymised-user-{user.id:04d}"
    )

    assert (
        audit_log.metadata_json["display_name"]
        == f"Anonymised User {user.id:04d}"
    )


def test_anonymisation_records_safe_audit_event(
    db: Session,
) -> None:
    (
        administrator,
        user,
        _,
        _,
        _,
    ) = _create_context(
        db,
    )

    original_username = user.username
    original_display_name = user.display_name

    AnonymisationService.anonymise_user(
        db,
        actor=administrator,
        user_id=user.id,
        confirmation_phrase="ANONYMISE USER",
        ip_address="192.0.2.120",
        user_agent="pytest anonymisation",
        commit=False,
    )

    audit_log = db.scalar(
        select(
            AuditLog,
        ).where(
            AuditLog.action
            == AuditAction.USER_ANONYMISED.value,
            AuditLog.entity_type
            == "user",
            AuditLog.entity_id
            == user.id,
        ),
    )

    assert audit_log is not None
    assert original_username not in audit_log.summary
    assert original_display_name not in audit_log.summary

    assert original_username not in str(
        audit_log.metadata_json,
    )

    assert original_display_name not in str(
        audit_log.metadata_json,
    )


def test_active_user_cannot_be_anonymised(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    user = create_user(
        db,
        is_active=True,
    )

    with pytest.raises(
        UserMustBeInactiveError,
        match="deactivated",
    ):
        AnonymisationService.anonymise_user(
            db,
            actor=administrator,
            user_id=user.id,
            confirmation_phrase="ANONYMISE USER",
            commit=False,
        )


def test_confirmation_phrase_must_match_exactly(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    user = create_user(
        db,
        is_active=False,
    )

    with pytest.raises(
        AnonymisationConfirmationError,
    ):
        AnonymisationService.anonymise_user(
            db,
            actor=administrator,
            user_id=user.id,
            confirmation_phrase="anonymise user",
            commit=False,
        )


def test_standard_user_cannot_anonymise_user(
    db: Session,
) -> None:
    actor = create_user(
        db,
    )

    target = create_user(
        db,
        is_active=False,
    )

    with pytest.raises(
        AnonymisationPermissionError,
    ):
        AnonymisationService.anonymise_user(
            db,
            actor=actor,
            user_id=target.id,
            confirmation_phrase="ANONYMISE USER",
            commit=False,
        )


def test_administrator_cannot_anonymise_self(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    with pytest.raises(
        SelfAnonymisationError,
        match="own account",
    ):
        AnonymisationService.anonymise_user(
            db,
            actor=administrator,
            user_id=administrator.id,
            confirmation_phrase="ANONYMISE USER",
            commit=False,
        )


def test_user_cannot_be_anonymised_twice(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    user = create_user(
        db,
        is_active=False,
        is_anonymised=True,
    )

    with pytest.raises(
        UserAlreadyAnonymisedError,
    ):
        AnonymisationService.anonymise_user(
            db,
            actor=administrator,
            user_id=user.id,
            confirmation_phrase="ANONYMISE USER",
            commit=False,
        )