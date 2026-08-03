from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User

from datetime import datetime

from sqlalchemy import delete, func, select, update

from app.models.company_membership import CompanyMembership
from app.models.section_membership import SectionMembership
from app.models.session import AuthSession
from app.models.task_assignee import TaskAssignee

class UserRepository:
    @staticmethod
    def get_by_id(
        db: Session,
        *,
        user_id: int,
    ) -> User | None:
        query = select(User).where(
            User.id == user_id,
        )

        return db.scalar(
            query,
        )

    @staticmethod
    def get_by_username(
        db: Session,
        *,
        username: str,
    ) -> User | None:
        """
        Return a user using a case-insensitive username lookup.

        Usernames should normally be stored in normalised lowercase form, but
        the case-insensitive comparison protects authentication against legacy
        or manually inserted mixed-case values.
        """
        normalised_username = username.strip().lower()

        if not normalised_username:
            return None

        query = select(User).where(
            func.lower(User.username)
            == normalised_username,
        )

        return db.scalar(
            query,
        )
    
    @staticmethod
    def build_anonymised_username(
        *,
        user_id: int,
    ) -> str:
        return (
            f"anonymised-user-{user_id:04d}"
        )

    @staticmethod
    def build_anonymised_display_name(
        *,
        user_id: int,
    ) -> str:
        return (
            f"Anonymised User {user_id:04d}"
        )

    @staticmethod
    def anonymise(
        db: Session,
        *,
        user: User,
        username: str,
        display_name: str,
        password_hash: str,
        anonymised_at: datetime,
    ) -> User:
        user.username = username
        user.display_name = display_name
        user.password_hash = password_hash
        user.global_role = "user"
        user.is_active = False
        user.is_anonymised = True
        user.anonymised_at = anonymised_at

        db.add(
            user,
        )
        db.flush()

        return user

    @staticmethod
    def count_company_memberships(
        db: Session,
        *,
        user_id: int,
    ) -> int:
        return int(
            db.scalar(
                select(
                    func.count(
                        CompanyMembership.id,
                    ),
                ).where(
                    CompanyMembership.user_id
                    == user_id,
                ),
            )
            or 0
        )

    @staticmethod
    def count_section_memberships(
        db: Session,
        *,
        user_id: int,
    ) -> int:
        return int(
            db.scalar(
                select(
                    func.count(
                        SectionMembership.id,
                    ),
                ).where(
                    SectionMembership.user_id
                    == user_id,
                ),
            )
            or 0
        )

    @staticmethod
    def count_task_assignments(
        db: Session,
        *,
        user_id: int,
    ) -> int:
        return int(
            db.scalar(
                select(
                    func.count(
                        TaskAssignee.id,
                    ),
                ).where(
                    TaskAssignee.user_id
                    == user_id,
                ),
            )
            or 0
        )

    @staticmethod
    def count_active_sessions(
        db: Session,
        *,
        user_id: int,
        now: datetime,
    ) -> int:
        return int(
            db.scalar(
                select(
                    func.count(
                        AuthSession.id,
                    ),
                ).where(
                    AuthSession.user_id
                    == user_id,
                    AuthSession.is_revoked.is_(False),
                    AuthSession.expires_at > now,
                ),
            )
            or 0
        )

    @staticmethod
    def remove_company_memberships(
        db: Session,
        *,
        user_id: int,
    ) -> int:
        result = db.execute(
            delete(
                CompanyMembership,
            ).where(
                CompanyMembership.user_id
                == user_id,
            ),
        )

        return int(
            result.rowcount
            or 0,
        )

    @staticmethod
    def remove_section_memberships(
        db: Session,
        *,
        user_id: int,
    ) -> int:
        result = db.execute(
            delete(
                SectionMembership,
            ).where(
                SectionMembership.user_id
                == user_id,
            ),
        )

        return int(
            result.rowcount
            or 0,
        )

    @staticmethod
    def remove_task_assignments(
        db: Session,
        *,
        user_id: int,
    ) -> int:
        result = db.execute(
            delete(
                TaskAssignee,
            ).where(
                TaskAssignee.user_id
                == user_id,
            ),
        )

        return int(
            result.rowcount
            or 0,
        )

    @staticmethod
    def revoke_all_sessions(
        db: Session,
        *,
        user_id: int,
        revoked_at: datetime,
    ) -> int:
        result = db.execute(
            update(
                AuthSession,
            )
            .where(
                AuthSession.user_id == user_id,
                AuthSession.is_revoked.is_(False),
                AuthSession.expires_at
                > revoked_at,
            )
            .values(
                is_revoked=True,
                revoked_at=revoked_at,
            ),
        )

        return int(
            result.rowcount
            or 0,
        )
    
    @staticmethod
    def get_authenticatable_by_username(
        db: Session,
        *,
        username: str,
    ) -> User | None:
        """
        Return an active, non-anonymised user for authentication.

        Administration workflows may still retrieve inactive or anonymised
        users through get_by_username().
        """
        normalised_username = username.strip().lower()

        if not normalised_username:
            return None

        query = select(User).where(
            func.lower(User.username)
            == normalised_username,
            User.is_active.is_(True),
            User.is_anonymised.is_(False),
        )

        return db.scalar(
            query,
        )

    @staticmethod
    def username_exists(
        db: Session,
        *,
        username: str,
        exclude_user_id: int | None = None,
    ) -> bool:
        normalised_username = username.strip().lower()

        if not normalised_username:
            return False

        query = select(User.id).where(
            func.lower(User.username)
            == normalised_username,
        )

        if exclude_user_id is not None:
            query = query.where(
                User.id != exclude_user_id,
            )

        return db.scalar(
            query,
        ) is not None

    @staticmethod
    def list_all(
        db: Session,
        *,
        include_inactive: bool = True,
        include_anonymised: bool = True,
    ) -> list[User]:
        query = select(User)

        if not include_inactive:
            query = query.where(
                User.is_active.is_(True),
            )

        if not include_anonymised:
            query = query.where(
                User.is_anonymised.is_(False),
            )

        query = query.order_by(
            func.lower(
                User.display_name,
            ),
            func.lower(
                User.username,
            ),
            User.id,
        )

        return list(
            db.scalars(
                query,
            ).all(),
        )

    @staticmethod
    def create(
        db: Session,
        *,
        username: str,
        display_name: str,
        password_hash: str,
        global_role: str,
        is_active: bool = True,
    ) -> User:
        user = User(
            username=username.strip().lower(),
            display_name=display_name.strip(),
            password_hash=password_hash,
            global_role=global_role,
            is_active=is_active,
            is_anonymised=False,
        )

        db.add(
            user,
        )
        db.flush()

        return user

    @staticmethod
    def update_password_hash(
        db: Session,
        *,
        user: User,
        password_hash: str,
    ) -> User:
        user.password_hash = password_hash

        db.add(
            user,
        )
        db.flush()

        return user

    @staticmethod
    def set_active_status(
        db: Session,
        *,
        user: User,
        is_active: bool,
    ) -> User:
        user.is_active = is_active

        db.add(
            user,
        )
        db.flush()

        return user

    @staticmethod
    def update_profile(
        db: Session,
        *,
        user: User,
        username: str | None = None,
        display_name: str | None = None,
        global_role: str | None = None,
        is_active: bool | None = None,
    ) -> User:
        if username is not None:
            user.username = (
                username.strip().lower()
            )

        if display_name is not None:
            user.display_name = (
                display_name.strip()
            )

        if global_role is not None:
            user.global_role = global_role

        if is_active is not None:
            user.is_active = is_active

        db.add(
            user,
        )
        db.flush()

        return user