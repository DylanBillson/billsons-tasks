from dataclasses import dataclass, field
from typing import Mapping

from pydantic import ValidationError

from app.models.section import Section
from app.schemas.section import (
    SectionCreateRequest,
    SectionMembershipCreateRequest,
    SectionUpdateRequest,
)
from app.web.forms.common import (
    FormErrors,
    apply_validation_errors,
    get_integer,
    get_optional_string,
    get_string,
)


@dataclass
class SectionForm:
    name: str = ""
    description: str | None = None
    errors: FormErrors = field(
        default_factory=FormErrors,
    )

    @classmethod
    def from_form_data(
        cls,
        form_data: Mapping[str, object],
    ) -> "SectionForm":
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
    def from_section(
        cls,
        section: Section,
    ) -> "SectionForm":
        return cls(
            name=section.name,
            description=section.description,
        )

    def validate_create(
        self,
    ) -> SectionCreateRequest | None:
        self.errors = FormErrors()

        try:
            section_create = SectionCreateRequest(
                name=self.name,
                description=self.description,
            )
        except ValidationError as exc:
            apply_validation_errors(
                errors=self.errors,
                exception=exc,
            )

            return None

        self.name = section_create.name
        self.description = section_create.description

        return section_create

    def validate_update(
        self,
    ) -> SectionUpdateRequest | None:
        self.errors = FormErrors()

        try:
            section_update = SectionUpdateRequest(
                name=self.name,
                description=self.description,
            )
        except ValidationError as exc:
            apply_validation_errors(
                errors=self.errors,
                exception=exc,
            )

            return None

        self.name = section_update.name
        self.description = section_update.description

        return section_update


@dataclass
class SectionMembershipCreateForm:
    user_id: int | None = None
    errors: FormErrors = field(
        default_factory=FormErrors,
    )

    @classmethod
    def from_form_data(
        cls,
        form_data: Mapping[str, object],
    ) -> "SectionMembershipCreateForm":
        return cls(
            user_id=get_integer(
                form_data,
                "user_id",
            ),
        )

    def validate(
        self,
    ) -> SectionMembershipCreateRequest | None:
        self.errors = FormErrors()

        try:
            membership_create = SectionMembershipCreateRequest(
                user_id=self.user_id,
            )
        except ValidationError as exc:
            apply_validation_errors(
                errors=self.errors,
                exception=exc,
            )

            return None

        self.user_id = membership_create.user_id

        return membership_create