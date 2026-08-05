from pathlib import Path

from app.core.version import get_version


def test_get_version_reads_version_file(
    monkeypatch,
    tmp_path: Path,
) -> None:
    version_file = tmp_path / "VERSION.txt"

    version_file.write_text(
        "1.2.3\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "app.core.version.VERSION_FILE",
        version_file,
    )

    get_version.cache_clear()

    assert get_version() == "1.2.3"

    get_version.cache_clear()


def test_get_version_returns_development_when_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "app.core.version.VERSION_FILE",
        tmp_path / "missing.txt",
    )

    get_version.cache_clear()

    assert get_version() == "development"

    get_version.cache_clear()