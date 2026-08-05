from app.core.config import APP_VERSION, settings


def test_feedback_email_is_loaded() -> None:
    assert settings.feedback_email_to


def test_application_version_is_available() -> None:
    assert APP_VERSION
    assert isinstance(
        APP_VERSION,
        str,
    )