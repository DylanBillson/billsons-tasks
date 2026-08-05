from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.constants import CompanyRole
from app.models.company_membership import (
    CompanyMembership,
)
from tests.factories import (
    create_administrator,
    create_auth_session,
    create_company,
    create_company_membership,
    create_user,
)


def _authenticate(
    client: TestClient,
    db: Session,
    *,
    user,
) -> str:
    _, session_token, csrf_token = create_auth_session(
        db,
        user=user,
    )

    db.commit()

    client.cookies.set(
        settings.session_cookie_name,
        session_token,
    )

    client.cookies.set(
        f"{settings.session_cookie_name}_csrf",
        csrf_token,
    )

    return csrf_token


def test_phase66_manager_membership_page_replaces_placeholder(
    client: TestClient,
    db: Session,
) -> None:
    company = create_company(
        db,
        name="Phase 66 Membership Company",
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

    db.commit()

    _authenticate(
        client,
        db,
        user=manager,
    )

    response = client.get(
        f"/companies/{company.id}/members",
        follow_redirects=False,
    )

    assert response.status_code == 200

    assert (
        "manager-facing company membership "
        "page has not been created"
        not in response.text
    )

    assert "Current Members" in response.text
    assert "Add Member" in response.text


def test_phase66_company_detail_links_manager_to_members_page(
    client: TestClient,
    db: Session,
) -> None:
    company = create_company(
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

    db.commit()

    _authenticate(
        client,
        db,
        user=manager,
    )

    response = client.get(
        f"/companies/{company.id}",
    )

    assert response.status_code == 200

    assert (
        f'href="http://testserver/companies/'
        f'{company.id}/members"'
        in response.text
    )

    assert "Manage Members" in response.text


def test_phase66_employee_company_detail_has_no_membership_link(
    client: TestClient,
    db: Session,
) -> None:
    company = create_company(
        db,
    )

    employee = create_user(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=employee,
        role=CompanyRole.EMPLOYEE,
    )

    db.commit()

    _authenticate(
        client,
        db,
        user=employee,
    )

    response = client.get(
        f"/companies/{company.id}",
    )

    assert response.status_code == 200

    assert (
        f"/companies/{company.id}/members"
        not in response.text
    )


def test_phase66_shared_membership_partials_exist() -> None:
    table_partial = Path(
        "app/web/templates/partials/"
        "company_membership_table.html",
    )

    form_partial = Path(
        "app/web/templates/partials/"
        "company_membership_form.html",
    )

    assert table_partial.is_file()
    assert form_partial.is_file()

    table_text = table_partial.read_text(
        encoding="utf-8",
    )

    form_text = form_partial.read_text(
        encoding="utf-8",
    )

    assert "membership_role_update_route_name" in (
        table_text
    )

    assert "membership_remove_route_name" in (
        table_text
    )

    assert "membership_add_route_name" in (
        form_text
    )


def test_phase66_admin_and_manager_templates_use_shared_partials() -> None:
    admin_template = Path(
        "app/web/templates/admin/companies/"
        "members.html",
    ).read_text(
        encoding="utf-8",
    )

    manager_template = Path(
        "app/web/templates/companies/"
        "members.html",
    ).read_text(
        encoding="utf-8",
    )

    for template in (
        admin_template,
        manager_template,
    ):
        assert (
            "partials/company_membership_table.html"
            in template
        )

        assert (
            "partials/company_membership_form.html"
            in template
        )


def test_phase66_manager_completes_membership_lifecycle(
    client: TestClient,
    db: Session,
) -> None:
    company = create_company(
        db,
    )

    manager = create_user(
        db,
    )

    target = create_user(
        db,
    )

    create_company_membership(
        db,
        company=company,
        user=manager,
        role=CompanyRole.MANAGER,
    )

    db.commit()

    csrf_token = _authenticate(
        client,
        db,
        user=manager,
    )

    add_response = client.post(
        f"/companies/{company.id}/members",
        data={
            "csrf_token": csrf_token,
            "user_id": str(
                target.id,
            ),
            "role": CompanyRole.EMPLOYEE.value,
        },
        follow_redirects=False,
    )

    assert add_response.status_code == 303

    membership = db.scalar(
        select(CompanyMembership).where(
            CompanyMembership.company_id
            == company.id,
            CompanyMembership.user_id
            == target.id,
        )
    )

    assert membership is not None

    update_response = client.post(
        (
            f"/companies/{company.id}/members/"
            f"{target.id}/role"
        ),
        data={
            "csrf_token": csrf_token,
            "role": CompanyRole.MANAGER.value,
        },
        follow_redirects=False,
    )

    assert update_response.status_code == 303

    db.refresh(
        membership,
    )

    assert membership.role == CompanyRole.MANAGER.value

    remove_response = client.post(
        (
            f"/companies/{company.id}/members/"
            f"{target.id}/remove"
        ),
        data={
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert remove_response.status_code == 303

    assert db.get(
        CompanyMembership,
        membership.id,
    ) is None