from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    #
    # Application
    #

    app_name: str = Field(
        alias="APP_NAME",
    )

    app_env: str = Field(
        alias="APP_ENV",
    )

    app_debug: bool = Field(
        alias="APP_DEBUG",
    )

    base_url: str = Field(
        alias="BASE_URL",
    )

    default_timezone: str = Field(
        alias="DEFAULT_TIMEZONE",
    )

    app_secret_key: str = Field(
        alias="APP_SECRET_KEY",
    )

    #
    # Database
    #

    postgres_db: str = Field(
        alias="POSTGRES_DB",
    )

    postgres_user: str = Field(
        alias="POSTGRES_USER",
    )

    postgres_password: str = Field(
        alias="POSTGRES_PASSWORD",
    )

    database_url: str = Field(
        alias="DATABASE_URL",
    )

    #
    # Sessions
    #

    session_cookie_name: str = Field(
        alias="SESSION_COOKIE_NAME",
    )

    session_duration_hours: int = Field(
        default=12,
        alias="SESSION_MAX_AGE_HOURS",
        ge=1,
        le=168,
    )

    remember_me_duration_days: int = Field(
        default=30,
        alias="SESSION_REMEMBER_ME_DAYS",
        ge=1,
        le=365,
    )

    session_last_seen_update_minutes: int = Field(
        default=5,
        alias="SESSION_LAST_SEEN_UPDATE_MINUTES",
        ge=1,
        le=60,
    )

    session_cookie_secure: bool = Field(
        default=False,
        alias="SESSION_COOKIE_SECURE",
    )

    session_cookie_httponly: bool = Field(
        default=True,
        alias="SESSION_COOKIE_HTTPONLY",
    )

    session_cookie_samesite: Literal[
        "lax",
        "strict",
        "none",
    ] = Field(
        default="lax",
        alias="SESSION_COOKIE_SAMESITE",
    )

    #
    # Security
    #

    password_min_length: int = Field(
        alias="PASSWORD_MIN_LENGTH",
        ge=8,
        le=128,
    )

    #
    # Notifications
    #

    notifications_enabled: bool = Field(
        alias="NOTIFICATIONS_ENABLED",
    )

    #
    # Logging
    #

    log_level: str = Field(
        alias="LOG_LEVEL",
    )

    #
    # Traefik
    #

    traefik_host: str = Field(
        alias="TRAEFIK_HOST",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()