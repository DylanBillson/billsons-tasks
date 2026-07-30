import logging
import sys
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )

from app.db.session import SessionLocal
from app.services.setting_service import SettingService


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


def main() -> int:
    try:
        with SessionLocal() as db:
            created_settings = SettingService.seed_registry(db)

    except SQLAlchemyError:
        logger.exception(
            "The settings registry could not be seeded because of a database error.",
        )
        return 1

    except Exception:
        logger.exception(
            "The settings registry could not be seeded.",
        )
        return 1

    if not created_settings:
        logger.info(
            "Settings registry is already up to date. No settings were created.",
        )
        return 0

    logger.info(
        "Created %s application setting%s:",
        len(created_settings),
        "" if len(created_settings) == 1 else "s",
    )

    for setting in created_settings:
        logger.info(
            "  - %s",
            setting.key,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())