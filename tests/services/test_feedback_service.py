from datetime import UTC, datetime
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import AuditAction
from app.models.audit_log import AuditLog
from app.schemas.feedback import FeedbackSubmission
from app.services.feedback_service import (
    FeedbackConfigurationError,
    FeedbackDeliveryError,
    FeedbackPermissionError,
    FeedbackService,
)
from tests.factories import create_user


FIXED_SENT_AT = datetime(
    2026,
    8,
    4,
    12,
    30,
    tzinfo=UTC,
)


def _submission() -> FeedbackSubmission:
    return FeedbackSubmission(
        message=(
            "The task board does not fit correctly "
            "on my screen."
        ),
        page_url=(
            "https://tasks.billson.xyz/sections/42"
        ),
    )


def test_generate_issue_number_returns_six_digits() -> None:
    with patch(
        "app.services.feedback_service.secrets.randbelow",
        return_value=23,
    ):
        result = (
            FeedbackService.generate_issue_number()
        )

    assert result == "100023"
    assert len(result) == 6
    assert result.isdigit()


def test_build_email_uses_expected_subject_and_body(
    db: Session,
) -> None:
    user = create_user(
        db,
        display_name="Dylan Billson",
    )

    message = FeedbackService.build_email(
        user=user,
        submission=_submission(),
        issue_number="123456",
        sent_at=FIXED_SENT_AT,
    )

    assert isinstance(
        message,
        EmailMessage,
    )

    assert message["Subject"] == (
        f"{settings.app_name} Feedback - "
        "123456 - "
        "12:30 04/08/26 - "
        "Dylan Billson"
    )

    assert message["To"] == (
        settings.feedback_email_to
    )

    assert settings.smtp_from_email in str(
        message["From"],
    )

    body = message.get_content()

    assert "Issue number: 123456" in body
    assert "Date: 12:30 04/08/26" in body
    assert "User: Dylan Billson" in body

    assert (
        "Page: "
        "https://tasks.billson.xyz/sections/42"
        in body
    )

    assert "Message:" in body

    assert (
        "The task board does not fit correctly "
        "on my screen."
        in body
    )


def test_build_email_removes_header_line_breaks(
    db: Session,
) -> None:
    user = create_user(
        db,
        display_name=(
            "Dylan\nBcc: attacker@example.com"
        ),
    )

    message = FeedbackService.build_email(
        user=user,
        submission=_submission(),
        issue_number="123456",
        sent_at=FIXED_SENT_AT,
    )

    subject = str(
        message["Subject"],
    )

    assert "\n" not in subject
    assert "\r" not in subject

    assert subject == (
        f"{settings.app_name} Feedback - "
        "123456 - "
        "12:30 04/08/26 - "
        "Dylan Bcc: attacker@example.com"
    )


def test_send_feedback_delivers_email_and_creates_audit_log(
    db: Session,
) -> None:
    user = create_user(
        db,
        display_name="Dylan Billson",
    )

    with (
        patch.object(
            FeedbackService,
            "generate_issue_number",
            return_value="654321",
        ),
        patch.object(
            FeedbackService,
            "deliver_email",
        ) as deliver_mock,
    ):
        result = FeedbackService.send_feedback(
            db,
            user=user,
            submission=_submission(),
            sent_at=FIXED_SENT_AT,
            ip_address="203.0.113.45",
            user_agent="Feedback service test",
        )

    assert result.issue_number == "654321"

    assert result.recipient == (
        settings.feedback_email_to
    )

    assert result.sent_at.tzinfo is not None

    deliver_mock.assert_called_once()

    delivered_message = (
        deliver_mock.call_args.args[0]
    )

    assert isinstance(
        delivered_message,
        EmailMessage,
    )

    assert "654321" in str(
        delivered_message["Subject"],
    )

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action
            == AuditAction.FEEDBACK_SUBMITTED.value,
            AuditLog.entity_type == "feedback",
            AuditLog.user_id == user.id,
        )
    )

    assert audit_log is not None

    assert audit_log.summary == (
        "Dylan Billson submitted feedback "
        "reference 654321."
    )

    assert audit_log.entity_id is None
    assert audit_log.ip_address == "203.0.113.45"
    assert audit_log.user_agent == (
        "Feedback service test"
    )

    assert audit_log.metadata_json == {
        "issue_number": "654321",
        "page_url": (
            "https://tasks.billson.xyz/sections/42"
        ),
        "recipient": settings.feedback_email_to,
        "sent_at": result.sent_at.isoformat(),
    }


def test_feedback_audit_log_does_not_store_message(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    sensitive_message = (
        "This message contains information that "
        "must not be written to the audit log."
    )

    submission = FeedbackSubmission(
        message=sensitive_message,
        page_url=(
            "https://tasks.billson.xyz/tasks/99"
        ),
    )

    with (
        patch.object(
            FeedbackService,
            "generate_issue_number",
            return_value="111222",
        ),
        patch.object(
            FeedbackService,
            "deliver_email",
        ),
    ):
        FeedbackService.send_feedback(
            db,
            user=user,
            submission=submission,
            sent_at=FIXED_SENT_AT,
        )

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action
            == AuditAction.FEEDBACK_SUBMITTED.value,
            AuditLog.user_id == user.id,
        )
    )

    assert audit_log is not None

    audit_text = " ".join(
        (
            audit_log.summary,
            str(
                audit_log.metadata_json,
            ),
        ),
    )

    assert sensitive_message not in audit_text
    assert "message" not in audit_log.metadata_json


def test_failed_delivery_creates_no_audit_log(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    with (
        patch.object(
            FeedbackService,
            "generate_issue_number",
            return_value="333444",
        ),
        patch.object(
            FeedbackService,
            "deliver_email",
            side_effect=FeedbackDeliveryError(
                "The feedback email could not be sent.",
            ),
        ),
    ):
        with pytest.raises(
            FeedbackDeliveryError,
            match="could not be sent",
        ):
            FeedbackService.send_feedback(
                db,
                user=user,
                submission=_submission(),
                sent_at=FIXED_SENT_AT,
            )

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action
            == AuditAction.FEEDBACK_SUBMITTED.value,
            AuditLog.user_id == user.id,
        )
    )

    assert audit_log is None


def test_send_feedback_does_not_commit_when_commit_is_false(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    with (
        patch.object(
            FeedbackService,
            "generate_issue_number",
            return_value="555666",
        ),
        patch.object(
            FeedbackService,
            "deliver_email",
        ),
        patch.object(
            db,
            "commit",
            wraps=db.commit,
        ) as commit_mock,
    ):
        result = FeedbackService.send_feedback(
            db,
            user=user,
            submission=_submission(),
            sent_at=FIXED_SENT_AT,
            commit=False,
        )

    commit_mock.assert_not_called()

    assert result.issue_number == "555666"

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action
            == AuditAction.FEEDBACK_SUBMITTED.value,
            AuditLog.user_id == user.id,
        )
    )

    assert audit_log is not None
    assert audit_log.metadata_json[
        "issue_number"
    ] == "555666"


def test_send_feedback_rejects_inactive_user(
    db: Session,
) -> None:
    user = create_user(
        db,
        is_active=False,
    )

    with pytest.raises(
        FeedbackPermissionError,
        match="active user account",
    ):
        FeedbackService.send_feedback(
            db,
            user=user,
            submission=_submission(),
            sent_at=FIXED_SENT_AT,
        )


def test_send_feedback_rejects_anonymised_user(
    db: Session,
) -> None:
    user = create_user(
        db,
        is_active=False,
        is_anonymised=True,
    )

    with pytest.raises(
        FeedbackPermissionError,
        match="active user account",
    ):
        FeedbackService.send_feedback(
            db,
            user=user,
            submission=_submission(),
            sent_at=FIXED_SENT_AT,
        )


def test_configuration_rejects_missing_smtp_host(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "smtp_host",
        "",
    )

    with pytest.raises(
        FeedbackConfigurationError,
        match="SMTP_HOST",
    ):
        FeedbackService._validate_configuration()


def test_configuration_requires_password_for_username(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "smtp_username",
        "smtp-user",
    )

    monkeypatch.setattr(
        settings,
        "smtp_password",
        "",
    )

    with pytest.raises(
        FeedbackConfigurationError,
        match="SMTP_PASSWORD",
    ):
        FeedbackService._validate_configuration()


def test_deliver_email_uses_starttls_and_login(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "smtp_host",
        "smtp.example.com",
    )

    monkeypatch.setattr(
        settings,
        "smtp_port",
        587,
    )

    monkeypatch.setattr(
        settings,
        "smtp_use_tls",
        True,
    )

    monkeypatch.setattr(
        settings,
        "smtp_username",
        "smtp-user",
    )

    monkeypatch.setattr(
        settings,
        "smtp_password",
        "smtp-password",
    )

    smtp_client = MagicMock()
    smtp_context = MagicMock()

    smtp_context.__enter__.return_value = (
        smtp_client
    )

    message = EmailMessage()
    message["From"] = "sender@example.com"
    message["To"] = "recipient@example.com"
    message["Subject"] = "Feedback"
    message.set_content("Test feedback")

    with patch(
        "app.services.feedback_service.smtplib.SMTP",
        return_value=smtp_context,
    ) as smtp_class:
        FeedbackService.deliver_email(
            message,
        )

    smtp_class.assert_called_once_with(
        host="smtp.example.com",
        port=587,
        timeout=20,
    )

    assert smtp_client.ehlo.call_count == 2

    smtp_client.starttls.assert_called_once_with()

    smtp_client.login.assert_called_once_with(
        "smtp-user",
        "smtp-password",
    )

    smtp_client.send_message.assert_called_once_with(
        message,
    )


def test_deliver_email_skips_tls_and_login_when_disabled(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "smtp_host",
        "localhost",
    )

    monkeypatch.setattr(
        settings,
        "smtp_port",
        1025,
    )

    monkeypatch.setattr(
        settings,
        "smtp_use_tls",
        False,
    )

    monkeypatch.setattr(
        settings,
        "smtp_username",
        "",
    )

    monkeypatch.setattr(
        settings,
        "smtp_password",
        "",
    )

    smtp_client = MagicMock()
    smtp_context = MagicMock()

    smtp_context.__enter__.return_value = (
        smtp_client
    )

    message = EmailMessage()
    message["From"] = "sender@example.com"
    message["To"] = "recipient@example.com"
    message["Subject"] = "Feedback"
    message.set_content("Test feedback")

    with patch(
        "app.services.feedback_service.smtplib.SMTP",
        return_value=smtp_context,
    ):
        FeedbackService.deliver_email(
            message,
        )

    smtp_client.starttls.assert_not_called()
    smtp_client.login.assert_not_called()

    smtp_client.send_message.assert_called_once_with(
        message,
    )


def test_deliver_email_wraps_smtp_failure(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "smtp_host",
        "smtp.example.com",
    )

    message = EmailMessage()
    message["From"] = "sender@example.com"
    message["To"] = "recipient@example.com"
    message["Subject"] = "Feedback"
    message.set_content("Test feedback")

    with patch(
        "app.services.feedback_service.smtplib.SMTP",
        side_effect=OSError(
            "Connection failed",
        ),
    ):
        with pytest.raises(
            FeedbackDeliveryError,
            match="could not be sent",
        ):
            FeedbackService.deliver_email(
                message,
            )