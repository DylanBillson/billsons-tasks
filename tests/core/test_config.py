from app.core.config import APP_VERSION, settings


def test_feedback_email_is_loaded() -> None:
    assert settings.feedback_email_to


def test_application_version_is_available() -> None:
    assert APP_VERSION
    assert isinstance(
        APP_VERSION,
        str,
    )

def test_live_update_settings_are_loaded() -> None:
    assert settings.live_updates_enabled is True

    assert (
        settings.live_updates_poll_interval_seconds
        == 5
    )


def test_live_update_poll_interval_is_reasonable() -> None:
    assert (
        2
        <= settings.live_updates_poll_interval_seconds
        <= 60
    )