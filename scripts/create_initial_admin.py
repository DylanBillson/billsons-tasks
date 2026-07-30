import argparse
import getpass
import logging
import re
import sys
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )

from app.core.constants import AuditAction, GlobalRole
from app.core.security import (
    PasswordValidationError,
    hash_password,
    validate_password,
)
from app.db.session import SessionLocal
from app.models.user import User
from app.services.audit_service import AuditService


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


USERNAME_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9._-]{2,99}$",
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create the initial Billson's Tasks administrator.",
    )

    parser.add_argument(
        "--username",
        help="Administrator username.",
    )

    parser.add_argument(
        "--display-name",
        help="Administrator display name.",
    )

    return parser.parse_args()


def normalise_username(
    value: str,
) -> str:
    return value.strip().lower()


def validate_username(
    username: str,
) -> None:
    if not USERNAME_PATTERN.fullmatch(username):
        raise ValueError(
            "Username must be between 3 and 100 characters and may only "
            "contain lowercase letters, numbers, periods, underscores "
            "and hyphens."
        )


def validate_display_name(
    display_name: str,
) -> None:
    if not display_name:
        raise ValueError(
            "Display name cannot be empty.",
        )

    if len(display_name) > 150:
        raise ValueError(
            "Display name cannot exceed 150 characters.",
        )


def prompt_for_username(
    supplied_username: str | None,
) -> str:
    if supplied_username is not None:
        username = normalise_username(
            supplied_username,
        )
    else:
        username = normalise_username(
            input("Username: "),
        )

    validate_username(username)

    return username


def prompt_for_display_name(
    supplied_display_name: str | None,
) -> str:
    if supplied_display_name is not None:
        display_name = supplied_display_name.strip()
    else:
        display_name = input(
            "Display name: ",
        ).strip()

    validate_display_name(display_name)

    return display_name


def prompt_for_password() -> str:
    password = getpass.getpass(
        "Password: ",
    )

    confirmation = getpass.getpass(
        "Confirm password: ",
    )

    validate_password(
        password,
        confirmation=confirmation,
    )

    return password


def count_administrators(
    db: Session,
) -> int:
    query = select(
        func.count(User.id),
    ).where(
        User.global_role == GlobalRole.ADMINISTRATOR.value,
        User.is_active.is_(True),
        User.is_anonymised.is_(False),
    )

    return int(
        db.scalar(query) or 0,
    )


def username_exists(
    db: Session,
    *,
    username: str,
) -> bool:
    query = select(
        User.id,
    ).where(
        func.lower(User.username) == username.lower(),
    )

    return db.scalar(query) is not None


def create_initial_administrator(
    db: Session,
    *,
    username: str,
    display_name: str,
    password: str,
) -> User:
    if count_administrators(db) > 0:
        raise RuntimeError(
            "An active administrator already exists. "
            "Use the administration interface to create additional users."
        )

    if username_exists(
        db,
        username=username,
    ):
        raise ValueError(
            f"Username '{username}' is already in use.",
        )

    administrator = User(
        username=username,
        display_name=display_name,
        password_hash=hash_password(
            password,
        ),
        global_role=GlobalRole.ADMINISTRATOR.value,
        is_active=True,
        is_anonymised=False,
    )

    db.add(administrator)
    db.flush()

    AuditService.record_system_event(
        db,
        action=AuditAction.USER_CREATED,
        summary=(
            f"Initial administrator "
            f"{administrator.display_name} was created."
        ),
        entity_type="user",
        entity_id=administrator.id,
        metadata_json={
            "username": administrator.username,
            "global_role": administrator.global_role,
            "initial_administrator": True,
        },
    )

    db.commit()
    db.refresh(administrator)

    return administrator


def main() -> int:
    arguments = parse_arguments()

    try:
        username = prompt_for_username(
            arguments.username,
        )

        display_name = prompt_for_display_name(
            arguments.display_name,
        )

        password = prompt_for_password()

        with SessionLocal() as db:
            administrator = create_initial_administrator(
                db,
                username=username,
                display_name=display_name,
                password=password,
            )

    except PasswordValidationError as exc:
        logger.error(
            "%s",
            exc,
        )
        return 1

    except (
        ValueError,
        RuntimeError,
    ) as exc:
        logger.error(
            "%s",
            exc,
        )
        return 1

    except IntegrityError:
        logger.exception(
            "The administrator could not be created because the "
            "username or another unique value already exists.",
        )
        return 1

    except SQLAlchemyError:
        logger.exception(
            "The administrator could not be created because of a "
            "database error.",
        )
        return 1

    except KeyboardInterrupt:
        logger.info(
            "Administrator creation cancelled.",
        )
        return 130

    except Exception:
        logger.exception(
            "The administrator could not be created.",
        )
        return 1

    logger.info(
        "Created initial administrator '%s' with user ID %s.",
        administrator.username,
        administrator.id,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main(),
    )