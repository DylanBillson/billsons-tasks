from dataclasses import dataclass, field
from typing import Mapping

from pydantic import ValidationError

from app.core.constants import CompanyRole
from app.models.company import Company
from app.models.company_membership import CompanyMembership
from app.schemas.company import (
    CompanyCreateRequest,
    CompanyMembershipCreateRequest,
    CompanyMembershipUpdateRequest,
    CompanyUpdateRequest,
)
from app.web.forms.common import (
    FormErrors,
    apply_validation_errors,
    get_integer,
    get_optional_string,
    get_string,
)


@dataclass
class CompanyForm:
    name: str = ""
    description: str | None = None
    errors: FormErrors = field(
        default_factory=FormErrors,
    )

    @classmethod
    def from_form_data(
        cls,
        form_data: Mapping[str, object],
    ) -> "CompanyForm":
        return cls(
            name=get_string(
                form_data,
                "name",
            ),
            description=get_optional_string(
                form_data,
                "description",
            ),
        )

    @classmethod
    def from_company(
        cls,
        company: Company,
    ) -> "CompanyForm":
        return cls(
            name=company.name,
            description=company.description,
        )

    def validate_create(
        self,
    ) -> CompanyCreateRequest | None:
        self.errors = FormErrors()

        try:
            company_create = CompanyCreateRequest(
                name=self.name,
                description=self.description,
            )
        except ValidationError as exc:
            apply_validation_errors(
                errors=self.errors,
                exception=exc,
            )

            return None

        self.name = company_create.name
        self.description = company_create.description

        return company_create

    def validate_update(
        self,
    ) -> CompanyUpdateRequest | None:
        self.errors = FormErrors()

        try:
            company_update = CompanyUpdateRequest(
                name=self.name,
                description=self.description,
            )
        except ValidationError as exc:
            apply_validation_errors(
                errors=self.errors,
                exception=exc,
            )

            return None

        self.name = company_update.name
        self.description = company_update.description

        return company_update


@dataclass
class CompanyMembershipCreateForm:
    user_id: int | None = None
    role: str = CompanyRole.EMPLOYEE.value
    errors: FormErrors = field(
        default_factory=FormErrors,
    )

    @classmethod
    def from_form_data(
        cls,
        form_data: Mapping[str, object],
    ) -> "CompanyMembershipCreateForm":
        return cls(
            user_id=get_integer(
                form_data,
                "user_id",
            ),
            role=get_string(
                form_data,
                "role",
            )
            or CompanyRole.EMPLOYEE.value,
        )

    def validate(
        self,
    ) -> CompanyMembershipCreateRequest | None:
        self.errors = FormErrors()

        try:
            membership_create = CompanyMembershipCreateRequest(
                user_id=self.user_id,
                role=self.role,
            )
        except ValidationError as exc:
            apply_validation_errors(
                errors=self.errors,
                exception=exc,
            )

            return None

        self.user_id = membership_create.user_id
        self.role = membership_create.role.value

        return membership_create


@dataclass
class CompanyMembershipUpdateForm:
    role: str = CompanyRole.EMPLOYEE.value
    errors: FormErrors = field(
        default_factory=FormErrors,
    )

    @classmethod
    def from_form_data(
        cls,
        form_data: Mapping[str, object],
    ) -> "CompanyMembershipUpdateForm":
        return cls(
            role=get_string(
                form_data,
                "role",
            ),
        )

    @classmethod
    def from_membership(
        cls,
        membership: CompanyMembership,
    ) -> "CompanyMembershipUpdateForm":
        return cls(
            role=membership.role,
        )

    def validate(
        self,
    ) -> CompanyMembershipUpdateRequest | None:
        self.errors = FormErrors()

        try:
            membership_update = CompanyMembershipUpdateRequest(
                role=self.role,
            )
        except ValidationError as exc:
            apply_validation_errors(
                errors=self.errors,
                exception=exc,
            )

            return None

        self.role = membership_update.role.value

        return membership_update