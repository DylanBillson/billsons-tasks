import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import PermissionDeniedError
from app.core.constants import AuditAction, CompanyRole
from app.models.audit_log import AuditLog
from app.models.section_membership import SectionMembership
from app.schemas.section import SectionMembershipCreateRequest
from app.services.section_membership_service import (
    SectionCompanyMembershipRequiredError,
    SectionMembershipAlreadyExistsError,
    SectionMembershipService,
    SectionMembershipUserNotFoundError,
    SectionMembershipUserUnavailableError,
)
from tests.factories import (
    create_administrator,
    create_company,
    create_company_membership,
    create_section,
    create_section_membership,
    create_user,
)


def test_creator_assigns_company_member_to_section(db: Session) -> None:
    company = create_company(db)
    creator = create_user(db)
    target = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=creator,
        role=CompanyRole.MANAGER,
    )
    create_company_membership(db, company=company, user=target)
    section = create_section(db, company=company, created_by=creator)

    membership = SectionMembershipService.assign_user(
        db,
        actor=creator,
        section=section,
        membership_create=SectionMembershipCreateRequest(
            user_id=target.id,
        ),
    )

    assert membership.section_id == section.id
    assert membership.user_id == target.id


def test_administrator_assigns_company_member_to_section(
    db: Session,
) -> None:
    administrator = create_administrator(db)
    company = create_company(db)
    creator = create_user(db)
    target = create_user(db)
    create_company_membership(db, company=company, user=target)
    section = create_section(db, company=company, created_by=creator)

    membership = SectionMembershipService.assign_user(
        db,
        actor=administrator,
        section=section,
        membership_create=SectionMembershipCreateRequest(
            user_id=target.id,
        ),
    )

    assert membership.user_id == target.id


def test_assigned_manager_cannot_manage_section_memberships(
    db: Session,
) -> None:
    company = create_company(db)
    creator = create_user(db)
    manager = create_user(db)
    target = create_user(db)
    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )
    create_company_membership(db, company=company, user=target)
    section = create_section(db, company=company, created_by=creator)
    create_section_membership(db, section=section, user=manager)

    with pytest.raises(PermissionDeniedError):
        SectionMembershipService.assign_user(
            db,
            actor=manager,
            section=section,
            membership_create=SectionMembershipCreateRequest(
                user_id=target.id,
            ),
        )


def test_assign_user_rejects_unknown_user(db: Session) -> None:
    administrator = create_administrator(db)
    company = create_company(db)
    creator = create_user(db)
    section = create_section(db, company=company, created_by=creator)

    with pytest.raises(
        SectionMembershipUserNotFoundError,
        match="could not be found",
    ):
        SectionMembershipService.assign_user(
            db,
            actor=administrator,
            section=section,
            membership_create=SectionMembershipCreateRequest(
                user_id=999_999,
            ),
        )


def test_assign_user_rejects_inactive_user(db: Session) -> None:
    administrator = create_administrator(db)
    company = create_company(db)
    creator = create_user(db)
    target = create_user(db, is_active=False)
    create_company_membership(db, company=company, user=target)
    section = create_section(db, company=company, created_by=creator)

    with pytest.raises(
        SectionMembershipUserUnavailableError,
        match="not available",
    ):
        SectionMembershipService.assign_user(
            db,
            actor=administrator,
            section=section,
            membership_create=SectionMembershipCreateRequest(
                user_id=target.id,
            ),
        )


def test_assign_user_requires_parent_company_membership(
    db: Session,
) -> None:
    administrator = create_administrator(db)
    company = create_company(db)
    creator = create_user(db)
    target = create_user(db)
    section = create_section(db, company=company, created_by=creator)

    with pytest.raises(
        SectionCompanyMembershipRequiredError,
        match="must belong",
    ):
        SectionMembershipService.assign_user(
            db,
            actor=administrator,
            section=section,
            membership_create=SectionMembershipCreateRequest(
                user_id=target.id,
            ),
        )


def test_assign_user_rejects_duplicate_membership(db: Session) -> None:
    administrator = create_administrator(db)
    company = create_company(db)
    creator = create_user(db)
    target = create_user(db)
    create_company_membership(db, company=company, user=target)
    section = create_section(db, company=company, created_by=creator)
    create_section_membership(db, section=section, user=target)

    with pytest.raises(
        SectionMembershipAlreadyExistsError,
        match="already assigned",
    ):
        SectionMembershipService.assign_user(
            db,
            actor=administrator,
            section=section,
            membership_create=SectionMembershipCreateRequest(
                user_id=target.id,
            ),
        )


def test_creator_removes_section_member(db: Session) -> None:
    company = create_company(db)
    creator = create_user(db)
    target = create_user(db)
    section = create_section(db, company=company, created_by=creator)
    membership = create_section_membership(
        db,
        section=section,
        user=target,
    )
    membership_id = membership.id

    SectionMembershipService.remove_user(
        db,
        actor=creator,
        membership=membership,
    )

    assert db.scalar(
        select(SectionMembership).where(
            SectionMembership.id == membership_id,
        )
    ) is None


def test_assign_user_records_audit_log(db: Session) -> None:
    administrator = create_administrator(db)
    company = create_company(db)
    creator = create_user(db)
    target = create_user(db)
    create_company_membership(db, company=company, user=target)
    section = create_section(db, company=company, created_by=creator)

    membership = SectionMembershipService.assign_user(
        db,
        actor=administrator,
        section=section,
        membership_create=SectionMembershipCreateRequest(
            user_id=target.id,
        ),
    )

    audit_log = db.scalar(
        select(AuditLog).where(
            AuditLog.action == AuditAction.SECTION_MEMBER_ADDED.value,
            AuditLog.entity_id == membership.id,
        )
    )

    assert audit_log is not None
