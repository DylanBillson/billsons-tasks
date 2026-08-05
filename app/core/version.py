from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VERSION_FILE = PROJECT_ROOT / "VERSION.txt"


@lru_cache
def get_version() -> str:
    try:
        version = VERSION_FILE.read_text(
            encoding="utf-8",
        ).strip()

        if version:
            return version

    except OSError:
        pass

    return "development"