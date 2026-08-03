from dataclasses import dataclass, field
from typing import Mapping

from pydantic import ValidationError

from app.models.section_list import SectionList
from app.schemas.section_list import (
    SectionListCreateRequest,
    SectionListUpdateRequest,
)
from app.web.forms.common import (
    FormErrors,
    apply_validation_errors,
    get_string,
)


@dataclass
class SectionListForm:
    name: str = ""
    description: str = ""

    errors: FormErrors = field(
        default_factory=FormErrors,
    )

    @classmethod
    def from_form_data(
        cls,
        form_data: Mapping[str, object],
    ) -> "SectionListForm":
        return cls(
            name=get_string(
                form_data,
                "name",
            ),
            description=get_string(
                form_data,
                "description",
            ),
        )

    @classmethod
    def from_section_list(
        cls,
        section_list: SectionList,
    ) -> "SectionListForm":
        return cls(
            name=section_list.name,
            description=section_list.description or "",
        )

    def validate_create(
        self,
    ) -> SectionListCreateRequest | None:
        self.errors = FormErrors()

        try:
            request = SectionListCreateRequest(
                name=self.name,
                description=self.description,
            )

        except ValidationError as exc:
            apply_validation_errors(
                errors=self.errors,
                exception=exc,
            )

            return None

        self._apply_validated_values(
            request,
        )

        return request

    def validate_update(
        self,
    ) -> SectionListUpdateRequest | None:
        self.errors = FormErrors()

        try:
            request = SectionListUpdateRequest(
                name=self.name,
                description=self.description,
            )

        except ValidationError as exc:
            apply_validation_errors(
                errors=self.errors,
                exception=exc,
            )

            return None

        self._apply_validated_values(
            request,
        )

        return request

    def _apply_validated_values(
        self,
        request: (
            SectionListCreateRequest
            | SectionListUpdateRequest
        ),
    ) -> None:
        self.name = request.name
        self.description = request.description or ""