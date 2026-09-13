"""
Config-URL alignment: ``mkdocs.yml`` publisher URLs vs ``doc_urls.py``.

Constraint 5 of the user-docs platform plan: publisher ``repo_url`` /
``edit_uri`` (or Zensical equivalents) must target the same ``main`` +
``user-docs/`` paths as ``USER_DOCS_GITHUB_PREFIX`` in
``src/utils/doc_urls.py``, so Constraint 5 cannot silently drift the way
relative links once did.

PyYAML note: no other test imports ``yaml``; it resolves via the mkdocs
chain (``import yaml`` verified in the project ``.venv``, 6.0.3) and CI
installs ``requirements-dev.txt`` (which pins ``mkdocs``), so a direct
import is used here instead of a regex fallback.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from utils.doc_urls import (
    GITHUB_BLOB_BASE,
    USER_DOCS_GITHUB_PREFIX,
    user_doc_url,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MKDOCS_YML = REPO_ROOT / "mkdocs.yml"
USER_DOCS = REPO_ROOT / "user-docs"

# Sample of nav targets: landing hub pointer + user guide hub (minimum per plan).
SAMPLE_TARGETS = ["index.md", "USER_GUIDE.md"]


def _load_mkdocs_config() -> dict[str, Any]:
    text = MKDOCS_YML.read_text(encoding="utf-8")
    config = yaml.safe_load(text)
    assert isinstance(config, dict), "mkdocs.yml must parse to a mapping"
    return config


def _docs_dir(config: dict[str, Any]) -> Path:
    docs_dir = config.get("docs_dir", "docs")
    assert docs_dir == "user-docs", f"docs_dir drifted: {docs_dir!r}"
    resolved = (REPO_ROOT / str(docs_dir)).resolve()
    assert resolved == USER_DOCS.resolve(), f"docs_dir does not resolve to user-docs/: {resolved}"
    return resolved


def _nav_targets(config: dict[str, Any]) -> list[str]:
    targets: list[str] = []
    nav = config.get("nav", [])
    assert isinstance(nav, list) and nav, "mkdocs.yml nav must be a non-empty list"
    for entry in nav:
        assert isinstance(entry, dict) and len(entry) == 1, (
            f"unexpected nav entry shape: {entry!r}"
        )
        targets.append(next(iter(entry.values())))
    return targets


def test_repo_url_matches_github_blob_base():
    """``repo_url`` + ``/blob/main`` must equal ``GITHUB_BLOB_BASE``."""
    config = _load_mkdocs_config()
    repo_url = str(config["repo_url"]).rstrip("/")
    assert f"{repo_url}/blob/main" == GITHUB_BLOB_BASE


def test_edit_uri_targets_same_user_docs_tree():
    """``repo_url`` + ``edit_uri`` must share the blob prefix's repo/branch/path.

    Edit links use the ``/edit/`` verb where blob links use ``/blob/``;
    everything else (repo slug, ``main``, ``user-docs``) must agree.
    """
    config = _load_mkdocs_config()
    repo_url = str(config["repo_url"]).rstrip("/")
    edit_uri = str(config["edit_uri"]).strip("/")
    assert edit_uri == "edit/main/user-docs", (
        f"edit_uri drifted: {edit_uri!r}"
    )
    edit_base = f"{repo_url}/{edit_uri}"
    assert edit_base.replace("/edit/", "/blob/") == USER_DOCS_GITHUB_PREFIX


def test_sample_nav_targets_align_with_doc_urls():
    """Edit-link and blob URLs agree per nav target (index + USER_GUIDE)."""
    config = _load_mkdocs_config()
    docs_root = _docs_dir(config)
    repo_url = str(config["repo_url"]).rstrip("/")
    edit_uri = str(config["edit_uri"]).strip("/")
    edit_base = f"{repo_url}/{edit_uri}"
    targets = _nav_targets(config)
    for filename in SAMPLE_TARGETS:
        assert filename in targets, (
            f"{filename} missing from mkdocs.yml nav: {targets}"
        )
        blob_url = f"{USER_DOCS_GITHUB_PREFIX}/{filename}"
        assert user_doc_url(filename) == blob_url
        assert f"{edit_base}/{filename}" == blob_url.replace("/blob/", "/edit/")
        resolved = (docs_root / filename).resolve()
        assert resolved.is_file(), f"nav target not found under docs_dir: {filename}"
