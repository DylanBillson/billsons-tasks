import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import PermissionDeniedError
from app.core.constants import AuditAction
from app.models.audit_log import AuditLog
from app.services.section_service import (
    SectionArchiveFilterError,
    SectionParentCompanyArchivedError,
    SectionService,
)
from tests.factories import (
    create_administrator,
    create_company,
    create_section,
    create_user,
)


def test_administrator_lists_archived_sections(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    company = create_company(
        db,
    )

    archived = create_section(
        db,
        company=company,
        created_by=creator,
        is_archived=True,
    )

    create_section(
        db,
        company=company,
        created_by=creator,
    )

    sections, total_items = (
        SectionService.list_archived_sections(
            db,
            actor=administrator,
        )
    )

    assert sections == [
        archived,
    ]
    assert total_items == 1


def test_standard_user_cannot_list_archived_sections(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    with pytest.raises(
        PermissionDeniedError,
    ):
        SectionService.list_archived_sections(
            db,
            actor=user,
        )


def test_archived_section_listing_supports_pagination(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    company = create_company(
        db,
    )

    first = create_section(
        db,
        company=company,
        created_by=creator,
        name="A Section",
        is_archived=True,
    )

    second = create_section(
        db,
        company=company,
        created_by=creator,
        name="B Section",
        is_archived=True,
    )

    sections, total_items = (
        SectionService.list_archived_sections(
            db,
            actor=administrator,
            page=2,
            page_size=1,
        )
    )

    assert sections == [
        second,
    ]
    assert total_items == 2
    assert first not in sections


@pytest.mark.parametrize(
    (
        "page",
        "page_size",
    ),
    [
        (
            0,
            25,
        ),
        (
            1,
            0,
        ),
        (
            1,
            101,
        ),
    ],
)
def test_archived_section_listing_rejects_invalid_pagination(
    db: Session,
    page: int,
    page_size: int,
) -> None:
    administrator = create_administrator(
        db,
    )

    with pytest.raises(
        SectionArchiveFilterError,
    ):
        SectionService.list_archived_sections(
            db,
            actor=administrator,
            page=page,
            page_size=page_size,
        )


def test_administrator_restores_archived_section(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    company = create_company(
        db,
    )

    section = create_section(
        db,
        company=company,
        created_by=creator,
        is_archived=True,
    )

    result = SectionService.set_archived_status_by_id(
        db,
        actor=administrator,
        section_id=section.id,
        is_archived=False,
        commit=False,
    )

    assert result is section
    assert section.is_archived is False


def test_restoring_section_records_audit_log(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    company = create_company(
        db,
        name="Audit Company",
    )

    section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Audit Section",
        is_archived=True,
    )

    SectionService.set_archived_status_by_id(
        db,
        actor=administrator,
        section_id=section.id,
        is_archived=False,
        ip_address="192.0.2.60",
        user_agent="pytest section archive",
        commit=False,
    )

    audit_log = db.scalar(
        select(
            AuditLog,
        ).where(
            AuditLog.action
            == AuditAction.SECTION_RESTORED.value,
            AuditLog.entity_type
            == "section",
            AuditLog.entity_id
            == section.id,
        ),
    )

    assert audit_log is not None
    assert audit_log.user_id == administrator.id
    assert audit_log.metadata_json[
        "company_id"
    ] == company.id
    assert audit_log.metadata_json[
        "company_name"
    ] == company.name
    assert audit_log.metadata_json[
        "is_archived"
    ] is False


def test_cannot_restore_section_inside_archived_company(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    creator = create_user(
        db,
    )

    company = create_company(
        db,
        is_archived=True,
    )

    section = create_section(
        db,
        company=company,
        created_by=creator,
        is_archived=True,
    )

    with pytest.raises(
        SectionParentCompanyArchivedError,
        match="company is archived",
    ):
        SectionService.set_archived_status_by_id(
            db,
            actor=administrator,
            section_id=section.id,
            is_archived=False,
            commit=False,
        )

    assert section.is_archived is True