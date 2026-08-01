"""
Reusable database factories for tests.

Factories flush and refresh records but never commit. Transaction ownership
remains with the calling test and the shared ``db`` fixture.
"""

from collections.abc import Mapping
from datetime import datetime, timedelta
from itertools import count
from typing import Any

from sqlalchemy.orm import Session

from app.core.constants import AuditAction, CompanyRole, GlobalRole
from app.core.security import (
    generate_csrf_token,
    generate_session_token,
    hash_password,
    hash_token,
)
from app.core.timezone import utc_now
from app.models.audit_log import AuditLog
from app.models.company import Company
from app.models.company_membership import CompanyMembership
from app.models.section import Section
from app.models.section_membership import SectionMembership
from app.models.session import AuthSession
from app.models.user import User
from app.services.audit_service import AuditService


DEFAULT_TEST_PASSWORD = "Correct-Horse-Battery-Staple-123!"

_user_counter = count(start=1)

_company_counter = count(
    start=1,
)

_section_counter = count(
    start=1,
)


def _next_company_number() -> int:
    """
    Return a process-local unique number for generated company names.
    """
    return next(
        _company_counter,
    )


def _next_section_number() -> int:
    """
    Return a process-local unique number for generated section names.
    """
    return next(
        _section_counter,
    )

def create_user(
    db: Session,
    *,
    username: str | None = None,
    display_name: str | None = None,
    password: str = DEFAULT_TEST_PASSWORD,
    password_hash: str | None = None,
    global_role: str | GlobalRole = GlobalRole.USER,
    is_active: bool = True,
    is_anonymised: bool = False,
    anonymised_at: datetime | None = None,
) -> User:
    number = next(_user_counter)
    resolved_role = (
        global_role.value
        if isinstance(global_role, GlobalRole)
        else global_role
    )

    if is_anonymised and anonymised_at is None:
        anonymised_at = utc_now()

    user = User(
        username=username or f"test-user-{number}",
        display_name=display_name or f"Test User {number}",
        password_hash=password_hash or hash_password(password),
        global_role=resolved_role,
        is_active=is_active,
        is_anonymised=is_anonymised,
        anonymised_at=anonymised_at,
    )

    db.add(user)
    db.flush()
    db.refresh(user)
    return user


def create_administrator(
    db: Session,
    *,
    username: str | None = None,
    display_name: str | None = None,
    password: str = DEFAULT_TEST_PASSWORD,
    password_hash: str | None = None,
    is_active: bool = True,
    is_anonymised: bool = False,
    anonymised_at: datetime | None = None,
) -> User:
    return create_user(
        db,
        username=username,
        display_name=display_name,
        password=password,
        password_hash=password_hash,
        global_role=GlobalRole.ADMINISTRATOR,
        is_active=is_active,
        is_anonymised=is_anonymised,
        anonymised_at=anonymised_at,
    )


def create_company(
    db: Session,
    *,
    name: str | None = None,
    description: str | None = None,
    is_archived: bool = False,
) -> Company:
    """
    Create and flush a company.
    """
    company_number = _next_company_number()

    resolved_name = (
        name
        if name is not None
        else f"Test Company {company_number}"
    )

    company = Company(
        name=resolved_name,
        description=description,
        is_archived=is_archived,
    )

    db.add(
        company,
    )
    db.flush()

    return company


def create_company_membership(
    db: Session,
    *,
    company: Company,
    user: User,
    role: str | CompanyRole = CompanyRole.EMPLOYEE,
) -> CompanyMembership:
    """
    Create and flush a company membership.

    Assigning relationship objects rather than only foreign-key IDs keeps both
    sides of the SQLAlchemy relationships synchronised in memory.
    """
    resolved_role = (
        role.value
        if isinstance(
            role,
            CompanyRole,
        )
        else role
    )

    membership = CompanyMembership(
        company=company,
        user=user,
        role=resolved_role,
    )

    db.add(
        membership,
    )
    db.flush()

    return membership


def create_section(
    db: Session,
    *,
    company: Company,
    created_by: User,
    name: str | None = None,
    description: str | None = None,
    is_archived: bool = False,
) -> Section:
    """
    Create and flush a section.

    The creator relationship is separate from section membership. Creating a
    section does not create a SectionMembership row.
    """
    section_number = _next_section_number()

    resolved_name = (
        name
        if name is not None
        else f"Test Section {section_number}"
    )

    section = Section(
        company=company,
        created_by=created_by,
        name=resolved_name,
        description=description,
        is_archived=is_archived,
    )

    db.add(
        section,
    )
    db.flush()

    return section


def create_section_membership(
    db: Session,
    *,
    section: Section,
    user: User,
) -> SectionMembership:
    """
    Create and flush an explicit section membership.

    This factory does not create or require a company membership. That
    integrity rule will be enforced by the service layer; model-level tests
    may deliberately construct lower-level database states.
    """
    membership = SectionMembership(
        section=section,
        user=user,
    )

    db.add(
        membership,
    )
    db.flush()

    return membership


def create_auth_session(
    db: Session,
    *,
    user: User,
    session_token: str | None = None,
    csrf_token: str | None = None,
    expires_at: datetime | None = None,
    last_seen_at: datetime | None = None,
    remember_me: bool = False,
    is_revoked: bool = False,
    revoked_at: datetime | None = None,
    ip_address: str | None = "127.0.0.1",
    user_agent: str | None = "Billsons Tasks pytest",
) -> tuple[AuthSession, str, str]:
    now = utc_now()
    raw_session_token = session_token or generate_session_token()
    raw_csrf_token = csrf_token or generate_csrf_token()
    resolved_last_seen = last_seen_at or now
    resolved_expiry = expires_at or now + timedelta(hours=12)
    resolved_revoked_at = revoked_at

    if is_revoked and resolved_revoked_at is None:
        resolved_revoked_at = now

    auth_session = AuthSession(
        user_id=user.id,
        token_hash=hash_token(raw_session_token),
        csrf_token_hash=hash_token(raw_csrf_token),
        expires_at=resolved_expiry,
        last_seen_at=resolved_last_seen,
        remember_me=remember_me,
        is_revoked=is_revoked,
        revoked_at=resolved_revoked_at,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    db.add(auth_session)
    db.flush()
    db.refresh(auth_session)
    return auth_session, raw_session_token, raw_csrf_token


def create_expired_auth_session(
    db: Session,
    *,
    user: User,
    expired_at: datetime | None = None,
    session_token: str | None = None,
    csrf_token: str | None = None,
    remember_me: bool = False,
    ip_address: str | None = "127.0.0.1",
    user_agent: str | None = "Billsons Tasks pytest",
) -> tuple[AuthSession, str, str]:
    resolved_expiry = expired_at or utc_now() - timedelta(minutes=1)

    return create_auth_session(
        db,
        user=user,
        session_token=session_token,
        csrf_token=csrf_token,
        expires_at=resolved_expiry,
        last_seen_at=resolved_expiry - timedelta(minutes=5),
        remember_me=remember_me,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def create_revoked_auth_session(
    db: Session,
    *,
    user: User,
    revoked_at: datetime | None = None,
    session_token: str | None = None,
    csrf_token: str | None = None,
    expires_at: datetime | None = None,
    remember_me: bool = False,
    ip_address: str | None = "127.0.0.1",
    user_agent: str | None = "Billsons Tasks pytest",
) -> tuple[AuthSession, str, str]:
    return create_auth_session(
        db,
        user=user,
        session_token=session_token,
        csrf_token=csrf_token,
        expires_at=expires_at,
        remember_me=remember_me,
        is_revoked=True,
        revoked_at=revoked_at,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def create_audit_log(
    db: Session,
    *,
    action: str | AuditAction = AuditAction.LOGIN,
    summary: str = "Test audit event.",
    user: User | None = None,
    user_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    metadata_json: Mapping[str, Any] | None = None,
    ip_address: str | None = "127.0.0.1",
    user_agent: str | None = "Billsons Tasks pytest",
) -> AuditLog:
    audit_log = AuditService.record(
        db,
        action=action,
        summary=summary,
        user=user,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=dict(metadata_json) if metadata_json is not None else None,
        ip_address=ip_address,
        user_agent=user_agent,
        commit=False,
    )

    db.flush()
    db.refresh(audit_log)
    return audit_log
