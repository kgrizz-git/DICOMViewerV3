"""
Online user documentation URLs (GitHub) with offline-bundle fallback.

All in-app links that open ``user-docs/*.md`` on GitHub are built from
**GITHUB_BLOB_BASE** / **USER_DOCS_GITHUB_PREFIX** below. Change
``GITHUB_BLOB_BASE`` when you fork the repo, use a different branch or tag, or
host docs elsewhere (keep the path ending at the blob root, not ``user-docs``).
Markdown under ``user-docs/`` that needs an absolute GitHub link (for example
``CHANGELOG.md`` or a contributor deep dive under ``dev-docs/``) should use the
same ``GITHUB_BLOB_BASE`` value — Markdown cannot import this module, so keep
those strings in sync when editing the constant.

Release builds also ship a pre-rendered offline copy of the user docs under
``resources/help/docs/`` (flat ``FOO.html`` files plus an ``index.html``
landing — flat layout pinned by ``use_directory_urls: false`` in ``mkdocs.yml``,
populated by ``scripts/build_offline_docs.py``). Callers that can open
a local file prefer ``local_doc_url(...)`` and fall back to the GitHub URL when
it returns None (bundle absent, e.g. a source checkout without a build step).

Used by:
  - ``Help → Documentation`` (``DialogCoordinator.open_user_documentation_in_browser``)
  - ``QuickStartGuideDialog`` (substitutes placeholders in ``quick_start_guide.html``)
  - 3D volume viewer help (``volume_viewer_widget._on_open_documentation``)

Inputs: none at runtime (edit constants; local bundle resolved from this file).
Outputs: full https URLs as strings, or ``file://`` URLs / Paths for the bundle.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Blob root through .../blob/<ref> (no trailing slash). For frozen builds whose
# behavior lags `main`, point this at a tag (e.g. .../blob/v0.2.10) so Help and
# absolute Markdown GitHub links match the binary — see RELEASING.md.
GITHUB_BLOB_BASE = "https://github.com/kgrizz-git/DICOMViewerV3/blob/main"

# Full URL prefix through .../user-docs (no trailing slash required).
USER_DOCS_GITHUB_PREFIX = f"{GITHUB_BLOB_BASE.rstrip('/')}/user-docs"


def repo_blob_url(relative_path: str) -> str:
    """
    Build the GitHub blob URL for a path at the repository root.

    Args:
        relative_path: e.g. ``CHANGELOG.md`` or ``dev-docs/info/FOO.md``.

    Returns:
        Full https URL to the blob view on GitHub.
    """
    name = relative_path.strip().lstrip("/")
    return f"{GITHUB_BLOB_BASE.rstrip('/')}/{name}"


def user_doc_url(filename: str) -> str:
    """
    Build the GitHub URL for a Markdown file under user-docs/.

    Args:
        filename: e.g. ``USER_GUIDE.md`` or ``USER_GUIDE_MPR.md`` (leading slashes stripped).

    Returns:
        Full https URL to the blob view on GitHub.
    """
    name = filename.strip().lstrip("/")
    base = USER_DOCS_GITHUB_PREFIX.rstrip("/")
    return f"{base}/{name}"


def user_guide_hub_url() -> str:
    """URL opened by Help → Documentation (user guide hub)."""
    return user_doc_url("USER_GUIDE.md")


def help_dir() -> Path:
    """Return the absolute path to ``resources/help/`` (dev and frozen builds)."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass is not None:
            return Path(str(meipass)) / "resources" / "help"
    return Path(__file__).resolve().parent.parent.parent / "resources" / "help"


def local_doc_file(filename: str) -> Path | None:
    """
    Resolve a user-docs Markdown name to its offline-bundle HTML file.

    Maps ``FOO.md`` to ``resources/help/docs/FOO.html`` (``index.md`` to
    ``resources/help/docs/index.html``). Returns None when the name is not a
    plain basename or when the bundle file does not exist (source checkouts
    without a release build step have no ``docs/`` directory).
    """
    name = filename.strip().lstrip("/")
    if not name or "/" in name or "\\" in name or ".." in name:
        return None
    stem = Path(name).stem
    if not stem:
        return None
    candidate = help_dir() / "docs" / f"{stem}.html"
    if not candidate.is_file():
        return None
    return candidate


def local_doc_url(filename: str) -> str | None:
    """
    Return the ``file://`` URL for a bundled doc page, or None when absent.

    Callers prefer this result and fall back to :func:`user_doc_url` when None.
    """
    path = local_doc_file(filename)
    if path is None:
        return None
    return path.as_uri()
