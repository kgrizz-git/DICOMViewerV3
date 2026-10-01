#!/usr/bin/env python3
"""
Verify documentation references resolve: relative Markdown links, and inline
code paths pointing into src/.

Blocking coverage is user-docs/, the root README.md and ARCHITECTURE.md,
AGENTS.md, the top level of dev-docs/, dev-docs/info/, and the **active** plan
tree (dev-docs/plans/*.md and dev-docs/plans/supporting/*.md). Active plans are
live work documents that someone is implementing from right now, so a broken
link in one is a real defect.

``dev-docs/plans/completed/`` is deliberately excluded. A completed plan
describes the tree as it was when it was written, so a link to a file that was
later renamed is an *accurate* record rather than a defect; repairing those would
rewrite history to match a present the plan never described. CHANGELOG.md is
excluded for the same reason - released entries name modules that have since
moved.

Because the exclusion hides a whole subtree, ``--include-completed-plans`` makes
it visible: that mode reports rot in completed plans as **advisory** output and
still exits 0, so the debt can be measured without becoming a gate. It is a
report, not a policy change; a 40-link backlog in historical records is expected
and is not a failure.

Two checks run over the covered files:

1. **Relative Markdown links.** Scans inline links of the form [text](url). Skips
    http(s), mailto, and bare fragment-only targets. Resolves each relative URL
    against the source file's directory and fails if the target does not exist.
    For files under ``user-docs/``, a relative link whose resolved target falls
    outside ``user-docs/`` also fails, even if the target exists elsewhere in the
    repository. Absolute ``https://github.com/.../blob/...`` links under
    ``user-docs/`` must share the ``GITHUB_BLOB_BASE`` prefix from
    ``src/utils/doc_urls.py`` (so forks/tags stay aligned with in-app Help).
2. **Inline `src/...py` code paths.** A path written in backticks, such as
    `src/core/mpr_controller.py`, must exist. This catches the failure mode where a
    module moves between packages and prose that names it silently goes stale; a
    core/ to gui/ move left 17 such references wrong across the living docs before
    this check existed.

Usage (from repository root):
    python scripts/check_user_docs_links.py
    python scripts/check_user_docs_links.py --include-completed-plans  # advisory

Exit code: 0 if all blocking links resolve, 1 if any are broken (prints details).

Inputs: Markdown files on disk under the repo; ``GITHUB_BLOB_BASE`` from
``src/utils/doc_urls.py``.
Outputs: stdout messages; non-zero exit on failure.
Requirements: Python 3.9+; repository ``src/`` importable for ``utils.doc_urls``.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# [any](path) — path may include #anchor; exclude images ![alt](url) by requiring [ not preceded by !
LINK_PATTERN = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)")
# `src/pkg/module.py` written as inline code, optionally with a `:line` or
# `:line-range` suffix, which is how this repository cites code. Only .py paths,
# so prose naming a directory or a glob is not treated as a claim about one exact
# file. Path segments may not contain dots, which keeps illustrative prose such as
# `src/...py` from being read as a claim that a file exists.
#
# Note the deliberate limit: a name written as inline code is read as a claim that
# the file exists *now*. Prose proposing a file to create ("add `src/my_thing.py`")
# will be flagged. Write such names as a directory, a glob, or plain prose.
SRC_PATH_PATTERN = re.compile(
    r"`(src/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.py)(?::\d+(?:[-,]\d+)*)?`"
)
# Absolute GitHub blob links under user-docs/ must share GITHUB_BLOB_BASE.
GITHUB_BLOB_LINK_HINT = re.compile(r"https://github\.com/[^)\s]+/blob/")


def _completed_plans_root(repo_root: Path) -> Path:
    """Return the excluded ``dev-docs/plans/completed`` subtree.

    Resolved before use so a symlink in dev-docs/ cannot pull historical content
    back into the blocking set.
    """
    return (repo_root / "dev-docs" / "plans" / "completed").resolve()


def _is_excluded(candidate: Path, repo_root: Path) -> bool:
    """True for files outside the blocking set: completed plans and CHANGELOG.md."""
    resolved = candidate.resolve()
    if resolved.is_relative_to(_completed_plans_root(repo_root)):
        return True
    return resolved == (repo_root / "CHANGELOG.md").resolve()


def iter_markdown_files(
    repo_root: Path, include_completed_plans: bool = False
) -> list[Path]:
    """Markdown files to validate.

    Blocking set: user docs, the living dev docs, and the **active** plan tree
    (``dev-docs/plans/*.md`` plus ``dev-docs/plans/supporting/*.md``).
    ``dev-docs/plans/completed/`` and ``CHANGELOG.md`` are excluded because they
    describe the tree as it was; pass ``include_completed_plans=True`` to include
    them in an advisory pass.
    """
    paths: list[Path] = []
    user_docs = repo_root / "user-docs"
    if user_docs.is_dir():
        paths.extend(sorted(user_docs.rglob("*.md")))
    plans_root = repo_root / "dev-docs" / "plans"
    if plans_root.is_dir():
        # Active plans: the top level and supporting/. These are live documents.
        paths.extend(sorted(plans_root.glob("*.md")))
        supporting = plans_root / "supporting"
        if supporting.is_dir():
            paths.extend(sorted(supporting.glob("*.md")))
        if include_completed_plans:
            completed = plans_root / "completed"
            if completed.is_dir():
                paths.extend(sorted(completed.glob("*.md")))
    # Living dev docs. Resolve before excluding so a symlink in dev-docs/ cannot
    # pull excluded content back in.
    for subdir in ("dev-docs", "dev-docs/info"):
        directory = repo_root / subdir
        if not directory.is_dir():
            continue
        for candidate in sorted(directory.glob("*.md")):
            if _is_excluded(candidate, repo_root):
                continue
            paths.append(candidate)
    for rel in ("README.md", "ARCHITECTURE.md", "AGENTS.md"):
        candidate = repo_root / rel
        if candidate.is_file():
            paths.append(candidate)
    return sorted(set(paths))


def is_historical_record(md_path: Path, repo_root: Path) -> bool:
    """True when a file is in the advisory-only set (completed plans, CHANGELOG)."""
    return _is_excluded(md_path, repo_root)


def is_plan_document(md_path: Path, repo_root: Path) -> bool:
    """True when a file is a plan (active or completed) under ``dev-docs/plans/``.

    Plans get relative-link checking but not the inline ``src/...py`` existence
    check, because a plan may name a module it intends to create. See
    :func:`check_src_paths` for that contract.
    """
    plans_root = (repo_root / "dev-docs" / "plans").resolve()
    try:
        return md_path.resolve().is_relative_to(plans_root)
    except OSError:  # pragma: no cover - defensive
        return False


def exists_with_exact_case(repo_root: Path, relative: str) -> bool:
    """True when ``relative`` names a file that exists with exactly this casing.

    ``Path.is_file()`` follows the filesystem, which is case-insensitive on macOS
    and Windows. A doc naming ``src/GUI/main_window.py`` would therefore pass the
    pre-commit hook on a developer's Mac and then fail the same check on Linux
    CI. Comparing each component against the real directory listing makes local
    and CI agree.
    """
    current = repo_root
    for part in Path(relative).parts:
        try:
            names = {entry.name for entry in current.iterdir()}
        except (NotADirectoryError, PermissionError, FileNotFoundError):
            return False
        if part not in names:
            return False
        current = current / part
    return current.is_file()


def check_src_paths(md_path: Path, repo_root: Path) -> list[str]:
    """Return errors for inline `src/....py` paths that do not exist."""
    errors: list[str] = []
    text = md_path.read_text(encoding="utf-8")
    for src_path in SRC_PATH_PATTERN.findall(text):
        if not exists_with_exact_case(repo_root, src_path):
            errors.append(
                f"{md_path.relative_to(repo_root)}: names a source file that does "
                f"not exist: {src_path!r}"
            )
    return errors


def split_anchor(url: str) -> tuple[str, str]:
    if "#" in url:
        base, _, frag = url.partition("#")
        return base, frag
    return url, ""


def load_github_blob_base(repo_root: Path) -> str:
    """Return ``GITHUB_BLOB_BASE`` from ``src/utils/doc_urls.py`` (no trailing slash)."""
    src_root = str(repo_root / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)
    from utils.doc_urls import GITHUB_BLOB_BASE

    return GITHUB_BLOB_BASE.rstrip("/")


def check_github_blob_base_alignment(
    md_path: Path, repo_root: Path, blob_base: str
) -> list[str]:
    """Fail user-docs GitHub blob links that diverge from ``GITHUB_BLOB_BASE``."""
    errors: list[str] = []
    text = md_path.read_text(encoding="utf-8")
    for _label, raw_url in LINK_PATTERN.findall(text):
        url = raw_url.strip()
        if not GITHUB_BLOB_LINK_HINT.match(url):
            continue
        path_part, _anchor = split_anchor(url)
        if path_part == blob_base or path_part.startswith(blob_base + "/"):
            continue
        errors.append(
            f"{md_path.relative_to(repo_root)}: GitHub blob link {raw_url!r} "
            f"does not use GITHUB_BLOB_BASE ({blob_base!r})"
        )
    return errors


def check_file(md_path: Path, repo_root: Path, is_user_doc: bool = False) -> list[str]:
    """Return list of error messages for broken links in one file.

    When ``is_user_doc`` is True (the file lives under ``user-docs/``), relative
    links whose resolved target is outside ``user-docs/`` are rejected, even when
    the target exists elsewhere in the repository. Absolute ``https://``,
    ``http://``, ``mailto:``, and bare fragment-only targets remain allowed.
    """
    errors: list[str] = []
    text = md_path.read_text(encoding="utf-8")
    base_dir = md_path.parent
    user_docs_root = (repo_root / "user-docs").resolve()

    for _label, raw_url in LINK_PATTERN.findall(text):
        url = raw_url.strip()
        if not url or url.startswith(("#", "http://", "https://", "mailto:")):
            continue
        path_part, _anchor = split_anchor(url)
        if not path_part:
            continue
        target = (base_dir / path_part).resolve()
        try:
            target.relative_to(repo_root.resolve())
        except ValueError:
            errors.append(f"{md_path.relative_to(repo_root)}: link escapes repo: {raw_url!r}")
            continue
        if is_user_doc:
            try:
                target.relative_to(user_docs_root)
            except ValueError:
                errors.append(
                    f"{md_path.relative_to(repo_root)}: link escapes user-docs/: {raw_url!r}"
                )
                continue
        if not target.exists():
            errors.append(
                f"{md_path.relative_to(repo_root)}: broken link {raw_url!r} -> {target.relative_to(repo_root)}"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repository root (default: parent of scripts/).",
    )
    parser.add_argument(
        "--include-completed-plans",
        action="store_true",
        help=(
            "Also report link rot in dev-docs/plans/completed/ and CHANGELOG.md. "
            "Advisory only: reports and still exits 0, so historical-record debt "
            "is measurable without becoming a merge gate."
        ),
    )
    args = parser.parse_args()
    repo_root: Path = args.root.resolve()

    if not (repo_root / "user-docs").is_dir():
        print("error: user-docs/ was not found under the repository root", file=sys.stderr)
        return 1

    user_docs_root = repo_root / "user-docs"
    doc_urls_path = repo_root / "src" / "utils" / "doc_urls.py"
    blob_base = (
        load_github_blob_base(repo_root) if doc_urls_path.is_file() else None
    )
    blocking: list[str] = []
    advisory: list[str] = []
    files = iter_markdown_files(repo_root, args.include_completed_plans)
    for md in files:
        is_user_doc = md.is_relative_to(user_docs_root)
        errors = check_file(md, repo_root, is_user_doc=is_user_doc)
        # The inline `src/...py` check asserts that a backticked path names a
        # file that exists *now*, which is true of descriptive docs but false
        # of plans: a plan legitimately names modules it intends to create
        # ("add `src/core/image_pairing.py`"), and the checker's own contract
        # says such prose should be written as a glob or plain text instead.
        # Applying it to the plan tree would report 17 distinct proposed
        # modules as broken alongside the 16 genuinely-stale ones, so a gate
        # would be permanently red for a reason no edit can fix. Plans are
        # therefore link-checked only; the stale refs are swept separately.
        if not is_plan_document(md, repo_root):
            errors.extend(check_src_paths(md, repo_root))
        if is_user_doc and blob_base is not None:
            errors.extend(
                check_github_blob_base_alignment(md, repo_root, blob_base)
            )
        # Only rot in historical records is demoted; a broken link in a live
        # document blocks even during an advisory pass.
        if is_historical_record(md, repo_root):
            advisory.extend(errors)
        else:
            blocking.extend(errors)

    if blocking:
        print("Broken documentation references:", file=sys.stderr)
        for line in blocking:
            print(f"  {line}", file=sys.stderr)
        return 1

    n_files = len(files)
    scope = (
        "user-docs/, the living dev-docs/, the active plan tree, README.md, "
        "ARCHITECTURE.md, and AGENTS.md"
    )
    if advisory:
        print(
            f"OK: checked {n_files} Markdown file(s) ({scope}). "
            f"Advisory only - {len(advisory)} broken reference(s) in historical "
            "records (dev-docs/plans/completed/, CHANGELOG.md), which are "
            "excluded by policy because they describe the tree as it was:",
            file=sys.stderr,
        )
        for line in advisory:
            print(f"  {line}", file=sys.stderr)
    else:
        print(f"OK: checked links and src/ code paths in {n_files} Markdown file(s) ({scope}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
