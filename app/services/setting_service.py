from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.constants import APPLICATION_SETTINGS, SettingKey
from app.models.setting import ApplicationSetting
from app.repositories.setting_repository import SettingRepository
from app.schemas.setting import (
    SettingCreate,
    SettingDefinitionUpdate,
    SettingValueType,
    SettingValueUpdate,
    SettingValueValidator,
)


class SettingService:
    @staticmethod
    def get_setting(
        db: Session,
        *,
        key: str | SettingKey,
    ) -> ApplicationSetting | None:
        return SettingRepository.get_by_key(
            db,
            str(key),
        )

    @staticmethod
    def require_setting(
        db: Session,
        *,
        key: str | SettingKey,
    ) -> ApplicationSetting:
        setting = SettingService.get_setting(
            db,
            key=key,
        )

        if setting is None:
            raise LookupError(
                f"Application setting '{key}' was not found.",
            )

        return setting

    @staticmethod
    def list_settings(
        db: Session,
    ) -> list[ApplicationSetting]:
        return SettingRepository.list_all(db)

    @staticmethod
    def create_setting(
        db: Session,
        *,
        data: SettingCreate,
    ) -> ApplicationSetting:
        existing = SettingRepository.get_by_key(
            db,
            data.key,
        )

        if existing is not None:
            raise ValueError(
                f"Application setting '{data.key}' already exists.",
            )

        validated_value = SettingValueValidator.validate(
            value=data.value,
            value_type=data.value_type,
        )

        try:
            setting = SettingRepository.create(
                db,
                key=data.key,
                value=validated_value,
                value_type=data.value_type,
                is_public=data.is_public,
                description=data.description,
            )

            db.commit()

        except IntegrityError as exc:
            db.rollback()

            raise ValueError(
                f"Application setting '{data.key}' already exists.",
            ) from exc

        db.refresh(setting)

        return setting

    @staticmethod
    def update_value(
        db: Session,
        *,
        setting: ApplicationSetting,
        data: SettingValueUpdate,
    ) -> ApplicationSetting:
        validated_value = SettingValueValidator.validate(
            value=data.value,
            value_type=setting.value_type,
        )

        SettingRepository.update_value(
            db,
            setting,
            value=validated_value,
        )

        db.commit()
        db.refresh(setting)

        return setting

    @staticmethod
    def update_definition(
        db: Session,
        *,
        setting: ApplicationSetting,
        data: SettingDefinitionUpdate,
    ) -> ApplicationSetting:
        validated_value = SettingValueValidator.validate(
            value=setting.value,
            value_type=data.value_type,
        )

        setting.value = validated_value

        SettingRepository.update_definition(
            db,
            setting,
            value_type=data.value_type,
            is_public=data.is_public,
            description=data.description,
        )

        db.commit()
        db.refresh(setting)

        return setting

    @staticmethod
    def get_value(
        db: Session,
        *,
        key: str | SettingKey,
        default: Any = None,
    ) -> Any:
        setting = SettingService.get_setting(
            db,
            key=key,
        )

        if setting is None:
            return default

        return SettingService.convert_value(
            value=setting.value,
            value_type=setting.value_type,
        )

    @staticmethod
    def get_string(
        db: Session,
        *,
        key: str | SettingKey,
        default: str | None = None,
    ) -> str | None:
        value = SettingService.get_value(
            db,
            key=key,
            default=default,
        )

        if value is None:
            return None

        return str(value)

    @staticmethod
    def get_integer(
        db: Session,
        *,
        key: str | SettingKey,
        default: int | None = None,
    ) -> int | None:
        value = SettingService.get_value(
            db,
            key=key,
            default=default,
        )

        if value is None:
            return None

        if isinstance(value, bool):
            raise TypeError(
                f"Application setting '{key}' is not an integer.",
            )

        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"Application setting '{key}' is not an integer.",
            ) from exc

    @staticmethod
    def get_boolean(
        db: Session,
        *,
        key: str | SettingKey,
        default: bool | None = None,
    ) -> bool | None:
        value = SettingService.get_value(
            db,
            key=key,
            default=default,
        )

        if value is None:
            return None

        if not isinstance(value, bool):
            raise TypeError(
                f"Application setting '{key}' is not a boolean.",
            )

        return value

    @staticmethod
    def convert_value(
        *,
        value: str,
        value_type: str,
    ) -> str | int | bool:
        if value_type in {
            "string",
            "timezone",
        }:
            return value

        if value_type == "integer":
            return int(value)

        if value_type == "boolean":
            return value.strip().lower() in {
                "true",
                "1",
                "yes",
                "on",
            }

        raise ValueError(
            f"Unsupported setting value type: {value_type}",
        )

    @staticmethod
    def seed_registry(
        db: Session,
    ) -> list[ApplicationSetting]:
        created_settings: list[ApplicationSetting] = []

        registry_definitions: dict[
            SettingKey,
            tuple[str, SettingValueType, bool, str],
        ] = {
            SettingKey.APPLICATION_NAME: (
                APPLICATION_SETTINGS[SettingKey.APPLICATION_NAME],
                "string",
                True,
                "The application name displayed throughout the interface.",
            ),
            SettingKey.DEFAULT_TIMEZONE: (
                APPLICATION_SETTINGS[SettingKey.DEFAULT_TIMEZONE],
                "timezone",
                True,
                (
                    "The IANA timezone used when displaying dates and "
                    "interpreting local deadlines."
                ),
            ),
        }

        try:
            for key, definition in registry_definitions.items():
                default_value, value_type, is_public, description = definition

                existing = SettingRepository.get_by_key(
                    db,
                    key.value,
                )

                if existing is not None:
                    continue

                validated_value = SettingValueValidator.validate(
                    value=default_value,
                    value_type=value_type,
                )

                created_settings.append(
                    SettingRepository.create(
                        db,
                        key=key.value,
                        value=validated_value,
                        value_type=value_type,
                        is_public=is_public,
                        description=description,
                    )
                )

            db.commit()

        except Exception:
            db.rollback()
            raise

        for setting in created_settings:
            db.refresh(setting)

        return created_settings