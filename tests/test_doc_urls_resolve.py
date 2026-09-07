"""
Verify that in-app documentation links point at documents that exist.

``tests/test_doc_urls.py`` covers URL *string building*. It does not check that
the filenames handed to ``user_doc_url`` correspond to real files, so a renamed
or deleted guide would still produce a well-formed URL that 404s for the user.

This closes the mechanical half of TRIAGE-037 (DOC-11). What remains deferred is
launching the app and clicking each Help action; these tests instead pin the two
things that can be checked statically and would otherwise rot silently:

1. Every filename passed to ``user_doc_url(...)`` anywhere in ``src/`` exists
   under ``user-docs/``.
2. Every ``{doc_*}`` placeholder in ``resources/help/quick_start_guide.html`` has
   a substitution in ``QuickStartGuideDialog``. An unmapped placeholder ships to
   the user as literal ``{doc_FOO}`` text in the Quick Start window.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
USER_DOCS = REPO_ROOT / "user-docs"
SRC = REPO_ROOT / "src"
QUICK_START_HTML = REPO_ROOT / "resources" / "help" / "quick_start_guide.html"
QUICK_START_DIALOG = SRC / "gui" / "dialogs" / "quick_start_guide_dialog.py"

# user_doc_url("SOMETHING.md") — literal arguments only, which is how every
# current call site is written.
USER_DOC_URL_CALL = re.compile(r"""user_doc_url\(\s*["']([^"']+)["']\s*\)""")
PLACEHOLDER = re.compile(r"\{(doc_[A-Za-z0-9_]+)\}")
PLACEHOLDER_KEY = re.compile(r"""["'](doc_[A-Za-z0-9_]+)["']\s*:""")


def resolve_user_doc(filename: str) -> Path | None:
    """Resolve a filename under user-docs/, or None if it escapes that directory.

    A call site that passes ``../README.md`` or a leading-slash path is itself a
    bug; returning None makes the caller report it as missing rather than letting
    ``Path`` quietly resolve outside the documentation tree.
    """
    candidate = (USER_DOCS / filename.strip().lstrip("/")).resolve()
    if candidate != USER_DOCS and USER_DOCS not in candidate.parents:
        return None
    return candidate


def referenced_doc_filenames() -> dict[str, list[str]]:
    """Map each filename passed to user_doc_url() to the files referencing it."""
    referenced: dict[str, list[str]] = {}
    for path in sorted(SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for filename in USER_DOC_URL_CALL.findall(text):
            rel = str(path.relative_to(REPO_ROOT))
            referenced.setdefault(filename, []).append(rel)
    return referenced


def test_call_sites_are_discovered():
    """Guard the regex itself: if it stops matching, the rest is vacuously true."""
    referenced = referenced_doc_filenames()
    assert referenced, "no user_doc_url() call sites found; the scan regex is broken"
    assert "USER_GUIDE.md" in referenced


def test_every_linked_user_doc_exists():
    """A Help link must not resolve to a file that is not in the repository."""
    missing: list[str] = []
    for filename, sources in sorted(referenced_doc_filenames().items()):
        resolved = resolve_user_doc(filename)
        if resolved is None or not resolved.is_file():
            missing.append(f"{filename} (referenced by {', '.join(sources)})")
    assert not missing, "in-app Help links point at missing user-docs files: " + "; ".join(
        missing
    )


def test_quick_start_placeholders_are_all_substituted():
    """An unmapped placeholder renders as literal {doc_FOO} in the Quick Start."""
    html = QUICK_START_HTML.read_text(encoding="utf-8")
    dialog = QUICK_START_DIALOG.read_text(encoding="utf-8")
    used = set(PLACEHOLDER.findall(html))
    provided = set(PLACEHOLDER_KEY.findall(dialog))
    assert used, "no {doc_*} placeholders found; the scan regex is broken"
    unmapped = sorted(used - provided)
    assert not unmapped, (
        "Quick Start HTML uses placeholders with no substitution in "
        f"quick_start_guide_dialog.py: {', '.join(unmapped)}"
    )


def test_quick_start_substitutions_target_real_docs():
    """Every placeholder the dialog can substitute must resolve to a real file."""
    dialog = QUICK_START_DIALOG.read_text(encoding="utf-8")
    missing = []
    for filename in USER_DOC_URL_CALL.findall(dialog):
        resolved = resolve_user_doc(filename)
        if resolved is None or not resolved.is_file():
            missing.append(filename)
    assert not missing, "Quick Start substitutions point at missing files: " + ", ".join(
        missing
    )


def test_paths_escaping_user_docs_are_rejected():
    """A call site must never resolve to a file outside user-docs/.

    An absolute-looking path is re-rooted under user-docs/ (and so reported as
    missing); a traversal is rejected outright.
    """
    assert resolve_user_doc("../README.md") is None
    assert resolve_user_doc("/etc/passwd") == USER_DOCS / "etc" / "passwd"
    assert resolve_user_doc("USER_GUIDE.md") == USER_DOCS / "USER_GUIDE.md"
