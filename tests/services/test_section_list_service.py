import pytest
from sqlalchemy.orm import Session

from app.auth.permissions import PermissionDeniedError
from app.core.constants import AuditAction, CompanyRole
from app.repositories.audit_repository import AuditRepository
from app.schemas.section_list import (
    SectionListCreateRequest,
    SectionListPositionUpdate,
    SectionListReorderRequest,
    SectionListUpdateRequest,
)
from app.services.section_list_service import (
    SectionListNameAlreadyExistsError,
    SectionListNotEmptyError,
    SectionListNotFoundError,
    SectionListReorderError,
    SectionListService,
)
from tests.factories import (
    create_administrator,
    create_company,
    create_company_membership,
    create_section,
    create_section_list,
    create_section_membership,
    create_task,
    create_user,
)


def _create_context(
    db: Session,
):
    company = create_company(
        db,
    )

    creator = create_user(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=creator,
        role=CompanyRole.MANAGER,
    )

    section = create_section(
        db,
        company=company,
        created_by=creator,
    )

    return (
        company,
        creator,
        section,
    )


def _create_section_member(
    db: Session,
    *,
    company,
    section,
):
    member = create_user(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=member,
        role=CompanyRole.EMPLOYEE,
    )

    create_section_membership(
        db,
        section=section,
        user=member,
    )

    return member


def test_get_list_returns_existing_list(
    db: Session,
) -> None:
    _, _, section = _create_context(
        db,
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    result = SectionListService.get_list(
        db,
        section_list_id=section_list.id,
    )

    assert result is section_list


def test_get_list_returns_none_for_unknown_list(
    db: Session,
) -> None:
    result = SectionListService.get_list(
        db,
        section_list_id=999999,
    )

    assert result is None


def test_require_list_returns_existing_list(
    db: Session,
) -> None:
    _, _, section = _create_context(
        db,
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    result = SectionListService.require_list(
        db,
        section_list_id=section_list.id,
    )

    assert result is section_list


def test_require_list_raises_for_unknown_list(
    db: Session,
) -> None:
    with pytest.raises(
        SectionListNotFoundError,
        match="List was not found",
    ):
        SectionListService.require_list(
            db,
            section_list_id=999999,
        )


def test_get_accessible_list_returns_list_for_section_creator(
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    result = SectionListService.get_accessible_list(
        db,
        actor=creator,
        section_list_id=section_list.id,
    )

    assert result is section_list


def test_get_accessible_list_returns_list_for_section_member(
    db: Session,
) -> None:
    company, _, section = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    result = SectionListService.get_accessible_list(
        db,
        actor=member,
        section_list_id=section_list.id,
    )

    assert result is section_list


def test_get_accessible_list_denies_unassigned_company_manager(
    db: Session,
) -> None:
    company, _, section = _create_context(
        db,
    )

    manager = create_user(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="access to this list",
    ):
        SectionListService.get_accessible_list(
            db,
            actor=manager,
            section_list_id=section_list.id,
        )


def test_list_for_section_returns_active_lists_in_order(
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    later = create_section_list(
        db,
        section=section,
        name="Later",
        sort_position=3000,
    )

    first = create_section_list(
        db,
        section=section,
        name="First",
        sort_position=1000,
    )

    create_section_list(
        db,
        section=section,
        name="Archived",
        sort_position=2000,
        is_archived=True,
    )

    result = SectionListService.list_for_section(
        db,
        actor=creator,
        section=section,
    )

    assert result == [
        first,
        later,
    ]


def test_list_for_section_can_include_archived_lists(
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    active = create_section_list(
        db,
        section=section,
        sort_position=1000,
    )

    archived = create_section_list(
        db,
        section=section,
        sort_position=2000,
        is_archived=True,
    )

    result = SectionListService.list_for_section(
        db,
        actor=creator,
        section=section,
        include_archived=True,
    )

    assert result == [
        active,
        archived,
    ]


def test_list_for_section_denies_user_without_section_access(
    db: Session,
) -> None:
    company, _, section = _create_context(
        db,
    )

    company_member = create_user(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=company_member,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="access to this section",
    ):
        SectionListService.list_for_section(
            db,
            actor=company_member,
            section=section,
        )


def test_section_creator_creates_list(
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    section_list = SectionListService.create_list(
        db,
        actor=creator,
        section=section,
        section_list_create=SectionListCreateRequest(
            name="To Do",
            description="Tasks waiting to start.",
        ),
        commit=False,
    )

    assert section_list.id is not None
    assert section_list.section_id == section.id
    assert section_list.name == "To Do"
    assert section_list.description == "Tasks waiting to start."
    assert section_list.sort_position == 1000
    assert section_list.is_archived is False


def test_administrator_creates_list(
    db: Session,
) -> None:
    _, _, section = _create_context(
        db,
    )

    administrator = create_administrator(
        db,
    )

    section_list = SectionListService.create_list(
        db,
        actor=administrator,
        section=section,
        section_list_create=SectionListCreateRequest(
            name="To Do",
        ),
        commit=False,
    )

    assert section_list.section_id == section.id
    assert section_list.name == "To Do"


def test_explicit_section_member_cannot_create_list(
    db: Session,
) -> None:
    company, _, section = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="create lists",
    ):
        SectionListService.create_list(
            db,
            actor=member,
            section=section,
            section_list_create=SectionListCreateRequest(
                name="To Do",
            ),
            commit=False,
        )


def test_unassigned_company_manager_cannot_create_list(
    db: Session,
) -> None:
    company, _, section = _create_context(
        db,
    )

    manager = create_user(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="create lists",
    ):
        SectionListService.create_list(
            db,
            actor=manager,
            section=section,
            section_list_create=SectionListCreateRequest(
                name="To Do",
            ),
            commit=False,
        )


def test_create_list_rejects_archived_section(
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    section.is_archived = True
    db.flush()

    with pytest.raises(
        PermissionDeniedError,
        match="create lists",
    ):
        SectionListService.create_list(
            db,
            actor=creator,
            section=section,
            section_list_create=SectionListCreateRequest(
                name="To Do",
            ),
            commit=False,
        )


def test_create_list_rejects_archived_company(
    db: Session,
) -> None:
    company, creator, section = _create_context(
        db,
    )

    company.is_archived = True
    db.flush()

    with pytest.raises(
        PermissionDeniedError,
        match="create lists",
    ):
        SectionListService.create_list(
            db,
            actor=creator,
            section=section,
            section_list_create=SectionListCreateRequest(
                name="To Do",
            ),
            commit=False,
        )


def test_create_list_uses_next_sort_position(
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    create_section_list(
        db,
        section=section,
        sort_position=3000,
    )

    section_list = SectionListService.create_list(
        db,
        actor=creator,
        section=section,
        section_list_create=SectionListCreateRequest(
            name="New List",
        ),
        commit=False,
    )

    assert section_list.sort_position == 4000


def test_create_list_rejects_duplicate_name(
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    create_section_list(
        db,
        section=section,
        name="To Do",
    )

    with pytest.raises(
        SectionListNameAlreadyExistsError,
        match="already exists",
    ):
        SectionListService.create_list(
            db,
            actor=creator,
            section=section,
            section_list_create=SectionListCreateRequest(
                name="To Do",
            ),
            commit=False,
        )


def test_create_list_records_audit_log(
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    section_list = SectionListService.create_list(
        db,
        actor=creator,
        section=section,
        section_list_create=SectionListCreateRequest(
            name="To Do",
            description="Pending tasks.",
        ),
        ip_address="192.0.2.10",
        user_agent="pytest section-list service",
        commit=False,
    )

    audit_logs = AuditRepository.list_logs(
        db,
        action=AuditAction.LIST_CREATED.value,
    )

    matching = [
        log
        for log in audit_logs
        if (
            log.entity_type == "section_list"
            and log.entity_id == section_list.id
        )
    ]

    assert len(matching) == 1

    audit_log = matching[0]

    assert audit_log.user_id == creator.id
    assert audit_log.action == AuditAction.LIST_CREATED.value
    assert audit_log.metadata_json["section_id"] == section.id
    assert audit_log.metadata_json["name"] == "To Do"
    assert audit_log.ip_address == "192.0.2.10"


def test_section_creator_updates_list(
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    section_list = create_section_list(
        db,
        section=section,
        name="Old Name",
        description="Old description.",
    )

    result = SectionListService.update_list(
        db,
        actor=creator,
        section_list=section_list,
        section_list_update=SectionListUpdateRequest(
            name="New Name",
            description="New description.",
        ),
        commit=False,
    )

    assert result is section_list
    assert section_list.name == "New Name"
    assert section_list.description == "New description."


def test_section_member_cannot_update_list(
    db: Session,
) -> None:
    company, _, section = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="manage this list",
    ):
        SectionListService.update_list(
            db,
            actor=member,
            section_list=section_list,
            section_list_update=SectionListUpdateRequest(
                name="Updated",
            ),
            commit=False,
        )


def test_update_list_rejects_duplicate_name(
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    first = create_section_list(
        db,
        section=section,
        name="To Do",
    )

    create_section_list(
        db,
        section=section,
        name="In Progress",
    )

    with pytest.raises(
        SectionListNameAlreadyExistsError,
        match="already exists",
    ):
        SectionListService.update_list(
            db,
            actor=creator,
            section_list=first,
            section_list_update=SectionListUpdateRequest(
                name="In Progress",
            ),
            commit=False,
        )


def test_update_list_allows_same_existing_name(
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    section_list = create_section_list(
        db,
        section=section,
        name="To Do",
        description="Old description.",
    )

    result = SectionListService.update_list(
        db,
        actor=creator,
        section_list=section_list,
        section_list_update=SectionListUpdateRequest(
            name="To Do",
            description="New description.",
        ),
        commit=False,
    )

    assert result is section_list
    assert section_list.name == "To Do"
    assert section_list.description == "New description."


def test_update_list_records_audit_log(
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    section_list = create_section_list(
        db,
        section=section,
        name="Old Name",
    )

    SectionListService.update_list(
        db,
        actor=creator,
        section_list=section_list,
        section_list_update=SectionListUpdateRequest(
            name="New Name",
        ),
        commit=False,
    )

    audit_logs = AuditRepository.list_logs(
        db,
        action=AuditAction.LIST_UPDATED.value,
    )

    matching = [
        log
        for log in audit_logs
        if (
            log.entity_type == "section_list"
            and log.entity_id == section_list.id
        )
    ]

    assert len(matching) == 1
    assert matching[0].metadata_json["previous_name"] == "Old Name"
    assert matching[0].metadata_json["name"] == "New Name"


def test_section_creator_archives_list(
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    result = SectionListService.set_archived_status(
        db,
        actor=creator,
        section_list=section_list,
        is_archived=True,
        commit=False,
    )

    assert result is section_list
    assert section_list.is_archived is True


def test_section_creator_restores_archived_list(
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    section_list = create_section_list(
        db,
        section=section,
        is_archived=True,
    )

    result = SectionListService.set_archived_status(
        db,
        actor=creator,
        section_list=section_list,
        is_archived=False,
        commit=False,
    )

    assert result is section_list
    assert section_list.is_archived is False


def test_archiving_list_records_audit_log(
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    section_list = create_section_list(
        db,
        section=section,
        name="To Do",
    )

    SectionListService.set_archived_status(
        db,
        actor=creator,
        section_list=section_list,
        is_archived=True,
        commit=False,
    )

    audit_logs = AuditRepository.list_logs(
        db,
        action=AuditAction.LIST_ARCHIVED.value,
    )

    matching = [
        log
        for log in audit_logs
        if log.entity_id == section_list.id
    ]

    assert len(matching) == 1
    assert matching[0].metadata_json["is_archived"] is True


def test_setting_same_archive_status_is_noop(
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    section_list = create_section_list(
        db,
        section=section,
        is_archived=False,
    )

    result = SectionListService.set_archived_status(
        db,
        actor=creator,
        section_list=section_list,
        is_archived=False,
        commit=False,
    )

    assert result is section_list

    audit_logs = AuditRepository.list_logs(
        db,
        action=AuditAction.LIST_RESTORED.value,
    )

    assert all(
        log.entity_id != section_list.id
        for log in audit_logs
    )


def test_section_creator_reorders_lists(
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    first = create_section_list(
        db,
        section=section,
        name="First",
        sort_position=1000,
    )

    second = create_section_list(
        db,
        section=section,
        name="Second",
        sort_position=2000,
    )

    result = SectionListService.reorder_lists(
        db,
        actor=creator,
        section=section,
        reorder_request=SectionListReorderRequest(
            items=[
                SectionListPositionUpdate(
                    list_id=first.id,
                    sort_position=3000,
                ),
                SectionListPositionUpdate(
                    list_id=second.id,
                    sort_position=1000,
                ),
            ],
        ),
        commit=False,
    )

    assert first.sort_position == 3000
    assert second.sort_position == 1000
    assert result == [
        second,
        first,
    ]


def test_section_member_cannot_reorder_lists(
    db: Session,
) -> None:
    company, _, section = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="reorder lists",
    ):
        SectionListService.reorder_lists(
            db,
            actor=member,
            section=section,
            reorder_request=SectionListReorderRequest(
                items=[
                    SectionListPositionUpdate(
                        list_id=section_list.id,
                        sort_position=1000,
                    ),
                ],
            ),
            commit=False,
        )


def test_reorder_lists_rejects_list_from_other_section(
    db: Session,
) -> None:
    company, creator, section = _create_context(
        db,
    )

    local_list = create_section_list(
        db,
        section=section,
    )

    other_section = create_section(
        db,
        company=company,
        created_by=creator,
        name="Other Section",
    )

    foreign_list = create_section_list(
        db,
        section=other_section,
    )

    with pytest.raises(
        SectionListReorderError,
        match="does not belong to this section",
    ):
        SectionListService.reorder_lists(
            db,
            actor=creator,
            section=section,
            reorder_request=SectionListReorderRequest(
                items=[
                    SectionListPositionUpdate(
                        list_id=local_list.id,
                        sort_position=1000,
                    ),
                    SectionListPositionUpdate(
                        list_id=foreign_list.id,
                        sort_position=2000,
                    ),
                ],
            ),
            commit=False,
        )


def test_reorder_lists_records_audit_log(
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    SectionListService.reorder_lists(
        db,
        actor=creator,
        section=section,
        reorder_request=SectionListReorderRequest(
            items=[
                SectionListPositionUpdate(
                    list_id=section_list.id,
                    sort_position=2500,
                ),
            ],
        ),
        commit=False,
    )

    audit_logs = AuditRepository.list_logs(
        db,
        action=AuditAction.LIST_UPDATED.value,
    )

    matching = [
        log
        for log in audit_logs
        if (
            log.entity_type == "section"
            and log.entity_id == section.id
        )
    ]

    assert len(matching) == 1

    positions = matching[0].metadata_json["list_positions"]

    assert (
        positions[str(section_list.id)] == 2500
        or positions[section_list.id] == 2500
    )


def test_section_creator_deletes_empty_list(
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    section_list_id = section_list.id

    SectionListService.delete_list(
        db,
        actor=creator,
        section_list=section_list,
        commit=False,
    )

    assert SectionListService.get_list(
        db,
        section_list_id=section_list_id,
    ) is None


def test_delete_list_rejects_non_empty_list(
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    create_task(
        db,
        section_list=section_list,
        created_by=creator,
    )

    with pytest.raises(
        SectionListNotEmptyError,
        match="containing tasks",
    ):
        SectionListService.delete_list(
            db,
            actor=creator,
            section_list=section_list,
            commit=False,
        )


def test_section_member_cannot_delete_list(
    db: Session,
) -> None:
    company, _, section = _create_context(
        db,
    )

    member = _create_section_member(
        db,
        company=company,
        section=section,
    )

    section_list = create_section_list(
        db,
        section=section,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="manage this list",
    ):
        SectionListService.delete_list(
            db,
            actor=member,
            section_list=section_list,
            commit=False,
        )


def test_delete_list_records_audit_log(
    db: Session,
) -> None:
    _, creator, section = _create_context(
        db,
    )

    section_list = create_section_list(
        db,
        section=section,
        name="Temporary",
    )

    section_list_id = section_list.id

    SectionListService.delete_list(
        db,
        actor=creator,
        section_list=section_list,
        commit=False,
    )

    audit_logs = AuditRepository.list_logs(
        db,
        action=AuditAction.LIST_DELETED.value,
    )

    matching = [
        log
        for log in audit_logs
        if (
            log.entity_type == "section_list"
            and log.entity_id == section_list_id
        )
    ]

    assert len(matching) == 1
    assert matching[0].metadata_json["section_id"] == section.id
    assert matching[0].metadata_json["name"] == "Temporary"