from dataclasses import dataclass, field
from typing import Mapping

from app.core.constants import (
    ANONYMISATION_CONFIRMATION_PHRASE,
)
from app.web.forms.common import FormErrors


@dataclass
class UserDeactivationForm:
    confirm_deactivation: bool = False
    errors: FormErrors = field(
        default_factory=FormErrors,
    )

    @classmethod
    def from_form_data(
        cls,
        form_data: Mapping[str, object],
    ) -> "UserDeactivationForm":
        raw_value = form_data.get(
            "confirm_deactivation",
        )

        return cls(
            confirm_deactivation=(
                str(
                    raw_value,
                ).strip().lower()
                in {
                    "1",
                    "true",
                    "yes",
                    "on",
                }
            ),
        )

    def validate(
        self,
    ) -> bool:
        self.errors = FormErrors()

        if not self.confirm_deactivation:
            self.errors.add_field_error(
                "confirm_deactivation",
                (
                    "Confirm that you want to deactivate "
                    "this user."
                ),
            )

        return not self.errors.has_errors


@dataclass
class UserAnonymisationForm:
    confirmation_phrase: str = ""
    confirm_irreversible: bool = False
    errors: FormErrors = field(
        default_factory=FormErrors,
    )

    @classmethod
    def from_form_data(
        cls,
        form_data: Mapping[str, object],
    ) -> "UserAnonymisationForm":
        phrase = form_data.get(
            "confirmation_phrase",
            "",
        )

        irreversible = form_data.get(
            "confirm_irreversible",
        )

        return cls(
            confirmation_phrase=str(
                phrase
                or "",
            ).strip(),
            confirm_irreversible=(
                str(
                    irreversible,
                ).strip().lower()
                in {
                    "1",
                    "true",
                    "yes",
                    "on",
                }
            ),
        )

    def validate(
        self,
    ) -> bool:
        self.errors = FormErrors()

        if (
            self.confirmation_phrase
            != ANONYMISATION_CONFIRMATION_PHRASE
        ):
            self.errors.add_field_error(
                "confirmation_phrase",
                (
                    "Enter ANONYMISE USER exactly "
                    "to continue."
                ),
            )

        if not self.confirm_irreversible:
            self.errors.add_field_error(
                "confirm_irreversible",
                (
                    "Confirm that you understand "
                    "anonymisation is irreversible."
                ),
            )

        return not self.errors.has_errors