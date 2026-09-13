"""
Online user documentation URLs (GitHub).

All in-app links that open ``user-docs/*.md`` on GitHub are built from
**GITHUB_BLOB_BASE** / **USER_DOCS_GITHUB_PREFIX** below. Change
``GITHUB_BLOB_BASE`` when you fork the repo, use a different branch or tag, or
host docs elsewhere (keep the path ending at the blob root, not ``user-docs``).
Markdown under ``user-docs/`` that needs an absolute GitHub link (for example
``CHANGELOG.md`` or a contributor deep dive under ``dev-docs/``) should use the
same ``GITHUB_BLOB_BASE`` value — Markdown cannot import this module, so keep
those strings in sync when editing the constant.

Used by:
  - ``Help → Documentation`` (``DialogCoordinator.open_user_documentation_in_browser``)
  - ``QuickStartGuideDialog`` (substitutes placeholders in ``quick_start_guide.html``)

Inputs: none at runtime (edit constants).
Outputs: full https URLs as strings.
"""

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
