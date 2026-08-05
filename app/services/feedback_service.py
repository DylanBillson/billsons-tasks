from __future__ import annotations

import secrets
import smtplib
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import AuditAction
from app.core.timezone import local_now, to_local
from app.models.user import User
from app.schemas.feedback import (
    FeedbackDeliveryResult,
    FeedbackSubmission,
)
from app.services.audit_service import AuditService


class FeedbackServiceError(RuntimeError):
    """Base exception for feedback-delivery failures."""


class FeedbackPermissionError(
    FeedbackServiceError,
):
    """Raised when an unavailable user submits feedback."""


class FeedbackConfigurationError(
    FeedbackServiceError,
):
    """Raised when email delivery is not configured."""


class FeedbackDeliveryError(
    FeedbackServiceError,
):
    """Raised when the SMTP server cannot deliver feedback."""


class FeedbackService:
    @staticmethod
    def send_feedback(
        db: Session,
        *,
        user: User,
        submission: FeedbackSubmission,
        sent_at: datetime | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> FeedbackDeliveryResult:
        FeedbackService._require_available_user(
            user,
        )

        FeedbackService._validate_configuration()

        resolved_sent_at = (
            to_local(
                sent_at,
            )
            if sent_at is not None
            else local_now()
        )

        if resolved_sent_at is None:
            raise FeedbackServiceError(
                "The feedback time could not be determined.",
            )

        issue_number = (
            FeedbackService.generate_issue_number()
        )

        email_message = FeedbackService.build_email(
            user=user,
            submission=submission,
            issue_number=issue_number,
            sent_at=resolved_sent_at,
        )

        # Delivery occurs before the audit entry is created. A failed SMTP
        # request must not produce a successful feedback-submission audit
        # event.
        FeedbackService.deliver_email(
            email_message,
        )

        result = FeedbackDeliveryResult(
            issue_number=issue_number,
            sent_at=resolved_sent_at,
            recipient=settings.feedback_email_to,
        )

        AuditService.record(
            db,
            user=user,
            action=AuditAction.FEEDBACK_SUBMITTED,
            summary=(
                f"{user.display_name} submitted feedback "
                f"reference {issue_number}."
            ),
            entity_type="feedback",
            entity_id=None,
            metadata_json={
                "issue_number": issue_number,
                "page_url": submission.page_url,
                "recipient": settings.feedback_email_to,
                "sent_at": resolved_sent_at.isoformat(),
            },
            ip_address=ip_address,
            user_agent=user_agent,
            commit=False,
        )

        if commit:
            db.commit()

        return result

    @staticmethod
    def generate_issue_number() -> str:
        """
        Return a six-digit feedback reference.

        The reference is intentionally not persisted as a dedicated record
        and is not guaranteed to be globally unique.
        """
        return str(
            100_000
            + secrets.randbelow(
                900_000,
            ),
        )

    @staticmethod
    def build_email(
        *,
        user: User,
        submission: FeedbackSubmission,
        issue_number: str,
        sent_at: datetime,
    ) -> EmailMessage:
        display_time = sent_at.strftime(
            "%H:%M %d/%m/%y",
        )

        subject = (
            f"{settings.app_name} Feedback - "
            f"{issue_number} - "
            f"{display_time} - "
            f"{user.display_name}"
        )

        body = "\n".join(
            (
                f"Issue number: {issue_number}",
                f"Date: {display_time}",
                f"User: {user.display_name}",
                f"Page: {submission.page_url}",
                "",
                "Message:",
                submission.message,
            ),
        )

        message = EmailMessage()

        message["Subject"] = (
            FeedbackService._clean_header_value(
                subject,
            )
        )

        message["From"] = formataddr(
            (
                FeedbackService._clean_header_value(
                    settings.smtp_from_name,
                ),
                settings.smtp_from_email,
            ),
        )

        message["To"] = settings.feedback_email_to

        message.set_content(
            body,
        )

        return message

    @staticmethod
    def deliver_email(
        message: EmailMessage,
    ) -> None:
        try:
            with smtplib.SMTP(
                host=settings.smtp_host,
                port=settings.smtp_port,
                timeout=20,
            ) as smtp:
                smtp.ehlo()

                if settings.smtp_use_tls:
                    smtp.starttls()
                    smtp.ehlo()

                if settings.smtp_username:
                    smtp.login(
                        settings.smtp_username,
                        settings.smtp_password,
                    )

                smtp.send_message(
                    message,
                )

        except (
            OSError,
            smtplib.SMTPException,
        ) as exc:
            raise FeedbackDeliveryError(
                "The feedback email could not be sent.",
            ) from exc

    @staticmethod
    def _require_available_user(
        user: User,
    ) -> None:
        if not user.can_authenticate:
            raise FeedbackPermissionError(
                "An active user account is required "
                "to submit feedback.",
            )

    @staticmethod
    def _validate_configuration() -> None:
        required_values = {
            "SMTP_HOST": settings.smtp_host,
            "SMTP_FROM_EMAIL": (
                settings.smtp_from_email
            ),
            "FEEDBACK_EMAIL_TO": (
                settings.feedback_email_to
            ),
        }

        missing_values = [
            name
            for name, value in required_values.items()
            if not value.strip()
        ]

        if missing_values:
            raise FeedbackConfigurationError(
                "Feedback email is not fully configured. "
                "Missing: "
                + ", ".join(
                    missing_values,
                ),
            )

        if (
            settings.smtp_username
            and not settings.smtp_password
        ):
            raise FeedbackConfigurationError(
                "SMTP_PASSWORD is required when "
                "SMTP_USERNAME is configured.",
            )

    @staticmethod
    def _clean_header_value(
        value: str,
    ) -> str:
        """
        Prevent user-controlled line breaks from creating extra headers.
        """
        return " ".join(
            value.replace(
                "\r",
                " ",
            ).replace(
                "\n",
                " ",
            ).split(),
        )