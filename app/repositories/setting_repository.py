from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.setting import ApplicationSetting


class SettingRepository:
    @staticmethod
    def get_by_id(
        db: Session,
        setting_id: int,
    ) -> ApplicationSetting | None:
        return db.get(
            ApplicationSetting,
            setting_id,
        )

    @staticmethod
    def get_by_key(
        db: Session,
        key: str,
    ) -> ApplicationSetting | None:
        query = select(ApplicationSetting).where(
            ApplicationSetting.key == key,
        )

        return db.scalar(query)

    @staticmethod
    def list_all(
        db: Session,
    ) -> list[ApplicationSetting]:
        query = select(ApplicationSetting).order_by(
            ApplicationSetting.key.asc(),
        )

        return list(
            db.scalars(query).all(),
        )

    @staticmethod
    def list_by_keys(
        db: Session,
        keys: Iterable[str],
    ) -> list[ApplicationSetting]:
        key_list = list(keys)

        if not key_list:
            return []

        query = (
            select(ApplicationSetting)
            .where(
                ApplicationSetting.key.in_(key_list),
            )
            .order_by(
                ApplicationSetting.key.asc(),
            )
        )

        return list(
            db.scalars(query).all(),
        )

    @staticmethod
    def create(
        db: Session,
        *,
        key: str,
        value: str,
        value_type: str = "string",
        is_public: bool = False,
        description: str | None = None,
    ) -> ApplicationSetting:
        setting = ApplicationSetting(
            key=key,
            value=value,
            value_type=value_type,
            is_public=is_public,
            description=description,
        )

        db.add(setting)
        db.flush()

        return setting

    @staticmethod
    def update_value(
        db: Session,
        setting: ApplicationSetting,
        *,
        value: str,
    ) -> ApplicationSetting:
        setting.value = value

        db.flush()

        return setting

    @staticmethod
    def update_definition(
        db: Session,
        setting: ApplicationSetting,
        *,
        value_type: str,
        is_public: bool,
        description: str | None,
    ) -> ApplicationSetting:
        setting.value_type = value_type
        setting.is_public = is_public
        setting.description = description

        db.flush()

        return setting

    @staticmethod
    def delete(
        db: Session,
        setting: ApplicationSetting,
    ) -> None:
        db.delete(setting)
        db.flush()