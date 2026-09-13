"""
Qt-free tests for the offline documentation bundle helpers in utils.doc_urls.

Covers ``help_dir`` / ``local_doc_file`` / ``local_doc_url`` path mapping and
the caller fallback pattern (``local_doc_url(...) or user_doc_url(...)``) used
by Help → Documentation, the 3D viewer help button, and Quick Start
placeholders. No Qt widgets are instantiated here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils import doc_urls
from utils.doc_urls import (
    help_dir,
    local_doc_file,
    local_doc_url,
    user_doc_url,
)


def _make_bundle(bundle_root: Path, stems: list[str]) -> Path:
    """Create ``docs/<stem>.html`` files under *bundle_root* and return it."""
    docs_dir = bundle_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    for stem in stems:
        (docs_dir / f"{stem}.html").write_text("<html></html>", encoding="utf-8")
    return bundle_root


def _point_help_dir(monkeypatch: pytest.MonkeyPatch, bundle_root: Path) -> None:
    """Redirect ``help_dir()`` at a tmp bundle for the duration of a test."""
    monkeypatch.setattr(doc_urls, "help_dir", lambda: bundle_root)


def test_help_dir_resolves_to_resources_help() -> None:
    """The real help dir is ``<repo>/resources/help`` (absolute path)."""
    resolved = help_dir()
    assert resolved.is_absolute()
    assert resolved.name == "help"
    assert resolved.parent.name == "resources"


def test_md_filename_maps_to_bundle_html(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``FOO.md`` resolves to ``docs/FOO.html`` when the bundle has it."""
    bundle_root = _make_bundle(tmp_path, ["USER_GUIDE"])
    _point_help_dir(monkeypatch, bundle_root)
    assert local_doc_file("USER_GUIDE.md") == bundle_root / "docs" / "USER_GUIDE.html"


def test_index_md_maps_to_index_html(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``index.md`` resolves to ``docs/index.html`` like any other page."""
    bundle_root = _make_bundle(tmp_path, ["index"])
    _point_help_dir(monkeypatch, bundle_root)
    assert local_doc_file("index.md") == bundle_root / "docs" / "index.html"


def test_name_normalization_strips_slashes_and_whitespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Leading slashes and surrounding whitespace are tolerated."""
    bundle_root = _make_bundle(tmp_path, ["USER_GUIDE_MPR"])
    _point_help_dir(monkeypatch, bundle_root)
    expected = bundle_root / "docs" / "USER_GUIDE_MPR.html"
    assert local_doc_file("  USER_GUIDE_MPR.md  ") == expected
    assert local_doc_file("/USER_GUIDE_MPR.md") == expected


def test_missing_page_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bundle without the page resolves to None (callers fall back to GitHub)."""
    bundle_root = _make_bundle(tmp_path, ["USER_GUIDE"])
    _point_help_dir(monkeypatch, bundle_root)
    assert local_doc_file("USER_GUIDE_3D.md") is None
    assert local_doc_url("USER_GUIDE_3D.md") is None


def test_absent_bundle_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No ``docs/`` directory at all (plain source checkout) resolves to None."""
    _point_help_dir(monkeypatch, tmp_path)
    assert local_doc_file("USER_GUIDE.md") is None
    assert local_doc_url("USER_GUIDE.md") is None


@pytest.mark.parametrize("bad_name", ["", "   ", "../README.md", "a/b.md", ".."])
def test_unsafe_names_return_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad_name: str
) -> None:
    """Empty, traversal, and nested names never resolve into the bundle."""
    bundle_root = _make_bundle(tmp_path, ["README"])
    _point_help_dir(monkeypatch, bundle_root)
    assert local_doc_file(bad_name) is None
    assert local_doc_url(bad_name) is None


def test_local_doc_url_forms_file_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Present pages produce a ``file://`` URL via ``Path.as_uri()``."""
    bundle_root = _make_bundle(tmp_path, ["USER_GUIDE_3D"])
    _point_help_dir(monkeypatch, bundle_root)
    url = local_doc_url("USER_GUIDE_3D.md")
    assert url is not None
    assert url.startswith("file://")
    assert url.endswith("/docs/USER_GUIDE_3D.html")
    expected = (bundle_root / "docs" / "USER_GUIDE_3D.html").as_uri()
    assert url == expected


def test_fallback_prefers_local_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Caller pattern selects the local ``file://`` URL when bundled."""
    bundle_root = _make_bundle(tmp_path, ["USER_GUIDE"])
    _point_help_dir(monkeypatch, bundle_root)
    selected = local_doc_url("USER_GUIDE.md") or user_doc_url("USER_GUIDE.md")
    assert selected.startswith("file://")
    assert selected.endswith("/docs/USER_GUIDE.html")


def test_fallback_uses_github_when_bundle_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Caller pattern selects the GitHub URL when the bundle is absent."""
    _point_help_dir(monkeypatch, tmp_path)
    selected = local_doc_url("USER_GUIDE.md") or user_doc_url("USER_GUIDE.md")
    assert selected == user_doc_url("USER_GUIDE.md")
    assert selected.startswith("https://")


def test_fallback_matrix_over_known_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Per-page fallback across the Quick Start placeholder set stays consistent."""
    pages: dict[str, bool] = {
        "USER_GUIDE.md": True,
        "CONFIGURATION.md": False,
        "USER_GUIDE_3D.md": True,
    }
    bundle_root = _make_bundle(tmp_path, [Path(k).stem for k, v in pages.items() if v])
    _point_help_dir(monkeypatch, bundle_root)
    for filename, bundled in pages.items():
        selected = local_doc_url(filename) or user_doc_url(filename)
        if bundled:
            assert selected.startswith("file://")
        else:
            assert selected == user_doc_url(filename)
