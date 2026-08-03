from dataclasses import dataclass
from typing import Mapping


DEFAULT_ARCHIVE_PAGE_SIZE = 25
MAX_ARCHIVE_PAGE_SIZE = 100


@dataclass
class ArchiveFilterForm:
    company_id: str = ""
    search: str = ""
    page: int = 1
    page_size: int = DEFAULT_ARCHIVE_PAGE_SIZE

    @classmethod
    def from_query_params(
        cls,
        query_params: Mapping[str, object],
    ) -> "ArchiveFilterForm":
        search = str(
            query_params.get(
                "search",
                "",
            )
            or "",
        ).strip()

        page = cls._parse_positive_integer(
            query_params.get(
                "page",
            ),
            default=1,
        )

        page_size = cls._parse_positive_integer(
            query_params.get(
                "page_size",
            ),
            default=DEFAULT_ARCHIVE_PAGE_SIZE,
        )

        page_size = min(
            page_size,
            MAX_ARCHIVE_PAGE_SIZE,
        )

        return cls(
            search=search,
            page=page,
            page_size=page_size,
        )

    @property
    def is_active(
        self,
    ) -> bool:
        return bool(
            self.search,
        )

    @staticmethod
    def _parse_positive_integer(
        value: object,
        *,
        default: int,
    ) -> int:
        if value is None:
            return default

        try:
            parsed = int(
                str(
                    value,
                ),
            )

        except (
            TypeError,
            ValueError,
        ):
            return default

        if parsed < 1:
            return default

        return parsed