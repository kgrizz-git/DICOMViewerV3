"""
Online user documentation URLs (GitHub).

All in-app links that open ``user-docs/*.md`` on GitHub are built from
**USER_DOCS_GITHUB_PREFIX** below. Change it when you fork the repo, use a
different branch, or host docs elsewhere (keep the path ending at ``user-docs``).

Used by:
  - ``Help → Documentation`` (``DialogCoordinator.open_user_documentation_in_browser``)
  - ``QuickStartGuideDialog`` (substitutes placeholders in ``quick_start_guide.html``)

Inputs: none at runtime (edit constants).
Outputs: full https URLs as strings.
"""

# Full URL prefix through .../user-docs (no trailing slash required).
USER_DOCS_GITHUB_PREFIX = (
    "https://github.com/kgrizz-git/DICOMViewerV3/blob/main/user-docs"
)


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
