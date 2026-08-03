import pytest
from sqlalchemy.orm import Session

from app.auth.permissions import (
    PermissionDeniedError,
    PermissionService,
)
from tests.factories import (
    create_administrator,
    create_company,
    create_company_membership,
    create_user,
)


def test_active_user_can_view_global_dashboard(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    assert (
        PermissionService.can_view_global_dashboard(
            actor=user,
        )
        is True
    )


def test_inactive_user_cannot_view_global_dashboard(
    db: Session,
) -> None:
    user = create_user(
        db,
        is_active=False,
    )

    assert (
        PermissionService.can_view_global_dashboard(
            actor=user,
        )
        is False
    )


def test_anonymised_user_cannot_view_global_dashboard(
    db: Session,
) -> None:
    user = create_user(
        db,
        is_active=False,
        is_anonymised=True,
    )

    assert (
        PermissionService.can_view_global_dashboard(
            actor=user,
        )
        is False
    )


def test_active_user_can_view_my_tasks(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    assert (
        PermissionService.can_view_my_tasks(
            actor=user,
        )
        is True
    )


def test_inactive_user_cannot_view_my_tasks(
    db: Session,
) -> None:
    user = create_user(
        db,
        is_active=False,
    )

    assert (
        PermissionService.can_view_my_tasks(
            actor=user,
        )
        is False
    )


def test_administrator_can_view_any_company_dashboard(
    db: Session,
) -> None:
    administrator = create_administrator(
        db,
    )

    company = create_company(
        db,
    )

    assert (
        PermissionService.can_view_company_dashboard(
            db,
            actor=administrator,
            company=company,
        )
        is True
    )


def test_company_member_can_view_company_dashboard(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    company = create_company(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=user,
    )

    assert (
        PermissionService.can_view_company_dashboard(
            db,
            actor=user,
            company=company,
        )
        is True
    )


def test_outsider_cannot_view_company_dashboard(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    company = create_company(
        db,
    )

    assert (
        PermissionService.can_view_company_dashboard(
            db,
            actor=user,
            company=company,
        )
        is False
    )


def test_require_company_dashboard_access_rejects_outsider(
    db: Session,
) -> None:
    user = create_user(
        db,
    )

    company = create_company(
        db,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="company dashboard",
    ):
        PermissionService.require_company_dashboard_access(
            db,
            actor=user,
            company=company,
        )


def test_require_global_dashboard_access_rejects_inactive_user(
    db: Session,
) -> None:
    user = create_user(
        db,
        is_active=False,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="dashboard",
    ):
        PermissionService.require_global_dashboard_access(
            actor=user,
        )


def test_require_my_tasks_access_rejects_anonymised_user(
    db: Session,
) -> None:
    user = create_user(
        db,
        is_active=False,
        is_anonymised=True,
    )

    with pytest.raises(
        PermissionDeniedError,
        match="My Tasks",
    ):
        PermissionService.require_my_tasks_access(
            actor=user,
        )